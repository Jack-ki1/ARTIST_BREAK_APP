"""Autonomous source collection worker. Run once per shared database."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import SessionLocal, create_database_tables
from app.main import _run_discovery, _settings, collect_evidence
from app.models import Artist, WorkerHeartbeat, utc_now
from app.schemas import DiscoveryRunRequest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _heartbeat(db, state: str, error: str | None = None) -> WorkerHeartbeat:
    row = db.get(WorkerHeartbeat, 1)
    if row is None:
        row = WorkerHeartbeat(id=1, state=state, last_seen_at=utc_now())
        db.add(row)
    row.state = state
    row.last_seen_at = utc_now()
    if error is not None:
        row.last_error = error[:2000]
    db.commit()
    return row


async def run_worker() -> None:
    create_database_tables()
    logger.info("Breakout Radar autonomous collection worker started")
    while True:
        try:
            with SessionLocal() as db:
                settings = _settings(db)
                now = utc_now()
                heartbeat = db.get(WorkerHeartbeat, 1)
                if heartbeat is None:
                    heartbeat = WorkerHeartbeat(id=1, state="starting", last_seen_at=now)
                    db.add(heartbeat)
                    db.commit()
                heartbeat.last_seen_at = now
                discovery_interval = max(1, min(168, int(settings.get("auto_discovery_interval_hours", 6))))
                evidence_interval = max(1, min(168, int(settings.get("auto_evidence_interval_hours", 24))))
                discovery_due = bool(settings.get("auto_discovery_enabled", True)) and (
                    _utc(heartbeat.last_discovery_at) is None or now - _utc(heartbeat.last_discovery_at) >= timedelta(hours=discovery_interval)
                )
                evidence_due = bool(settings.get("auto_evidence_enabled", True)) and (
                    _utc(heartbeat.last_evidence_at) is None or now - _utc(heartbeat.last_evidence_at) >= timedelta(hours=evidence_interval)
                )
                if discovery_due:
                    _heartbeat(db, "discovering")
                    try:
                        result = await _run_discovery(
                            DiscoveryRunRequest(query=None, limit=min(25, max(1, int(settings.get("analysis_batch_size", 10))))),
                            db, run_kind="scheduled",
                        )
                        heartbeat = db.get(WorkerHeartbeat, 1)
                        heartbeat.last_discovery_at = utc_now()
                        heartbeat.last_error = None if result.get("status") in {"completed", "partial"} else "Scheduled discovery returned a non-complete status"
                        logger.info("Scheduled discovery %s: %s candidates across %s sources", result.get("run_id"), result.get("candidates_found"), len(result.get("sources_attempted", [])))
                        db.commit()
                    except Exception as exc:
                        logger.exception("Scheduled discovery failed")
                        heartbeat = db.get(WorkerHeartbeat, 1)
                        heartbeat.last_discovery_at = utc_now()
                        heartbeat.last_error = f"Discovery: {exc}"[:2000]
                        db.commit()
                if evidence_due:
                    _heartbeat(db, "collecting_evidence")
                    try:
                        batch_size = min(50, max(1, int(settings.get("evidence_batch_size", 8))))
                        artist_ids = db.scalars(select(Artist.id).order_by(Artist.updated_at.desc()).limit(batch_size)).all()
                        evidence_total = 0
                        for artist_id in artist_ids:
                            try:
                                result = await collect_evidence(artist_id, db)
                                evidence_total += int(result.get("evidence_saved", 0))
                            except Exception as exc:
                                logger.warning("Evidence refresh for %s failed: %s", artist_id, exc)
                        heartbeat = db.get(WorkerHeartbeat, 1)
                        heartbeat.last_evidence_at = utc_now()
                        logger.info("Evidence refresh complete: %s artists processed, %s new links", len(artist_ids), evidence_total)
                        db.commit()
                    except Exception as exc:
                        logger.exception("Scheduled evidence refresh failed")
                        heartbeat = db.get(WorkerHeartbeat, 1)
                        heartbeat.last_error = f"Evidence refresh: {exc}"[:2000]
                        heartbeat.last_evidence_at = utc_now()
                        db.commit()
                heartbeat = db.get(WorkerHeartbeat, 1)
                heartbeat.state = "idle"
                heartbeat.last_seen_at = utc_now()
                if settings.get("auto_discovery_enabled", True):
                    last = _utc(heartbeat.last_discovery_at)
                    heartbeat.next_discovery_at = (last or utc_now()) + timedelta(hours=discovery_interval)
                else:
                    heartbeat.next_discovery_at = None
                db.commit()
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Worker cycle failed")
            try:
                with SessionLocal() as db:
                    _heartbeat(db, "error", str(exc))
            except Exception:
                logger.exception("Could not persist worker error heartbeat")
            await asyncio.sleep(30)


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("A&R worker stopped")
