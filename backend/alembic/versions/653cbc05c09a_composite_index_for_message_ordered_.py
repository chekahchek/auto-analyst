"""Composite index for message ordered retrieval.

Replaces the standalone ``ix_message_sequence`` and ``ix_message_session_id``
indexes with ``ix_message_session_id_sequence`` so that
``WHERE session_id = ? ORDER BY sequence`` is served by a single index.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "653cbc05c09a"
down_revision: Union[str, Sequence[str], None] = "6a9f3c2d4b8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_message_sequence"), table_name="message")
    op.drop_index(op.f("ix_message_session_id"), table_name="message")
    op.create_index(
        "ix_message_session_id_sequence",
        "message",
        ["session_id", "sequence"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_message_session_id_sequence", table_name="message")
    op.create_index(
        op.f("ix_message_session_id"), "message", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_message_sequence"), "message", ["sequence"], unique=False
    )