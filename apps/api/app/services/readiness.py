"""Dependency checks behind GET /ready. Each check reports ok/error without leaking secrets."""

import asyncio
from typing import Any

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Check = dict[str, Any]


async def check_all(session: AsyncSession, redis_url: str) -> dict[str, Check]:
    database = await _check_database(session)
    pgvector = await _check_pgvector(session) if database["ok"] else _fail("database down")
    return {"database": database, "pgvector": pgvector, "redis": await _check_redis(redis_url)}


def _fail(reason: str) -> Check:
    return {"ok": False, "error": reason}


async def _check_database(session: AsyncSession) -> Check:
    try:
        await session.execute(text("select 1"))
    except Exception as exc:  # report, never raise: this is a health probe
        return _fail(type(exc).__name__)
    return {"ok": True}


async def _check_pgvector(session: AsyncSession) -> Check:
    version = await session.scalar(
        text("select extversion from pg_extension where extname = 'vector'")
    )
    return {"ok": True, "version": version} if version else _fail("extension missing")


async def _check_redis(url: str) -> Check:
    client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        async with asyncio.timeout(2):
            await client.ping()
    except Exception as exc:
        return _fail(type(exc).__name__)
    finally:
        await client.aclose()
    return {"ok": True}
