"""Store dataset.data_type as JSON.

The profiler returns either a string or a list of strings. Lists were stored as
JSON-encoded strings and decoded on every read. Existing rows are converted in place:
JSON-encoded lists become JSON arrays and plain strings become JSON strings. A value
that starts with "[" must be valid JSON, otherwise the upgrade fails and rolls back.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "61857c63fc23"
down_revision: Union[str, Sequence[str], None] = "1e01e9b78089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "dataset",
        "data_type",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using=(
            "CASE WHEN data_type IS NULL THEN NULL "
            "WHEN left(data_type, 1) = '[' THEN data_type::json "
            "ELSE to_json(data_type) END"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "dataset",
        "data_type",
        existing_type=sa.JSON(),
        type_=sqlmodel.sql.sqltypes.AutoString(),
        existing_nullable=True,
        postgresql_using="data_type #>> '{}'",
    )
