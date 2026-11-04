from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.models import User
from app.database.session import get_db
from app.schemas.auth import DepartmentOut
from app.services.users import list_departments

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def get_departments(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DepartmentOut]:
    return [DepartmentOut.model_validate(department) for department in list_departments(db)]
