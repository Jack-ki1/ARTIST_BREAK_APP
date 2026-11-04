import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db
from app.models import ArtistCandidate, SourceConfiguration, SourceDailyUsage, WorkerHeartbeat
from app.source_catalog import source_catalog, source_ids
from app.scoring import artistic_overall, discovery_index, recommendation


@pytest.fixture
def client(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    sessions = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_db():
        with sessions() as session:
            yield session

    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(main, "create_database_tables", lambda: Base.metadata.create_all(test_engine))
    main.app.dependency_overrides[get_db] = override_db
    with TestClient(main.app) as test_client:
        yield test_client, sessions
    main.app.dependency_overrides.clear()
    test_engine.dispose()


def test_health_and_73_source_registry(client):
    http, _sessions = client
    response = http.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["source_count"] == 73

    sources = http.get("/api/sources").json()
    assert len(sources["items"]) == 73
    assert len(source_ids()) == 73
    assert len({item["id"] for item in sources["items"]}) == 73

    by_id = {item["id"]: item for item in sources["items"]}
    assert by_id["musicbrainz"]["status"] == "ready"
    assert by_id["tiktok_research"]["status"] == "disabled"
    assert by_id["chartmetric"]["access"] == "licensed"
    assert by_id["instagram_graph"]["access"] == "oauth"
    assert by_id["gdelt"]["capability"] == "evidence_enrichment"


def test_provider_credentials_are_encrypted_and_not_returned(client, monkeypatch):
    from cryptography.fernet import Fernet

    http, sessions = client
    monkeypatch.setenv("PROVIDER_SECRETS_KEY", Fernet.generate_key().decode("ascii"))
    response = http.put("/api/sources", json={
        "enabled_source_ids": ["youtube"],
        "credential_updates": {"youtube": {"api_key": "test-api-key-never-return"}},
    })
    assert response.status_code == 200
    payload = response.json()
    youtube = next(item for item in payload["items"] if item["id"] == "youtube")
    assert youtube["status"] == "ready"
    assert "test-api-key-never-return" not in response.text

    with sessions() as session:
        config = session.get(SourceConfiguration, 1)
        assert config.encrypted_credentials
        assert "test-api-key-never-return" not in config.encrypted_credentials


def test_settings_store_custom_discovery_seeds(client):
    http, _sessions = client
    response = http.put("/api/settings", json={"config": {
        "discovery_seeds": ["Kenya alternative", "Tanzania Bongo Flava"],
        "region_focus": "east",
        "artistic_share": 70,
    }})
    assert response.status_code == 200
    saved = http.get("/api/settings").json()["config"]
    assert saved["discovery_seeds"] == ["Kenya alternative", "Tanzania Bongo Flava"]
    assert saved["artistic_share"] == 70


def test_youtube_quota_follows_midnight_pacific_in_pst_and_pdt(client, monkeypatch):
    _http, sessions = client
    monkeypatch.setenv("YOUTUBE_SEARCH_DAILY_BUDGET", "1")
    with sessions() as session:
        # 07:59 UTC is 23:59 PST; the quota resets at 08:00 UTC in winter.
        before = datetime(2026, 1, 2, 7, 59, tzinfo=timezone.utc)
        after = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
        assert main._claim_source_request(session, "youtube", before)
        assert not main._claim_source_request(session, "youtube", before)
        assert main._claim_source_request(session, "youtube", after)

        # 06:59 UTC is 23:59 PDT; reset at 07:00 UTC in summer.
        summer_before = datetime(2026, 7, 2, 6, 59, tzinfo=timezone.utc)
        summer_after = datetime(2026, 7, 2, 7, 0, tzinfo=timezone.utc)
        assert main._claim_source_request(session, "youtube", summer_before)
        assert main._claim_source_request(session, "youtube", summer_after)


def test_discovery_groups_cross_source_results_and_accepts_artist(client, monkeypatch):
    http, _sessions = client
    response = http.put("/api/sources", json={
        "enabled_source_ids": ["itunes", "musicbrainz"],
    })
    assert response.status_code == 200

    async def fake_search(source_id, query, credentials, **kwargs):
        return [{
            "provider_id": source_id,
            "external_id": f"{source_id}-artist-1",
            "name": "Nia K",
            "source_url": f"https://{source_id}.example/artists/nia-k",
            "country": "KE",
            "city": "Nairobi",
            "genres": ["Alternative R&B"],
            "bio": "Independent Nairobi vocalist.",
            "image_url": None,
            "metrics": {"fans": 120, "albums": 2} if source_id == "itunes" else {},
            "context": {"query": query},
        }]

    monkeypatch.setattr(main, "search_identity_source", fake_search)
    result = http.post("/api/discovery/run", json={
        "query": "Nia K",
        "source_ids": ["itunes", "musicbrainz"],
        "country": "Kenya",
        "limit": 10,
    })
    assert result.status_code == 200, result.text
    run = result.json()
    assert run["status"] == "completed"
    assert run["candidates_found"] == 1

    candidates = http.get("/api/discovery/candidates").json()
    assert candidates["total"] == 1
    candidate = candidates["items"][0]
    assert candidate["name"] == "Nia K"
    assert candidate["source_count"] == 2

    accepted = http.post(
        f"/api/discovery/candidates/{candidate['candidate_ids'][0]}/review",
        json={"action": "accept", "note": "Identity cross-checked against two catalogues."},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["linked_sources"] == 2

    artists = http.get("/api/artists").json()
    assert artists["total"] == 1
    artist = artists["items"][0]
    assert artist["name"] == "Nia K"
    assert artist["discovery_confidence"] > 0

    detail = http.get(f"/api/artists/{artist['id']}").json()
    assert len(detail["identities"]) == 2
    assert len(detail["observations"]) == 2

    # A later scan appends to the accepted artist's source-specific history.
    second = http.post("/api/discovery/run", json={
        "query": "Nia K", "source_ids": ["itunes", "musicbrainz"], "limit": 10,
    })
    assert second.status_code == 200
    assert second.json()["candidates_found"] == 0
    refreshed = http.get(f"/api/artists/{artist['id']}").json()
    assert len(refreshed["observations"]) == 4


def test_artistic_review_is_separate_from_discovery_and_recommendation(client):
    http, _sessions = client
    created = http.post("/api/artists", json={
        "name": "Malaika",
        "country": "KE",
        "city": "Nairobi",
        "genres": ["Afropop", "R&B"],
    })
    assert created.status_code == 201, created.text
    artist_id = created.json()["id"]

    review = http.post(f"/api/artists/{artist_id}/reviews", json={
        "reviewer": "A&R Team",
        "track_title": "City Lights",
        "track_url": "https://example.com/track",
        "scores": {
            "songwriting": 9, "vocals": 8, "melody": 8,
            "production": 7, "originality": 8, "performance": 7, "identity": 9,
        },
        "verdict": "strong",
        "notes": "Strong writing and a distinctive vocal identity.",
        "strengths": ["Hook writing", "Vocal tone"],
        "risks": ["Need live performance assessment"],
        "evidence": [],
    })
    assert review.status_code == 201, review.text
    assert review.json()["overall"] >= 70

    detail = http.get(f"/api/artists/{artist_id}").json()
    assert detail["artistic_score"] == review.json()["overall"]
    assert detail["review_status"] == "reviewed"
    assert detail["recommendation_tier"] in {"watch", "meet", "pursue", "hold"}

    decision = http.post(f"/api/artists/{artist_id}/decisions", json={
        "decision": "watch", "owner": "A&R Team", "note": "Revisit after a live set.",
    })
    assert decision.status_code == 201
    assert http.get("/api/recommendations").json()["total"] == 1


def test_evidence_collector_stores_source_attributed_references(client, monkeypatch):
    http, _sessions = client
    created = http.post("/api/artists", json={"name": "Sauti Sample", "country": "TZ"})
    artist_id = created.json()["id"]
    http.put("/api/sources", json={"enabled_source_ids": ["gdelt"]})

    async def fake_evidence(source_id, artist_name, credentials, **kwargs):
        return [{
            "source_id": source_id,
            "evidence_type": "press",
            "title": f"{artist_name} — new single",
            "summary": "Source-linked editorial mention.",
            "url": "https://news.example/artist-single",
            "published_at": None,
            "context": {"domain": "news.example"},
        }]

    monkeypatch.setattr(main, "collect_artist_evidence", fake_evidence)
    response = http.post(f"/api/artists/{artist_id}/collect-evidence")
    assert response.status_code == 200, response.text
    assert response.json()["evidence_saved"] == 1
    detail = http.get(f"/api/artists/{artist_id}").json()
    assert detail["evidence"][0]["source_id"] == "gdelt"


def test_scoring_does_not_turn_missing_reviews_into_signing_recommendations():
    result = recommendation(95, None)
    assert result["tier"] == "hold"
    assert "No completed artistic review" in result["reason"]

    artistic = artistic_overall({"songwriting": 9, "vocals": 8})
    assert artistic is not None
    assert artistic > 80

    score = discovery_index({
        "momentum": None,
        "independent_source_count": 3,
        "release_activity": None,
        "live_activity": None,
        "search_interest": None,
        "catalogue_headroom": None,
    })
    assert score["score"] > 0
    assert score["confidence"] < 100


def test_automation_status_reports_worker_heartbeat_and_autonomous_defaults(client):
    http, sessions = client
    status = http.get("/api/automation/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["discovery_enabled"] is True
    assert payload["evidence_enabled"] is True
    assert payload["interval_hours"] == 6
    assert payload["worker_online"] is False

    from datetime import datetime, timezone
    with sessions() as session:
        session.add(WorkerHeartbeat(id=1, state="idle", last_seen_at=datetime.now(timezone.utc)))
        session.commit()
    live = http.get("/api/automation/status").json()
    assert live["worker_online"] is True
    assert live["state"] == "idle"


def test_discovery_processes_all_seed_terms_within_request_budget(client, monkeypatch):
    http, sessions = client
    http.put("/api/sources", json={"enabled_source_ids": ["musicbrainz", "itunes"]})
    http.put("/api/settings", json={"config": {"discovery_seeds": ["Seed A", "Seed B", "Seed C", "Seed D"]}})
    called = []

    async def fake_search(source_id, query, credentials, limit=10, **kwargs):
        called.append((source_id, query))
        return [{
            "provider_id": source_id, "external_id": f"{source_id}-{query}",
            "name": f"Artist {query}", "source_url": f"https://example.test/{source_id}/{query}",
            "country": "KE", "city": "Nairobi", "genres": [], "metrics": {}, "context": {},
        }]

    monkeypatch.setattr(main, "search_identity_source", fake_search)
    response = http.post("/api/discovery/run", json={"limit": 5})
    assert response.status_code == 200, response.text
    assert len(called) == 8
    assert {query for _source, query in called} == {"Seed A", "Seed B", "Seed C", "Seed D"}


def test_youtube_provider_enriches_channel_search_with_public_statistics(monkeypatch):
    from app import providers

    async def fake_get_json(_client, url, params=None, headers=None):
        if url.endswith("/search"):
            return {"items": [{"id": {"channelId": "channel-1"}, "snippet": {"channelTitle": "Nia K", "description": "Nairobi artist"}}]}
        if url.endswith("/channels"):
            return {"items": [{"id": "channel-1", "statistics": {"subscriberCount": "1250", "viewCount": "45000", "videoCount": "16", "hiddenSubscriberCount": False}}]}
        raise AssertionError(url)

    monkeypatch.setattr(providers, "_get_json", fake_get_json)
    result = asyncio.run(providers.search_provider(
        "youtube", query="Nia K", area=None, genre=None, limit=10, credentials={"api_key": "test-key"}
    ))
    assert len(result) == 1
    assert result[0]["name"] == "Nia K"
    assert result[0]["metrics"] == {"subscribers": 1250, "views": 45000, "tracks": 16}


def test_seed_rotation_prevents_later_markets_from_being_starved(client, monkeypatch):
    http, _sessions = client
    http.put("/api/sources", json={"enabled_source_ids": ["musicbrainz", "itunes"]})
    http.put("/api/settings", json={"config": {"discovery_seeds": ["Market A", "Market B", "Market C", "Market D"]}})
    monkeypatch.setenv("MAX_PROVIDER_CALLS_PER_SEARCH", "4")
    calls = []

    async def fake_search(source_id, query, credentials, limit=10, **kwargs):
        calls.append(query)
        return [{"provider_id": source_id, "external_id": f"{source_id}-{query}", "name": f"{source_id} {query}",
                 "source_url": f"https://example.test/{source_id}/{query}", "country": "KE", "city": "Nairobi",
                 "genres": [], "metrics": {}, "context": {}}]

    monkeypatch.setattr(main, "search_identity_source", fake_search)
    first = http.post("/api/discovery/run", json={"limit": 5})
    assert first.status_code == 200, first.text
    first_seeds = set(calls)
    calls.clear()
    second = http.post("/api/discovery/run", json={"limit": 5})
    assert second.status_code == 200, second.text
    second_seeds = set(calls)
    assert first_seeds == {"Market A", "Market B"}
    assert second_seeds == {"Market C", "Market D"}
