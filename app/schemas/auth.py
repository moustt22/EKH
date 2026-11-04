import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import RoleName


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    department_id: uuid.UUID
    role: RoleName


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    department_id: uuid.UUID | None = None
    role: RoleName | None = None
    is_active: bool | None = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    department_id: uuid.UUID
    department_name: str
    role: str
    is_active: bool
