"""Chunk text stored for citations and reindexing.

Revision ID: 20261104_0004
Revises: 20261102_0003
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_0004"
down_revision: Union[str, Sequence[str], None] = "20261102_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_chunks_document_id", ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "version_number", "chunk_index", name="uq_chunks_position"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
