"""API and unit tests. External services are mocked in conftest.py."""

from services.llm import _parse_newsletter


# --- Auth ---

def test_unauthenticated_is_blocked(client):
    assert client.get("/topics").status_code == 403


def test_register_login_me(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    assert r.json()["user"]["email"] == "a@b.com"

    assert client.post("/auth/login", json={"email": "a@b.com", "password": "secret123"}).status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "a@b.com"


def test_duplicate_register_conflicts(client):
    client.post("/auth/register", json={"email": "dup@b.com", "password": "secret123"})
    r = client.post("/auth/register", json={"email": "dup@b.com", "password": "secret123"})
    assert r.status_code == 409


def test_bad_login_unauthorized(client):
    client.post("/auth/register", json={"email": "c@b.com", "password": "secret123"})
    assert client.post("/auth/login", json={"email": "c@b.com", "password": "wrong"}).status_code == 401


# --- Topics (per-user) ---

def test_custom_topics_are_per_user(client, auth):
    a, b = auth(), auth()
    client.post("/topics", headers=a, json={"name": "Formula 1"})

    assert "Formula 1" in client.get("/topics", headers=a).json()["topics"]
    assert "Formula 1" not in client.get("/topics", headers=b).json()["topics"]


def test_add_topic_is_idempotent(client, auth):
    a = auth()
    client.post("/topics", headers=a, json={"name": "Crypto"})
    topics = client.post("/topics", headers=a, json={"name": "Crypto"}).json()["topics"]
    assert topics.count("Crypto") == 1


# --- Generate + newsletters ---

def test_generate_returns_structure_and_saves(client, auth):
    a = auth()
    r = client.post("/generate", headers=a, json={
        "topics": ["Tech"], "tone": "concise",
        "filters": {"language": "en", "sort_by": "publishedAt", "page_size": 3,
                    "domains": [], "exclude_domains": []},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject_options"] == ["Subject A", "Subject B", "Subject C"]
    assert body["preview_text"] == "A quick preview."
    assert "TL;DR" in body["markdown"]
    assert len(body["articles"]) == 3  # page_size honored
    assert body["articles"][0]["image_url"]  # image carried through

    # It was saved and shows in the list.
    listed = client.get("/newsletters", headers=a).json()
    assert len(listed) == 1 and listed[0]["id"] == body["id"]


def test_newsletters_are_isolated(client, auth):
    a, b = auth(), auth()
    nid = client.post("/generate", headers=a, json={"topics": ["Tech"]}).json()["id"]

    assert len(client.get("/newsletters", headers=b).json()) == 0
    assert client.get(f"/newsletters/{nid}", headers=b).status_code == 404
    assert client.get(f"/newsletters/{nid}", headers=a).status_code == 200


def test_delete_newsletter(client, auth):
    a = auth()
    nid = client.post("/generate", headers=a, json={"topics": ["Tech"]}).json()["id"]
    assert client.delete(f"/newsletters/{nid}", headers=a).status_code == 204
    assert len(client.get("/newsletters", headers=a).json()) == 0


# --- Presets ---

def test_presets_crud_and_isolation(client, auth):
    a, b = auth(), auth()
    filters = {"language": "fr", "sort_by": "popularity", "page_size": 8,
               "domains": ["lemonde.fr"], "exclude_domains": []}
    created = client.post("/presets", headers=a, json={"name": "French", "filters": filters})
    assert created.status_code == 201
    assert created.json()["filters"]["language"] == "fr"

    assert len(client.get("/presets", headers=a).json()) == 1
    assert len(client.get("/presets", headers=b).json()) == 0  # isolated

    # Same name overwrites rather than duplicating.
    client.post("/presets", headers=a, json={"name": "French", "filters": filters})
    assert len(client.get("/presets", headers=a).json()) == 1

    pid = client.get("/presets", headers=a).json()[0]["id"]
    assert client.delete(f"/presets/{pid}", headers=a).status_code == 204
    assert len(client.get("/presets", headers=a).json()) == 0


# --- Parser unit tests ---

def test_parse_newsletter_extracts_header():
    text = (
        "SUBJECT: One\nSUBJECT: Two\nPREVIEW: A teaser.\n---\n"
        "## TL;DR\n- a\n\n## Topic\nbody"
    )
    out = _parse_newsletter(text)
    assert out.subject_options == ["One", "Two"]
    assert out.preview_text == "A teaser."
    assert out.markdown.startswith("## TL;DR")
    assert "SUBJECT:" not in out.markdown


def test_parse_newsletter_falls_back_without_header():
    text = "## Just a body\nNo header at all."
    out = _parse_newsletter(text)
    assert out.subject_options == []
    assert out.preview_text is None
    assert out.markdown == text
