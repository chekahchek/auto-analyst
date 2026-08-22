"""Schema revision: simplify datasets/sessions and add artifacts.

Changes:
- Drop ``dataset.filename`` and ``dataset.updated_at`` (immutable, user-facing only).
- Drop ``user.updated_at``.
- Drop ``session.dashboard_path`` and ``session.cost_spent`` (latest dashboard now
  lives on the latest ``artifact``; cost tracking stays in logs/OTel).
- Drop ``message.metadata_json`` (unused).
- Add ``artifact`` table to store per-iteration analysis outputs so follow-up
  questions can hydrate the full context across iterations.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "6a9f3c2d4b8e"
down_revision: Union[str, Sequence[str], None] = "18e4e2510cbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("dataset", "filename")
    op.drop_column("dataset", "updated_at")
    op.drop_column("user", "updated_at")
    op.drop_column("session", "dashboard_path")
    op.drop_column("session", "cost_spent")
    op.drop_column("message", "metadata_json")

    op.create_table(
        "artifact",
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("hypotheses_evidence_json", sa.JSON(), nullable=True),
        sa.Column("narrative_json", sa.JSON(), nullable=True),
        sa.Column("dashboard_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_artifact_session_id"), "artifact", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact_iteration"), "artifact", ["iteration"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_artifact_iteration"), table_name="artifact")
    op.drop_index(op.f("ix_artifact_session_id"), table_name="artifact")
    op.drop_table("artifact")

    op.add_column(
        "message",
        sa.Column("metadata_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "session",
        sa.Column(
            "cost_spent",
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            server_default="0.0000",
        ),
    )
    op.add_column(
        "session",
        sa.Column("dashboard_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.add_column(
        "dataset",
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.add_column(
        "dataset",
        sa.Column(
            "filename",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="",
        ),
    )
