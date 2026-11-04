"""Document metadata, versions, grants, and ingestion jobs.

Revision ID: 20261102_0003
Revises: 20261102_0002
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0003"
down_revision: Union[str, Sequence[str], None] = "20261102_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=10), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("department_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("access_scope", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_documents_owner_id"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_documents_department_id"),
    )
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index("ix_documents_department_id", "documents", ["department_id"])
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_document_versions_document_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_document_versions_created_by"),
        sa.UniqueConstraint("storage_key", name="uq_document_versions_storage_key"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_number"),
    )
    op.create_table(
        "document_grants",
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_document_grants_document_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_document_grants_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_document_grants_created_by"),
        sa.PrimaryKeyConstraint("document_id", "user_id", name="pk_document_grants"),
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name="fk_ingestion_jobs_document_id", ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("document_grants")
    op.drop_table("document_versions")
    op.drop_index("ix_documents_department_id", table_name="documents")
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_table("documents")
