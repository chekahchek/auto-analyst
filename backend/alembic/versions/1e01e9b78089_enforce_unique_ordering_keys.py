"""Enforce unique ordering keys on message and artifact.

``(session_id, sequence)`` orders messages and ``(session_id, iteration)`` keys
artifacts. Both numbers are read-then-incremented, so two concurrent chat turns on one
session can pick the same number. The unique indexes turn that race into an integrity
error instead of duplicated rows. The upgrade fails if duplicate keys already exist.

The artifact composite index also serves ``WHERE session_id = ?`` lookups, so the
standalone ``session_id`` and ``iteration`` indexes are dropped.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1e01e9b78089"
down_revision: Union[str, Sequence[str], None] = "4dddd1694aa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_message_session_id_sequence", table_name="message")
    op.create_index(
        "ix_message_session_id_sequence",
        "message",
        ["session_id", "sequence"],
        unique=True,
    )
    op.drop_index(op.f("ix_artifact_iteration"), table_name="artifact")
    op.drop_index(op.f("ix_artifact_session_id"), table_name="artifact")
    op.create_index(
        "ix_artifact_session_id_iteration",
        "artifact",
        ["session_id", "iteration"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_artifact_session_id_iteration", table_name="artifact")
    op.create_index(
        op.f("ix_artifact_session_id"), "artifact", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact_iteration"), "artifact", ["iteration"], unique=False
    )
    op.drop_index("ix_message_session_id_sequence", table_name="message")
    op.create_index(
        "ix_message_session_id_sequence",
        "message",
        ["session_id", "sequence"],
        unique=False,
    )
