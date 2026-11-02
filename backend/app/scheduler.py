import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    DiscoveryCandidate,
    DiscoveryConfiguration,
    ProviderConfiguration,
    utc_now,
)
from app.providers import PROVIDER_CATALOG, expand_area_filter
from app.secrets import decrypt_credentials


logger = logging.getLogger(__name__)
DISCOVERY_INTERVAL_SECONDS = 15 * 60


async def run_discovery_cycle(
    session_factory: Callable[[], Session],
    search_provider: Callable[..., Awaitable[list[dict[str, Any]]]],
) -> int:
    with session_factory() as session:
        configuration = session.get(DiscoveryConfiguration, 1)
        providers_configuration = session.get(ProviderConfiguration, 1)
        if configuration is None or not configuration.enabled:
            return 0
        areas = list(configuration.areas)
        genres = list(configuration.genres)
        limit = configuration.result_limit
        enabled_provider_ids = (
            providers_configuration.enabled_provider_ids
            if providers_configuration else ["musicbrainz"]
        )
        encrypted_credentials = (
            providers_configuration.encrypted_credentials
            if providers_configuration else None
        )
    credentials = decrypt_credentials(encrypted_credentials)

    if not areas and not genres:
        logger.info("Scheduled discovery skipped: configure at least one region or genre")
        return 0
    if not enabled_provider_ids:
        logger.info("Scheduled discovery skipped: no providers are enabled")
        return 0

    search_pairs = [
        (expanded_area, genre or None)
        for area in (areas or [""])
        for expanded_area in expand_area_filter(area or None)
        for genre in (genres or [""])
    ]
    queued_count = 0

    provider_names = {provider["id"]: provider["name"] for provider in PROVIDER_CATALOG}
    for area, genre in search_pairs:
        for provider_id in enabled_provider_ids:
            provider_credentials = {
                key.removeprefix(f"{provider_id}."): value
                for key, value in credentials.items()
                if key.startswith(f"{provider_id}.")
            }
            try:
                items = await search_provider(
                    provider_id,
                    query=None,
                    area=area,
                    genre=genre,
                    limit=limit,
                    offset=0,
                    credentials=provider_credentials,
                )
            except (RuntimeError, ValueError, KeyError) as exc:
                logger.warning(
                    "Scheduled %s search failed for area=%r genre=%r: %s",
                    provider_names.get(provider_id, provider_id),
                    area,
                    genre,
                    exc,
                )
                continue

            with session_factory() as session:
                for item in items:
                    item_provider_id = item["provider_id"]
                    candidate = session.scalar(
                        select(DiscoveryCandidate).where(
                            DiscoveryCandidate.provider_id == item_provider_id,
                            DiscoveryCandidate.external_id == item["external_id"],
                        )
                    )
                    if candidate is None:
                        candidate = DiscoveryCandidate(
                            provider_id=item_provider_id,
                            external_id=item["external_id"],
                            name=item["name"],
                            country=item["country"],
                            area=item["area"],
                            artist_type=item["type"],
                            disambiguation=item["disambiguation"],
                            tags=item["tags"],
                            source_url=item["source_url"],
                            last_query_area=area,
                            last_query_genre=genre,
                        )
                        session.add(candidate)
                        queued_count += 1
                    else:
                        candidate.name = item["name"]
                        candidate.country = item["country"]
                        candidate.area = item["area"]
                        candidate.artist_type = item["type"]
                        candidate.disambiguation = item["disambiguation"]
                        candidate.tags = item["tags"]
                        candidate.last_query_area = area
                        candidate.last_query_genre = genre
                        candidate.last_seen_at = utc_now()
                session.commit()

    logger.info(
        "Scheduled multi-provider discovery completed: %d filter combinations across %d providers, %d new candidates",
        len(search_pairs),
        len(enabled_provider_ids),
        queued_count,
    )
    return queued_count


async def run_discovery_scheduler(
    session_factory: Callable[[], Session],
    search_provider: Callable[..., Awaitable[list[dict[str, Any]]]],
    wakeup: asyncio.Event,
) -> None:
    while True:
        cycle_started = asyncio.get_running_loop().time()
        try:
            await run_discovery_cycle(session_factory, search_provider)
        except (SQLAlchemyError, RuntimeError):
            logger.exception("Scheduled discovery cycle failed")

        timeout = max(
            0,
            DISCOVERY_INTERVAL_SECONDS - (asyncio.get_running_loop().time() - cycle_started),
        )
        try:
            await asyncio.wait_for(wakeup.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        wakeup.clear()
