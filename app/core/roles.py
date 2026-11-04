from enum import Enum


class RoleName(str, Enum):
    EMPLOYEE = "employee"
    DEPARTMENT_MANAGER = "department_manager"
    ADMINISTRATOR = "administrator"


DEPARTMENT_NAMES = (
    "HR",
    "Engineering",
    "Finance",
    "Sales",
    "Operations",
    "Management",
)

ROLE_NAMES = tuple(role.value for role in RoleName)
