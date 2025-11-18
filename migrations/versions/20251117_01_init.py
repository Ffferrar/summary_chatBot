"""initial tables for messages and answers

Revision ID: 20251117_01
Revises: 
Create Date: 2025-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251117_01'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tg_message_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('tg_user_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'answers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('asked_by_user_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('chat_id', sa.BigInteger(), nullable=False, index=True),
        sa.Column('tg_answer_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'answer_base_messages',
        sa.Column('answer_id', sa.Integer(), sa.ForeignKey('answers.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='CASCADE'), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('answer_base_messages')
    op.drop_table('answers')
    op.drop_table('messages')
