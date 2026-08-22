"""Drop dataset.domain.

The business domain is omitted for now; data_type alone drives analytical skill selection.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "d1f0a2b3c445"
down_revision: Union[str, Sequence[str], None] = "653cbc05c09a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("dataset", "domain")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "dataset",
        sa.Column("domain", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
