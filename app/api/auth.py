from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.database.models import User
from app.database.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.audit import record_audit
from app.services.users import authenticate, serialize_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        record_audit(db, action="login", outcome="denied", actor_email=payload.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    record_audit(db, action="login", outcome="allowed", actor=user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/logout", status_code=204)
def logout(_: User = Depends(get_current_user)) -> Response:
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return serialize_user(user)
