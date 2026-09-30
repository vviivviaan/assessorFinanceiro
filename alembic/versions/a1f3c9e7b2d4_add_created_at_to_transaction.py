"""adiciona created_at em transaction (Fase 6, item 4 — aba de Transações)

Revision ID: a1f3c9e7b2d4
Revises: 312668d180e5
Create Date: 2026-09-30 19:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a1f3c9e7b2d4'
down_revision: Union[str, Sequence[str], None] = '312668d180e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default garante que linhas já existentes recebam a data/hora da
    # migração em vez de ficarem com created_at nulo (a aba de Transações
    # agrupa por dia, então toda linha precisa de uma data utilizável).
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'created_at',
                sa.DateTime(),
                nullable=True,
                server_default=sa.text('CURRENT_TIMESTAMP'),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_column('created_at')
