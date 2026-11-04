"""Identity tables: departments, roles, users.

Revision ID: 20261102_0002
Revises: 20261102_0001
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0002"
down_revision: Union[str, Sequence[str], None] = "20261102_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_users_department_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_roles_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_user_roles_role_id"),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("departments")
