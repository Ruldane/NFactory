"""Programmatic Alembic entry points, used by the bootstrap job and by tests."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_API_ROOT = Path(__file__).resolve().parent.parent


def _config(database_url: str) -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "migrations"))
    # ConfigParser treats "%" as interpolation; escape it in passwords.
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(_config(database_url), "head")


def downgrade_to_base(database_url: str) -> None:
    command.downgrade(_config(database_url), "base")
