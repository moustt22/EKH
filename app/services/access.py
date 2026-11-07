import uuid

from app.core.documents import AccessScope, DocumentStatus
from app.core.roles import RoleName
from app.database.models import Document, User


def can_read(
    user: User,
    document: Document,
    grant_user_ids: set[uuid.UUID],
    department_ids: set[uuid.UUID] | None = None,
) -> bool:
    if document.status == DocumentStatus.DELETED.value:
        return False
    if user.role_name == RoleName.ADMINISTRATOR.value:
        return True
    if document.owner_id == user.id:
        return True
    if user.id in grant_user_ids:
        return True
    readable_departments = department_ids or {document.department_id}
    return (
        document.access_scope == AccessScope.DEPARTMENT.value
        and user.department_id in readable_departments
    )


def can_manage(user: User, document: Document) -> bool:
    if document.status == DocumentStatus.DELETED.value:
        return False
    if user.role_name == RoleName.ADMINISTRATOR.value:
        return True
    return (
        user.role_name == RoleName.DEPARTMENT_MANAGER.value
        and (
            document.department_id == user.department_id
            or any(item.department_id == user.department_id for item in document.departments)
        )
    )


def can_upload_to(user: User, department_id: uuid.UUID) -> bool:
    if user.role_name == RoleName.ADMINISTRATOR.value:
        return True
    return user.role_name == RoleName.DEPARTMENT_MANAGER.value and user.department_id == department_id
