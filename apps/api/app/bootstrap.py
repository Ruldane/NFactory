"""One-shot startup job (Compose `migrate` service): migrate, create local identity,
seed demo data when demo mode is on. Safe to run any number of times.

Usage: python -m app.bootstrap
"""

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import Database
from app.demo import seed_demo
from app.migrations_runner import upgrade_to_head
from app.services.identity import ensure_local_identity
from nfactory_core.config import get_settings

log = logging.getLogger("nfactory.bootstrap")


async def prepare_data(sessions: async_sessionmaker[AsyncSession], *, demo: bool) -> None:
    async with sessions() as session:
        await ensure_local_identity(session)
        if demo:
            await seed_demo(session)


async def _run() -> None:
    settings = get_settings()
    log.info("Applying migrations")
    upgrade_to_head(settings.database_url)
    database = Database(settings.database_url)
    try:
        await prepare_data(database.sessions, demo=settings.nfactory_demo_mode)
    finally:
        await database.dispose()
    log.info("Bootstrap done (demo data: %s)", settings.nfactory_demo_mode)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if sys.platform == "win32":  # psycopg async needs a selector loop on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_run())


if __name__ == "__main__":
    main()
