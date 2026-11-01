import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db


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
    monkeypatch.setattr(main, "create_database_tables", lambda: Base.metadata.create_all(test_engine))
    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    test_engine.dispose()


def test_health_discloses_demo_mode_and_unconfigured_sources(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "authentication": "disabled-demo-mode",
        "configured_data_providers": ["musicbrainz"],
    }


def test_provider_status_is_explicit_about_integrations(client):
    providers = client.get("/api/providers").json()

    assert [(provider["id"], provider["configured"]) for provider in providers] == [
        ("musicbrainz", True),
        ("spotify", False),
        ("youtube", False),
    ]


def test_discovery_search_requires_at_least_one_filter(client):
    response = client.get("/api/discovery/search")

    assert response.status_code == 422
    assert "artist, region, or genre" in response.json()["detail"]


def test_discovery_search_returns_attributed_musicbrainz_results(client, monkeypatch):
    calls = {}

    async def fake_search(**filters):
        calls.update(filters)
        return {
            "items": [
                {
                    "id": "musicbrainz-artist-id",
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
        }

    monkeypatch.setattr(main, "search_musicbrainz", fake_search)
    response = client.get("/api/discovery/search?area=Kenya&genre=Afrobeats&limit=5")

    assert response.status_code == 200
    assert calls == {"query": None, "area": "Kenya", "genre": "Afrobeats", "limit": 5, "offset": 0}
    assert response.json()["items"][0]["source_url"].startswith("https://musicbrainz.org/artist/")
    assert response.json()["items"][0]["tags"] == ["afrobeats"]


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
