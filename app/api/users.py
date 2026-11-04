import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.roles import RoleName
from app.database.models import User
from app.database.session import get_db
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services.users import UserServiceError, create_user, list_users, serialize_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def get_users(
    _: User = Depends(require_roles(RoleName.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    return [serialize_user(user) for user in list_users(db)]


@router.post("", response_model=UserOut, status_code=201)
def post_user(
    payload: UserCreate,
    _: User = Depends(require_roles(RoleName.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        user = create_user(db, payload)
    except UserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return serialize_user(user)


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    _: User = Depends(require_roles(RoleName.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        user = update_user(db, user_id, payload)
    except UserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return serialize_user(user)
