"""add role to users

Revision ID: 0003_add_role_to_users
Revises: 0002_add_company_to_users
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_role_to_users"
down_revision: Union[str, Sequence[str], None] = "0002_add_company_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(20), nullable=True))
    op.execute("UPDATE users SET role = 'user'")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role", nullable=False, existing_type=sa.String(20))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
