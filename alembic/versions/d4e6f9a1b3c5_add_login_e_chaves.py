"""adiciona usuários, sessões de login, chaves de API e dono do cliente (Fase 5)

Revision ID: d4e6f9a1b3c5
Revises: c3d5e8f0a2b4
Create Date: 2026-10-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'd4e6f9a1b3c5'
down_revision: Union[str, Sequence[str], None] = 'c3d5e8f0a2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'usuario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('senha_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuario_email'), ['email'], unique=True)

    op.create_table(
        'chaveapi',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('provedor', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('chave_cifrada', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('atualizada_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('chaveapi', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_chaveapi_usuario_id'), ['usuario_id'], unique=False)

    op.create_table(
        'sessaousuario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('expira_em', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('sessaousuario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessaousuario_usuario_id'), ['usuario_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sessaousuario_token_hash'), ['token_hash'], unique=True)

    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.add_column(sa.Column('usuario_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_cliente_usuario_id'), ['usuario_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cliente_usuario_id'))
        batch_op.drop_column('usuario_id')
    with op.batch_alter_table('sessaousuario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessaousuario_token_hash'))
        batch_op.drop_index(batch_op.f('ix_sessaousuario_usuario_id'))
    op.drop_table('sessaousuario')
    with op.batch_alter_table('chaveapi', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chaveapi_usuario_id'))
    op.drop_table('chaveapi')
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuario_email'))
    op.drop_table('usuario')
