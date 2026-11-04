"""Optional scheduled discovery worker.

Run separately from Uvicorn:
    python -m app.worker

The API remains responsive while this process executes discovery scans. One
worker should be run per database until a distributed lock service is deployed.
"""
from __future__ import annotations

import asyncio
import logging
import os

from app.database import SessionLocal, create_database_tables
from app.main import _settings, run_discovery
from app.schemas import DiscoveryRunRequest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


async def run_worker() -> None:
    create_database_tables()
    logger.info("A&R discovery worker started")
    while True:
        try:
            with SessionLocal() as db:
                settings = _settings(db)
                enabled = bool(settings.get("auto_discovery_enabled", False))
                interval = max(1, min(168, int(settings.get("auto_discovery_interval_hours", 24))))
                if enabled:
                    logger.info("Starting scheduled A&R discovery run")
                    try:
                        result = await run_discovery(
                            DiscoveryRunRequest(query=None, limit=min(25, max(1, int(settings.get("analysis_batch_size", 10))))),
                            db,
                        )
                        logger.info(
                            "Scheduled run %s completed with status=%s candidates=%s",
                            result.get("run_id"), result.get("status"), result.get("candidates_found"),
                        )
                    except Exception:
                        logger.exception("Scheduled A&R discovery run failed")
                else:
                    interval = 1
                    logger.debug("Scheduled discovery is disabled in Settings")
            await asyncio.sleep(interval * 60 * 60)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Discovery worker cycle failed")
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("A&R discovery worker stopped")
