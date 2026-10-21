"""adiciona conversas (Fase 5 — novas conversas)

Revision ID: c3d5e8f0a2b4
Revises: b2e4f7a9c1d3
Create Date: 2026-10-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c3d5e8f0a2b4'
down_revision: Union[str, Sequence[str], None] = 'b2e4f7a9c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Mensagens antigas ficam com conversa_id = "" (a "Conversa inicial").
    with op.batch_alter_table('chatmessage', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'conversa_id',
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default='',
            )
        )
        batch_op.create_index(
            batch_op.f('ix_chatmessage_conversa_id'), ['conversa_id'], unique=False
        )

    op.create_table(
        'conversa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('conversa_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('titulo', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('conversa', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_conversa_session_id'), ['session_id'], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('conversa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_conversa_session_id'))
    op.drop_table('conversa')
    with op.batch_alter_table('chatmessage', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chatmessage_conversa_id'))
        batch_op.drop_column('conversa_id')
