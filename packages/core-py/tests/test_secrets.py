"""Secret store (decision D10): keys are encrypted at rest, the database holds a reference."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nfactory_core.models import StoredSecret, User, Workspace
from nfactory_core.secrets import SecretKeyMissingError, SecretStore, SecretUnreadableError

pytestmark = pytest.mark.integration

MASTER = "local-master-key-for-tests-only-0123456789"
API_KEY = "sk-live-secret-value-0123456789abcdefgh"


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = User(display_name="Test")
        session.add(owner)
        await session.flush()
        workspace = Workspace(name="Secrets", owner_id=owner.id)
        session.add(workspace)
        await session.flush()
        session.info["workspace_id"] = workspace.id
        yield session
        await session.rollback()
    await engine.dispose()


async def test_a_stored_key_comes_back_and_is_encrypted_at_rest(session: AsyncSession) -> None:
    store = SecretStore(MASTER)

    ref = await store.put(session, session.info["workspace_id"], API_KEY)

    assert ref.startswith("db:")
    assert await store.get(session, ref) == API_KEY
    row = await session.scalar(select(StoredSecret).where(StoredSecret.id == ref[3:]))
    assert row is not None
    assert API_KEY.encode() not in row.ciphertext
    assert API_KEY not in repr(row)


async def test_another_master_key_cannot_read_it(session: AsyncSession) -> None:
    ref = await SecretStore(MASTER).put(session, session.info["workspace_id"], API_KEY)

    with pytest.raises(SecretUnreadableError):
        await SecretStore("another-master-key-0123456789abcdef").get(session, ref)


async def test_deleted_secret_is_gone(session: AsyncSession) -> None:
    store = SecretStore(MASTER)
    ref = await store.put(session, session.info["workspace_id"], API_KEY)

    await store.delete(session, ref)

    assert await store.get(session, ref) is None


async def test_env_reference_reads_the_environment_only_for_that_name(
    session: AsyncSession,
) -> None:
    store = SecretStore(MASTER, env={"OPENAI_API_KEY": API_KEY})

    assert await store.get(session, "env:OPENAI_API_KEY") == API_KEY
    assert await store.get(session, "env:MISSING_KEY") is None


async def test_without_a_master_key_nothing_is_stored(session: AsyncSession) -> None:
    with pytest.raises(SecretKeyMissingError) as caught:
        await SecretStore("").put(session, session.info["workspace_id"], API_KEY)
    assert "NFACTORY_SECRET_KEY" in str(caught.value)
