"""add tenant organizations and users tables and link to sources

Revision ID: fa9d49737cf6
Revises: 7c230dca3ad9
Create Date: 2026-07-10 22:52:35.821109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa9d49737cf6'
down_revision: Union[str, Sequence[str], None] = '7c230dca3ad9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('organizations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('org_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.String(), nullable=True))
        batch_op.create_foreign_key('fk_sources_org_id', 'organizations', ['org_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('sources', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sources_org_id', type_='foreignkey')
        batch_op.drop_column('org_id')
        
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('organizations')
