"""Allow documents to be visible to more than one department."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0007"
down_revision: Union[str, Sequence[str], None] = "20261104_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_departments",
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("department_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "department_id"),
    )
    op.execute(
        "INSERT INTO document_departments (document_id, department_id) "
        "SELECT id, department_id FROM documents"
    )


def downgrade() -> None:
    op.drop_table("document_departments")
