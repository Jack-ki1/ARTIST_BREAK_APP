import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db
from app.models import DiscoveryConfiguration
from app.providers import search_enabled_providers
from app.quotas import claim_provider_call
from app.providers import provider_status
from app.scheduler import run_discovery_cycle


@pytest.fixture
def client(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    test_sessions = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with test_sessions() as session:
            yield session

    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main, "SessionLocal", test_sessions)
    monkeypatch.setattr(main, "create_database_tables", lambda: Base.metadata.create_all(test_engine))

    async def disable_background_scheduler(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "run_discovery_scheduler", disable_background_scheduler)
    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    test_engine.dispose()


def test_provider_status_respects_an_explicit_empty_selection():
    providers = provider_status([])
    assert providers
    assert not any(provider["enabled"] for provider in providers)


def test_youtube_daily_request_budget_is_persisted_and_enforced(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_SEARCH_DAILY_BUDGET", "2")

    assert claim_provider_call(main.SessionLocal, "youtube") is True
    assert claim_provider_call(main.SessionLocal, "youtube") is True
    assert claim_provider_call(main.SessionLocal, "youtube") is False


def test_provider_search_retries_rate_limited_requests():
    from app.providers import _get_json

    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": "rate limited"},
                request=request,
            )
        return httpx.Response(200, json={"artists": []}, request=request)

    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await _get_json(http, "https://provider.example/search", params={})

    payload = asyncio.run(execute())
    assert payload == {"artists": []}
    assert len(requests) == 2


def test_provider_aggregation_batches_filters_and_deduplicates(monkeypatch):
    from app import providers

    calls = []

    async def fake_search(provider_id, **filters):
        calls.append((provider_id, filters["area"], filters["genre"]))
        return [{
            "id": "musicbrainz:shared-artist",
            "external_id": "shared-artist",
            "provider_id": provider_id,
            "name": "Shared Artist",
            "source_url": "https://musicbrainz.org/artist/shared-artist",
            "tags": [],
        }]

    monkeypatch.setattr(providers, "search_provider", fake_search)
    result = asyncio.run(search_enabled_providers(
        ["musicbrainz"],
        {},
        query=None,
        area=None,
        genre=None,
        areas=["Kenya", "Ghana"],
        genres=["Afrobeats", "Highlife"],
        limit=5,
    ))

    assert len(calls) == 4
    assert result["count"] == 1
    assert result["items"][0]["id"] == "musicbrainz:shared-artist"


def test_scheduler_skips_youtube_after_daily_budget_is_exhausted(client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_SEARCH_DAILY_BUDGET", "1")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PROVIDER_SECRETS_KEY", Fernet.generate_key().decode("ascii"))
    assert client.put(
        "/api/providers",
        json={
            "enabled_provider_ids": ["youtube"],
            "credential_updates": {"youtube": {"api_key": "test-youtube-key"}},
        },
    ).status_code == 200
    assert client.put(
        "/api/discovery/settings",
        json={"areas": ["Kenya"], "genres": [], "enabled": True},
    ).status_code == 200

    assert claim_provider_call(main.SessionLocal, "youtube") is True
    searches = []

    async def fake_search(provider_id, **filters):
        searches.append(provider_id)
        return []

    assert asyncio.run(run_discovery_cycle(main.SessionLocal, fake_search)) == 0
    assert searches == []


def test_health_discloses_authentication_status_and_configured_sources(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "authentication": "disabled",
        "configured_data_providers": ["musicbrainz"],
    }


def test_provider_status_is_explicit_about_integrations(client):
    providers = client.get("/api/providers").json()

    assert len(providers) >= 15
    status_by_id = {provider["id"]: provider for provider in providers}
    assert status_by_id["musicbrainz"]["configured"] is True
    assert status_by_id["musicbrainz"]["enabled"] is True
    assert status_by_id["spotify"]["configured"] is False
    assert status_by_id["spotify"]["fields"][0]["key"] == "client_id"


def test_provider_settings_encrypt_credentials_and_never_return_them(client, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("PROVIDER_SECRETS_KEY", Fernet.generate_key().decode("ascii"))
    response = client.put(
        "/api/providers",
        json={
            "enabled_provider_ids": ["musicbrainz", "youtube"],
            "credential_updates": {"youtube": {"api_key": "youtube-test-secret"}},
        },
    )

    assert response.status_code == 200
    status_by_id = {provider["id"]: provider for provider in response.json()}
    assert status_by_id["youtube"]["configured"] is True
    assert status_by_id["youtube"]["enabled"] is True
    assert "youtube-test-secret" not in response.text
    assert "api_key" in status_by_id["youtube"]["configured_fields"]

    listed = client.get("/api/providers")
    assert listed.status_code == 200
    assert "youtube-test-secret" not in listed.text


def test_provider_settings_reject_unknown_provider_and_require_encryption_key(client, monkeypatch):
    monkeypatch.delenv("PROVIDER_SECRETS_KEY", raising=False)
    assert client.put(
        "/api/providers",
        json={"enabled_provider_ids": ["made_up_provider"]},
    ).status_code == 422
    response = client.put(
        "/api/providers",
        json={
            "enabled_provider_ids": ["youtube"],
            "credential_updates": {"youtube": {"api_key": "secret"}},
        },
    )
    assert response.status_code == 503
    assert "PROVIDER_SECRETS_KEY" in response.json()["detail"]


def test_search_reports_selected_provider_missing_credentials(client):
    settings = client.put(
        "/api/providers",
        json={"enabled_provider_ids": ["spotify"]},
    )
    assert settings.status_code == 200
    response = client.get("/api/discovery/search?query=Example+Artist")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["errors"] == [
        "Spotify: missing credentials (client_id, client_secret)"
    ]


def test_region_search_expands_to_country_level_provider_queries(client, monkeypatch):
    from app import providers

    searched_areas = []

    async def fake_search(provider_id, **filters):
        searched_areas.append(filters["area"])
        return []

    monkeypatch.setattr(providers, "search_provider", fake_search)
    response = client.get("/api/discovery/search?area=East+Africa")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert len(searched_areas) == 18
    assert "Kenya" in searched_areas
    assert "Uganda" in searched_areas


def test_authenticated_provider_searches_send_bearer_tokens(monkeypatch):
    from app import providers

    requests = []

    async def fake_get_json(client, url, *, params, headers=None):
        requests.append(headers or {})
        return {
            "artists": {"items": []},
            "results": {"artists": {"data": []}},
            "response": {"hits": []},
        }

    async def fake_spotify_token(client, credentials):
        return "spotify-token"

    monkeypatch.setattr(providers, "_get_json", fake_get_json)
    monkeypatch.setattr(providers, "_spotify_token", fake_spotify_token)
    for provider_id, credentials, expected_header in (
        ("spotify", {"client_id": "id", "client_secret": "secret"}, "Bearer spotify-token"),
        ("apple_music", {"developer_token": "apple-token"}, "Bearer apple-token"),
        ("genius", {"access_token": "genius-token"}, "Bearer genius-token"),
    ):
        asyncio.run(providers.search_provider(
            provider_id,
            query="Example Artist",
            area=None,
            genre=None,
            limit=5,
            credentials=credentials,
        ))
        assert requests[-1]["Authorization"] == expected_header


def test_discovery_search_requires_at_least_one_filter(client):
    response = client.get("/api/discovery/search")

    assert response.status_code == 422
    assert "artist, region, or genre" in response.json()["detail"]


def test_discovery_search_returns_attributed_musicbrainz_results(client, monkeypatch):
    calls = {}

    async def fake_search(enabled_provider_ids, credentials, **filters):
        calls.update(filters)
        calls["enabled_provider_ids"] = enabled_provider_ids
        calls["credentials"] = credentials
        return {
            "items": [
                {
                    "id": "musicbrainz:musicbrainz-artist-id",
                    "external_id": "musicbrainz-artist-id",
                    "provider_id": "musicbrainz",
                    "name": "Artist from Live Catalog",
                    "country": "KE",
                    "area": "Kenya",
                    "type": "Person",
                    "disambiguation": None,
                    "tags": ["afrobeats"],
                    "source_url": "https://musicbrainz.org/artist/musicbrainz-artist-id",
                }
            ],
            "count": 1,
            "offset": 0,
            "errors": [],
        }

    monkeypatch.setattr(main, "search_enabled_providers", fake_search)
    response = client.get("/api/discovery/search?area=Kenya&genre=Afrobeats&limit=5")

    assert response.status_code == 200
    assert calls == {
        "enabled_provider_ids": ["musicbrainz"],
        "credentials": {},
        "query": None,
        "area": "Kenya",
        "genre": "Afrobeats",
        "limit": 5,
        "offset": 0,
    }
    assert response.json()["items"][0]["source_url"].startswith("https://musicbrainz.org/artist/")
    assert response.json()["items"][0]["tags"] == ["afrobeats"]


def test_discovery_settings_persist_multiple_regions_and_genres(client):
    settings = client.get("/api/discovery/settings")
    assert settings.status_code == 200
    assert settings.json()["interval_seconds"] == 900
    assert settings.json()["areas"] == []

    updated = client.put(
        "/api/discovery/settings",
        json={
            "areas": [" Kenya ", "Ghana"],
            "genres": ["Afrobeats", "Alternative R&B"],
            "result_limit": 5,
            "enabled": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["areas"] == ["Kenya", "Ghana"]
    assert updated.json()["genres"] == ["Afrobeats", "Alternative R&B"]
    assert updated.json()["enabled"] is False
    assert client.get("/api/discovery/settings").json()["result_limit"] == 5


def test_scheduled_discovery_waits_for_a_region_or_genre(client):
    searches = []

    async def fake_search(provider_id, **filters):
        searches.append((provider_id, filters))
        return []

    assert asyncio.run(run_discovery_cycle(main.SessionLocal, fake_search)) == 0
    assert searches == []


def test_scheduled_discovery_expands_named_regions_to_all_countries(client):
    settings = client.put(
        "/api/discovery/settings",
        json={
            "areas": ["East Africa", "Central Africa"],
            "genres": [],
            "enabled": False,
        },
    )
    assert settings.status_code == 200

    with main.SessionLocal() as session:
        configuration = session.get(DiscoveryConfiguration, 1)
        configuration.enabled = True
        session.commit()

    searches = []

    async def fake_search(provider_id, **filters):
        searches.append(filters["area"])
        return []

    assert asyncio.run(run_discovery_cycle(main.SessionLocal, fake_search)) == 0
    assert len(searches) == 27
    assert "Kenya" in searches
    assert "Uganda" in searches
    assert "Cameroon" in searches
    assert "Democratic Republic of the Congo" in searches


def test_scheduled_discovery_queues_unique_candidates_for_every_filter_combination(client):
    response = client.put(
        "/api/discovery/settings",
        json={
            "areas": ["Kenya", "Ghana"],
            "genres": ["Afrobeats", "Alternative R&B"],
            "result_limit": 5,
            "enabled": False,
        },
    )
    assert response.status_code == 200

    with main.SessionLocal() as session:
        configuration = session.get(DiscoveryConfiguration, 1)
        configuration.enabled = True
        session.commit()

    searches = []

    async def fake_search(provider_id, **filters):
        searches.append(filters)
        return [
            {
                "id": f"{provider_id}:shared-id",
                "external_id": "shared-id",
                "provider_id": provider_id,
                "name": "Queued Artist",
                "country": "KE",
                "area": "Nairobi",
                "type": "Person",
                "disambiguation": None,
                "tags": ["afrobeats"],
                "source_url": f"https://{provider_id}.example/artist/shared-id",
            }
        ]

    assert asyncio.run(run_discovery_cycle(main.SessionLocal, fake_search)) == 1
    assert len(searches) == 4
    assert {(item["area"], item["genre"]) for item in searches} == {
        ("Kenya", "Afrobeats"),
        ("Kenya", "Alternative R&B"),
        ("Ghana", "Afrobeats"),
        ("Ghana", "Alternative R&B"),
    }

    queue = client.get("/api/discovery/queue")
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    candidate_id = queue.json()["items"][0]["id"]

    reviewed = client.patch(
        f"/api/discovery/queue/{candidate_id}",
        json={"status": "accepted"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "accepted"
    assert client.get("/api/discovery/queue").json()["total"] == 0
    assert client.get("/api/artists").json()["items"][0]["source_name"] == "musicbrainz"
    assert client.patch(
        f"/api/discovery/queue/{candidate_id}",
        json={"status": "dismissed"},
    ).status_code == 409


def test_artist_collection_starts_empty_and_creates_only_submitted_identity(client):
    assert client.get("/api/artists").json()["total"] == 0

    response = client.post(
        "/api/artists",
        json={
            "name": "User Submitted Artist",
            "country": "GH",
            "city": "Accra",
            "genre": "Highlife",
            "source_name": "Authorized intake form",
            "source_url": "https://example.org/artist",
        },
    )

    assert response.status_code == 201
    artist = response.json()
    assert artist["name"] == "User Submitted Artist"
    assert artist["source_name"] == "Authorized intake form"
    assert "metrics" not in artist
    assert client.get("/api/artists").json()["total"] == 1


def test_artist_validation_rejects_blank_names_and_unknown_metric_fields(client):
    assert client.post("/api/artists", json={"name": "   "}).status_code == 422
    assert client.post(
        "/api/artists",
        json={"name": "Identity Only", "audience": 1000, "score": 85},
    ).status_code == 422
    assert client.post(
        "/api/artists",
        json={"name": "Bad Source", "source_url": "not-a-url"},
    ).status_code == 422


def test_artist_update_and_delete(client):
    created = client.post("/api/artists", json={"name": "First Name"}).json()
    artist_id = created["id"]

    updated = client.patch(f"/api/artists/{artist_id}", json={"name": "Updated Name"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Name"
    assert client.patch(f"/api/artists/{artist_id}", json={}).status_code == 400
    assert client.delete(f"/api/artists/{artist_id}").status_code == 204
    assert client.get(f"/api/artists/{artist_id}").status_code == 404


def test_artist_list_paginates_and_validates_limits(client):
    for name in ("Zulu", "Alpha", "Mango"):
        assert client.post("/api/artists", json={"name": name}).status_code == 201

    page = client.get("/api/artists?limit=2&offset=1")
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert [item["name"] for item in page.json()["items"]] == ["Mango", "Zulu"]
    assert client.get("/api/artists?limit=101").status_code == 422
