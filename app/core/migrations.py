import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

ALEMBIC_DIRECTORY = Path(__file__).resolve().parents[2] / "alembic"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIRECTORY))
    return config


async def run_migrations() -> None:
    logger.info("Applying pending database migrations")
    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    logger.info("Database schema is up to date")
