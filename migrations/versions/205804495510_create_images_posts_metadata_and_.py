"""create images posts metadata and vectors tables

Revision ID: 205804495510
Revises: a97d1eb44701
Create Date: 2026-08-19 19:55:17.744350

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '205804495510'
down_revision: Union[str, Sequence[str], None] = 'a97d1eb44701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('image_data', sa.LargeBinary(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('source_url', sa.String(length=512), nullable=True),
    sa.Column('license', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=512), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('image_metadata',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('image_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=64), nullable=False),
    sa.Column('subject', sa.String(length=64), nullable=False),
    sa.Column('attributes', sa.JSON(), nullable=True),
    sa.Column('caption', sa.Text(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('needs_review', sa.Boolean(), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('model_version', sa.String(length=128), nullable=True),
    sa.Column('raw_response', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('image_id', name='uq_image_metadata_image_id')
    )
    op.create_index(op.f('ix_image_metadata_category'), 'image_metadata', ['category'], unique=False)
    op.create_index(op.f('ix_image_metadata_image_id'), 'image_metadata', ['image_id'], unique=False)
    op.create_index(op.f('ix_image_metadata_subject'), 'image_metadata', ['subject'], unique=False)
    op.create_table('image_vectors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('image_id', sa.Integer(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('image_id', name='uq_image_vectors_image_id')
    )
    op.create_index(op.f('ix_image_vectors_image_id'), 'image_vectors', ['image_id'], unique=False)
    op.create_table('post_vectors',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('post_id', sa.Integer(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id', name='uq_post_vectors_post_id')
    )
    op.create_index(op.f('ix_post_vectors_post_id'), 'post_vectors', ['post_id'], unique=False)
    op.create_index(op.f('ix_ai_call_log_created_at'), 'ai_call_log', ['created_at'], unique=False)
    op.create_index(op.f('ix_ai_call_log_image_id'), 'ai_call_log', ['image_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ai_call_log_image_id'), table_name='ai_call_log')
    op.drop_index(op.f('ix_ai_call_log_created_at'), table_name='ai_call_log')
    op.drop_index(op.f('ix_post_vectors_post_id'), table_name='post_vectors')
    op.drop_table('post_vectors')
    op.drop_index(op.f('ix_image_vectors_image_id'), table_name='image_vectors')
    op.drop_table('image_vectors')
    op.drop_index(op.f('ix_image_metadata_subject'), table_name='image_metadata')
    op.drop_index(op.f('ix_image_metadata_image_id'), table_name='image_metadata')
    op.drop_index(op.f('ix_image_metadata_category'), table_name='image_metadata')
    op.drop_table('image_metadata')
    op.drop_table('posts')
    op.drop_table('images')
