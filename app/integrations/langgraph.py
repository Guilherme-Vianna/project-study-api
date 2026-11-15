import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.exceptions import QuestionGeneratorUnavailableError

logger = logging.getLogger(__name__)

CHECKPOINT_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)

_pool: AsyncConnectionPool | None = None
_saver: AsyncPostgresSaver | None = None


def checkpoint_conninfo(database_url: str) -> str:
    url = make_url(database_url).set(drivername="postgresql")
    query = dict(url.query)
    ssl = query.pop("ssl", None)
    if ssl is not None:
        query["sslmode"] = ssl
    return url.set(query=query).render_as_string(hide_password=False)


async def open_checkpointer(*, setup: bool) -> None:
    global _pool, _saver
    if _saver is not None or not (settings.llm_model or settings.llm_fallback_model):
        return
    pool = AsyncConnectionPool(
        checkpoint_conninfo(settings.database_url),
        open=False,
        max_size=settings.db_pool_size,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    try:
        await pool.open()
        saver = AsyncPostgresSaver(pool)
        if setup:
            await saver.setup()
    except Exception:
        logger.exception("Question generation checkpointer is unavailable")
        await pool.close()
        return
    _pool, _saver = pool, saver


async def close_checkpointer() -> None:
    global _pool, _saver
    if _pool is not None:
        await _pool.close()
    _pool, _saver = None, None


def get_checkpointer() -> BaseCheckpointSaver:
    if _saver is None:
        raise QuestionGeneratorUnavailableError("Question generation storage is not available")
    return _saver
