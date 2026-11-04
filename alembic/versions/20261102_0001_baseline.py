"""Baseline schema. Tables arrive in later revisions.

Revision ID: 20261102_0001
Revises:
Create Date: 2026-11-02
"""

from typing import Sequence, Union

revision: str = "20261102_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
