"""Set Andrey Filin as default assignee and assign all unassigned tickets to him.

Revision ID: 019
Revises: 018
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FILIN_EMAIL = "afilin@pass24online.ru"


def upgrade() -> None:
    conn = op.get_bind()

    # Find Andrey Filin's user ID by email
    result = conn.execute(
        sa.text("SELECT id FROM \"user\" WHERE email = :email"),
        {"email": FILIN_EMAIL},
    )
    row = result.fetchone()
    if not row:
        raise RuntimeError(f"User with email {FILIN_EMAIL} not found")
    filin_id = row[0]

    # Set default assignee in app_settings (upsert)
    existing = conn.execute(
        sa.text("SELECT id FROM app_settings WHERE key = 'default_assignee_id'")
    ).fetchone()
    if existing:
        conn.execute(
            sa.text("UPDATE app_settings SET value = :val WHERE key = 'default_assignee_id'"),
            {"val": filin_id},
        )
    else:
        import uuid
        conn.execute(
            sa.text("INSERT INTO app_settings (id, key, value) VALUES (:id, 'default_assignee_id', :val)"),
            {"id": str(uuid.uuid4()), "val": filin_id},
        )

    # Assign all unassigned tickets to Filin
    result = conn.execute(
        sa.text("UPDATE ticket SET assignee_id = :aid WHERE assignee_id IS NULL"),
        {"aid": filin_id},
    )
    print(f"Assigned {result.rowcount} unassigned tickets to {FILIN_EMAIL} ({filin_id})")


def downgrade() -> None:
    # Remove default assignee setting (don't unassign tickets — that's destructive)
    op.execute(sa.text("DELETE FROM app_settings WHERE key = 'default_assignee_id'"))
