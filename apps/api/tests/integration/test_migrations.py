import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.migrations_runner import downgrade_to_base, upgrade_to_head
from nfactory_core.models import Base

pytestmark = pytest.mark.integration


def _query(url: str, sql: str) -> set[str]:
    dsn = make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(dsn) as conn:
        return {row[0] for row in conn.execute(sql).fetchall()}


TABLES_SQL = "select tablename from pg_tables where schemaname = 'public'"


def test_upgrade_creates_every_model_table_and_pgvector(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)

    tables = _query(empty_database_url, TABLES_SQL)
    assert set(Base.metadata.tables) <= tables
    assert "vector" in _query(empty_database_url, "select extname from pg_extension")


def test_downgrade_removes_every_table(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)
    downgrade_to_base(empty_database_url)

    assert _query(empty_database_url, TABLES_SQL) <= {"alembic_version"}


def test_upgrade_is_idempotent(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)
    upgrade_to_head(empty_database_url)  # must be a no-op, not an error


def test_the_migrations_match_the_models(empty_database_url: str) -> None:
    """A hand-written migration must build exactly the tables the models describe."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine

    upgrade_to_head(empty_database_url)
    engine = create_engine(empty_database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_name": lambda name, type_, parents: (
                        type_ != "table" or name in Base.metadata.tables
                    )
                },
            )
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == []
