from collections.abc import Sequence

from alembic import op

revision: str = "a3c9e1d2b7f4"
down_revision: str | None = "f8fac76870d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
