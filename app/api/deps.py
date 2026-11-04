from collections.abc import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from app.core.security import decode_access_token
from app.database.models import User
from app.database.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _unauthorized() from None

    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.department), selectinload(User.roles))
    )
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def require_roles(*role_names: str) -> Callable[..., User]:
    allowed = set(role_names)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role_name not in allowed:
            raise HTTPException(status_code=403, detail="Not allowed")
        return user

    return checker


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
