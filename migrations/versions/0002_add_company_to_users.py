"""add company to users

Revision ID: 0002_add_company_to_users
Revises: 0001_initial_users_table
Create Date: 2026-05-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_company_to_users"
down_revision: Union[str, Sequence[str], None] = "0001_initial_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("company", sa.String(length=255), nullable=False, server_default=""))
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("company", server_default=None, existing_type=sa.String(255), existing_nullable=False)


def downgrade() -> None:
    op.drop_column("users", "company")
