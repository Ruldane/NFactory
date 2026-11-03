"""Alembic environment. Runs migrations synchronously with the psycopg driver."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from nfactory_core.config import get_settings
from nfactory_core.models import Base

config = context.config
if config.config_file_name and not config.attributes.get("skip_logging"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # Only our models: LangGraph's checkpoint tables live in the same database.
    return type_ != "table" or name in target_metadata.tables


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata, literal_binds=True, include_name=include_name
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_name=include_name
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
