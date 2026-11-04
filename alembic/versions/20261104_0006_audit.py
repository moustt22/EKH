"""Audit events for security-sensitive actions.

Revision ID: 20261104_0006
Revises: 20261104_0005
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0006"
down_revision: Union[str, Sequence[str], None] = "20261104_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_audit_events_actor_id"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
