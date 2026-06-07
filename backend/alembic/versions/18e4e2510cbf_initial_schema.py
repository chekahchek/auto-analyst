"""Initial schema migration.

Creates tables for user, dataset, session, and message.

Notes:
- `updated_at` columns use `server_default=sa.text('now()')` for the initial value.
- `onupdate` behavior is handled at the ORM/SQLAlchemy level, so it is intentionally
  absent from the migration DDL.
- `message` table intentionally omits `updated_at` (append-only design).
- `MessageRole` enum stores member names (uppercase) in the database — this is
  standard SQLAlchemy `Enum` behavior.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "18e4e2510cbf"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)
    op.create_table(
        "dataset",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "original_filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("domain", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("data_type", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dataset_user_id"), "dataset", ["user_id"], unique=False)
    op.create_table(
        "session",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("dashboard_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("cost_spent", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_session_dataset_id"), "session", ["dataset_id"], unique=False
    )
    op.create_table(
        "message",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "ASSISTANT", "SYSTEM", "TOOL", name="messagerole"),
            nullable=False,
        ),
        sa.Column("content", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("metadata_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_sequence"), "message", ["sequence"], unique=False)
    op.create_index(
        op.f("ix_message_session_id"), "message", ["session_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_message_session_id"), table_name="message")
    op.drop_index(op.f("ix_message_sequence"), table_name="message")
    op.drop_table("message")
    op.drop_index(op.f("ix_session_dataset_id"), table_name="session")
    op.drop_table("session")
    op.drop_index(op.f("ix_dataset_user_id"), table_name="dataset")
    op.drop_table("dataset")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
