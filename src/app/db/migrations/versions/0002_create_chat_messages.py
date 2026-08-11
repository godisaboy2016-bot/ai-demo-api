"""create chat messages table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the chat_messages table."""

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_messages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name=op.f("ck_chat_messages_role"),
        ),
    )
    op.create_index(
        "ix_chat_messages_user_created_id",
        "chat_messages",
        ["user_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_chat_messages_conversation_created_id",
        "chat_messages",
        ["conversation_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    """Drop the chat_messages table."""

    op.drop_index("ix_chat_messages_user_created_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation_created_id", table_name="chat_messages")
    op.drop_table("chat_messages")
