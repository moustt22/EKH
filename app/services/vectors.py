from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, get_settings


class VectorIndexError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass
class IndexPoint:
    point_id: str
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]
    payload: dict


@dataclass(frozen=True)
class SearchScope:
    user_id: str
    department_id: str
    is_admin: bool
    file_type: str | None = None
    classification: str | None = None
    department_filter: str | None = None


@dataclass(frozen=True)
class ScoredPoint:
    point_id: str
    score: float
    payload: dict


class MemoryVectorIndex:
    def __init__(self) -> None:
        self.points: dict[str, IndexPoint] = {}

    def upsert(self, points: list[IndexPoint]) -> None:
        for point in points:
            self.points[point.point_id] = point

    def deactivate_other_versions(self, document_id: str, keep_version: int) -> None:
        for point in self.points.values():
            if point.payload.get("document_id") == document_id and point.payload.get("version") != keep_version:
                point.payload["is_active"] = False

    def delete_document(self, document_id: str) -> None:
        self.points = {
            point_id: point
            for point_id, point in self.points.items()
            if point.payload.get("document_id") != document_id
        }

    def set_allowed_users(self, document_id: str, user_ids: list[str]) -> None:
        for point in self.points.values():
            if point.payload.get("document_id") == document_id:
                point.payload["allowed_user_ids"] = list(user_ids)

    def search(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        scope: SearchScope,
        limit: int = 24,
    ) -> list[ScoredPoint]:
        allowed = [point for point in self.points.values() if _payload_matches(point.payload, scope)]
        dense_order = sorted(allowed, key=lambda point: _cosine(dense, point.dense), reverse=True)
        sparse_order = sorted(
            allowed,
            key=lambda point: _sparse_overlap(sparse_indices, sparse_values, point),
            reverse=True,
        )
        fused = _reciprocal_rank_fusion(
            [point.point_id for point in dense_order],
            [point.point_id for point in sparse_order],
        )
        by_id = {point.point_id: point for point in allowed}
        return [
            ScoredPoint(point_id=point_id, score=score, payload=by_id[point_id].payload)
            for point_id, score in fused[:limit]
        ]


class QdrantVectorIndex:
    def __init__(self, settings: Settings | None = None) -> None:
        from qdrant_client import QdrantClient

        settings = settings or get_settings()
        self.collection = settings.qdrant_collection
        self.dimensions = settings.embed_dim
        self.client = QdrantClient(url=settings.qdrant_url, timeout=30)
        self._ready = False

    def upsert(self, points: list[IndexPoint]) -> None:
        if not points:
            return
        self._ensure()
        from qdrant_client.models import PointStruct, SparseVector

        try:
            self.client.upsert(
                collection_name=self.collection,
                points=[
                    PointStruct(
                        id=point.point_id,
                        vector={
                            "dense": point.dense,
                            "bm25": SparseVector(indices=point.sparse_indices, values=point.sparse_values),
                        },
                        payload=point.payload,
                    )
                    for point in points
                ],
            )
        except Exception as exc:
            raise VectorIndexError("Could not index the document") from exc

    def deactivate_other_versions(self, document_id: str, keep_version: int) -> None:
        self._set_payload(
            {"is_active": False},
            document_id=document_id,
            exclude_version=keep_version,
        )

    def delete_document(self, document_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        self._ensure()
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=FilterSelector(
                    filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
                ),
            )
        except Exception as exc:
            raise VectorIndexError("Could not remove the document from the index") from exc

    def set_allowed_users(self, document_id: str, user_ids: list[str]) -> None:
        self._set_payload({"allowed_user_ids": user_ids}, document_id=document_id, exclude_version=None)

    def search(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        scope: SearchScope,
        limit: int = 24,
    ) -> list[ScoredPoint]:
        from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

        self._ensure()
        query_filter = _qdrant_filter(scope)
        try:
            result = self.client.query_points(
                collection_name=self.collection,
                prefetch=[
                    Prefetch(query=dense, using="dense", filter=query_filter, limit=max(limit, 30)),
                    Prefetch(
                        query=SparseVector(indices=sparse_indices, values=sparse_values),
                        using="bm25",
                        filter=query_filter,
                        limit=max(limit, 30),
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorIndexError("Could not search the index") from exc
        return [
            ScoredPoint(point_id=str(point.id), score=float(point.score or 0), payload=point.payload or {})
            for point in result.points
        ]

    def _set_payload(self, payload: dict, *, document_id: str, exclude_version: int | None) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        self._ensure()
        query = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
        if exclude_version is not None:
            query.must_not = [FieldCondition(key="version", match=MatchValue(value=exclude_version))]
        try:
            self.client.set_payload(collection_name=self.collection, payload=payload, points=query)
        except Exception as exc:
            raise VectorIndexError("Could not update the document index") from exc

    def _ensure(self) -> None:
        if self._ready:
            return
        from qdrant_client.models import Distance, Modifier, SparseVectorParams, VectorParams

        try:
            names = {item.name for item in self.client.get_collections().collections}
            if self.collection not in names:
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config={"dense": VectorParams(size=self.dimensions, distance=Distance.COSINE)},
                    sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
                )
        except Exception as exc:
            raise VectorIndexError("Could not prepare the search index") from exc
        self._ready = True


class VectorIndex(Protocol):
    def upsert(self, points: list[IndexPoint]) -> None: ...

    def deactivate_other_versions(self, document_id: str, keep_version: int) -> None: ...

    def delete_document(self, document_id: str) -> None: ...

    def set_allowed_users(self, document_id: str, user_ids: list[str]) -> None: ...

    def search(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        scope: SearchScope,
        limit: int = 24,
    ) -> list[ScoredPoint]: ...


def _payload_matches(payload: dict, scope: SearchScope) -> bool:
    if payload.get("is_active") is not True:
        return False
    if scope.file_type and payload.get("file_type") != scope.file_type:
        return False
    if scope.classification and payload.get("classification") != scope.classification:
        return False
    if scope.department_filter and payload.get("department_id") != scope.department_filter:
        return False
    if scope.is_admin:
        return True
    if payload.get("owner_id") == scope.user_id:
        return True
    if scope.user_id in payload.get("allowed_user_ids", []):
        return True
    return payload.get("access_scope") == "department" and payload.get("department_id") == scope.department_id


def _qdrant_filter(scope: SearchScope):
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, MinShould

    must = [FieldCondition(key="is_active", match=MatchValue(value=True))]
    if scope.file_type:
        must.append(FieldCondition(key="file_type", match=MatchValue(value=scope.file_type)))
    if scope.classification:
        must.append(FieldCondition(key="classification", match=MatchValue(value=scope.classification)))
    if scope.department_filter:
        must.append(FieldCondition(key="department_id", match=MatchValue(value=scope.department_filter)))
    query = Filter(must=must)
    if scope.is_admin:
        return query
    access = [
        FieldCondition(key="owner_id", match=MatchValue(value=scope.user_id)),
        FieldCondition(key="allowed_user_ids", match=MatchAny(any=[scope.user_id])),
        Filter(
            must=[
                FieldCondition(key="access_scope", match=MatchValue(value="department")),
                FieldCondition(key="department_id", match=MatchValue(value=scope.department_id)),
            ]
        ),
    ]
    query.min_should = MinShould(conditions=access, min_count=1)
    return query


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _sparse_overlap(indices: list[int], values: list[float], point: IndexPoint) -> float:
    stored = dict(zip(point.sparse_indices, point.sparse_values, strict=False))
    return sum(value * stored.get(index, 0.0) for index, value in zip(indices, values, strict=False))


def _reciprocal_rank_fusion(*rankings: list[str], constant: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, point_id in enumerate(ranking, start=1):
            scores[point_id] = scores.get(point_id, 0.0) + 1.0 / (constant + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def get_vector_index() -> VectorIndex:
    return QdrantVectorIndex()
