from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.roles import DEPARTMENT_NAMES, ROLE_NAMES, RoleName
from app.core.security import hash_password
from app.database.models import Department, Role, User
from app.database.session import SessionLocal

DEMO_PASSWORD = "ChangeMe123!"

DEMO_USERS = (
    {
        "name": "Northwind Admin",
        "email": "admin@northwind.example",
        "department": "Management",
        "role": RoleName.ADMINISTRATOR.value,
    },
    {
        "name": "Engineering Employee",
        "email": "eng.employee@northwind.example",
        "department": "Engineering",
        "role": RoleName.EMPLOYEE.value,
    },
    {
        "name": "HR Manager",
        "email": "hr.manager@northwind.example",
        "department": "HR",
        "role": RoleName.DEPARTMENT_MANAGER.value,
    },
)


def seed_database(session: Session, password: str = DEMO_PASSWORD) -> None:
    departments = {name: _get_or_create_department(session, name) for name in DEPARTMENT_NAMES}
    roles = {name: _get_or_create_role(session, name) for name in ROLE_NAMES}
    session.flush()

    for spec in DEMO_USERS:
        existing = session.scalar(select(User).where(User.email == spec["email"]))
        if existing is not None:
            continue
        user = User(
            name=spec["name"],
            email=spec["email"],
            password_hash=hash_password(password),
            department_id=departments[spec["department"]].id,
            is_active=True,
        )
        user.roles = [roles[spec["role"]]]
        session.add(user)

    session.commit()


def _get_or_create_department(session: Session, name: str) -> Department:
    department = session.scalar(select(Department).where(Department.name == name))
    if department is None:
        department = Department(name=name)
        session.add(department)
    return department


def _get_or_create_role(session: Session, name: str) -> Role:
    role = session.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        session.add(role)
    return role


def main() -> None:
    settings = get_settings()
    if settings.environment != "local":
        raise SystemExit("Seed runs only when ENVIRONMENT=local.")
    with SessionLocal() as session:
        seed_database(session)


if __name__ == "__main__":
    main()
