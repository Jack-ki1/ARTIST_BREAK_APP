"""Provider request budgets backed by a durable database ledger."""

from datetime import datetime, timezone
import logging
import os
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ProviderDailyUsage

logger = logging.getLogger(__name__)

# Leave a safety margin below YouTube's standard 100 search.list calls/day.
# Operators with a different approved quota can tune this through the environment.
DEFAULT_YOUTUBE_DAILY_BUDGET = 80


def daily_provider_budget(provider_id: str) -> int | None:
    if provider_id != "youtube":
        return None
    try:
        return max(0, int(os.getenv(
            "YOUTUBE_SEARCH_DAILY_BUDGET",
            str(DEFAULT_YOUTUBE_DAILY_BUDGET),
        )))
    except ValueError:
        logger.warning(
            "Invalid YOUTUBE_SEARCH_DAILY_BUDGET; using default %s",
            DEFAULT_YOUTUBE_DAILY_BUDGET,
        )
        return DEFAULT_YOUTUBE_DAILY_BUDGET


def claim_provider_call(
    session_factory: Callable[[], Session],
    provider_id: str,
    now: datetime | None = None,
) -> bool:
    """Atomically reserve one request where a daily budget is configured.

    Requests are counted before transmission because failed and invalid YouTube
    search requests can still consume quota. A failed ledger write fails closed.
    """
    budget = daily_provider_budget(provider_id)
    if budget is None:
        return True

    request_time = now or datetime.now(timezone.utc)
    usage_date = request_time.astimezone(timezone.utc).date().isoformat()

    try:
        with session_factory() as session:
            usage = session.scalar(
                select(ProviderDailyUsage)
                .where(
                    ProviderDailyUsage.provider_id == provider_id,
                    ProviderDailyUsage.usage_date == usage_date,
                )
                .with_for_update()
            )
            if usage is None:
                usage = ProviderDailyUsage(
                    provider_id=provider_id,
                    usage_date=usage_date,
                    request_count=0,
                )
                session.add(usage)
                session.flush()

            if usage.request_count >= budget:
                return False

            usage.request_count += 1
            session.commit()
            return True
    except IntegrityError:
        # Another worker created the daily row at the same time. Fail closed;
        # the next request can retry against the now-existing row.
        logger.warning("Concurrent quota-ledger initialisation for %s", provider_id)
        return False
    except SQLAlchemyError:
        logger.exception("Could not reserve daily request budget for %s", provider_id)
        return False
