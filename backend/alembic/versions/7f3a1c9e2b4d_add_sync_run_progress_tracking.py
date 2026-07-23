"""add sync run progress tracking (total_estimate, roster run_type)

Revision ID: 7f3a1c9e2b4d
Revises: dcec4998b905
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f3a1c9e2b4d'
down_revision: Union[str, None] = 'dcec4998b905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('sync_runs', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('total_estimate', sa.Integer(), nullable=True))
        batch_op.drop_constraint('ck_sync_run_type', type_='check')
        batch_op.create_check_constraint(
            'ck_sync_run_type', "run_type IN ('manual','scheduled','add_ticket','backfill','roster')"
        )


def downgrade() -> None:
    with op.batch_alter_table('sync_runs', recreate='always') as batch_op:
        batch_op.drop_constraint('ck_sync_run_type', type_='check')
        batch_op.create_check_constraint(
            'ck_sync_run_type', "run_type IN ('manual','scheduled','add_ticket','backfill')"
        )
        batch_op.drop_column('total_estimate')
