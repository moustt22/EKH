import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password, verify_password
from app.database.models import Department, Role, User
from app.schemas.auth import UserCreate, UserOut, UserUpdate


class UserServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def list_departments(db: Session) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.name)))


def list_users(db: Session) -> list[User]:
    statement = (
        select(User)
        .options(selectinload(User.department), selectinload(User.roles))
        .order_by(User.email)
    )
    return list(db.scalars(statement))


def create_user(db: Session, payload: UserCreate) -> User:
    department = db.get(Department, payload.department_id)
    if department is None:
        raise UserServiceError(404, "Department not found")
    role = db.scalar(select(Role).where(Role.name == payload.role.value))
    if role is None:
        raise UserServiceError(400, "Role is not configured")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        department_id=department.id,
        is_active=True,
        updated_at=datetime.now(timezone.utc),
    )
    user.roles = [role]
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise UserServiceError(409, "A user with that email already exists") from exc
    return _load_user(db, user.id)


def update_user(db: Session, user_id: uuid.UUID, payload: UserUpdate) -> User:
    user = _load_user(db, user_id)
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.department_id is not None:
        department = db.get(Department, payload.department_id)
        if department is None:
            raise UserServiceError(404, "Department not found")
        user.department_id = department.id
    if payload.role is not None:
        role = db.scalar(select(Role).where(Role.name == payload.role.value))
        if role is None:
            raise UserServiceError(400, "Role is not configured")
        user.roles = [role]
    if payload.is_active is not None:
        user.is_active = payload.is_active
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _load_user(db, user.id)


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(
        select(User)
        .where(User.email == email.lower())
        .options(selectinload(User.department), selectinload(User.roles))
    )
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        department_id=user.department_id,
        department_name=user.department.name,
        role=user.role_name,
        is_active=user.is_active,
    )


def _load_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.department), selectinload(User.roles))
    )
    if user is None:
        raise UserServiceError(404, "User not found")
    return user
