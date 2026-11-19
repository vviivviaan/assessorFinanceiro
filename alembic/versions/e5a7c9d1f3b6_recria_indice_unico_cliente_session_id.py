"""recria o índice único de cliente.session_id

A migração anterior (4281cdfcba2a) foi gerada automaticamente e removeu esse
índice porque o model `Cliente` não o declarava. Ele é necessário: garante
que dois clientes nunca compartilhem o mesmo session_id (e, com isso, os
mesmos dados). O model agora declara o índice e esta migração o recria.

Revision ID: e5a7c9d1f3b6
Revises: 4281cdfcba2a
Create Date: 2026-11-11 23:30:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5a7c9d1f3b6'
down_revision: Union[str, Sequence[str], None] = '4281cdfcba2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cliente_session_id'), ['session_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('cliente', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cliente_session_id'))
