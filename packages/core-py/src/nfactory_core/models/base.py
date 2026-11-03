"""Declarative base and column helpers shared by every table.

Conventions:
- Prefixed text primary keys (`proj_…`, `run_…`), see `nfactory_core.ids`.
- Timezone-aware timestamps, always UTC.
- `dict`/`list` annotations map to JSONB.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nfactory_core.ids import new_id


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB, list[Any]: JSONB}


def id_column(prefix: str) -> Mapped[str]:
    return mapped_column(String(32), primary_key=True, default=lambda: new_id(prefix))


def created_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def optional_timestamp() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True))
