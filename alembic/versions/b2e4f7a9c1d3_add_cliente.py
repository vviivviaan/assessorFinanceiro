"""adiciona tabela cliente (Fase 7 — modo multiempresa/multicliente)

Revision ID: b2e4f7a9c1d3
Revises: a1f3c9e7b2d4
Create Date: 2026-10-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'b2e4f7a9c1d3'
down_revision: Union[str, Sequence[str], None] = 'a1f3c9e7b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cliente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('session_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_cliente_session_id'), ['session_id'], unique=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cliente_session_id'))
    op.drop_table('cliente')
