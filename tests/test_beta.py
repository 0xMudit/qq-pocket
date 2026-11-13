import os

os.environ["API_KEY"] = "test-secret-123456"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
import app

ORIGIN = {"origin": "http://testserver"}


@pytest.fixture
def client():
    with TestClient(app.app, headers=ORIGIN) as c:
        # Isolate beta data without relying on test order.
        with app.engine.begin() as db:
            for table in TABLES:
                db.execute(text("DELETE FROM " + table))
        yield c


def signup(client, name="alice"):
    body = {"username": name, "password": "ValidPassword!2026"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/login", json=body).status_code == 200
    return client.get("/api/auth/me").json()


def other_user(client):
    client.post("/api/auth/logout")
    signup(client, "bob")


def test_account_sessions_and_origin(client):
    assert client.get("/api/auth/me").status_code == 401
    signup(client)
    assert client.get("/api/auth/me").json()["username"] == "alice"
    assert (
        client.post(
            "/api/auth/keys",
            json={"label": "test"},
            headers={"origin": "https://evil.example"},
        ).status_code
        == 403
    )
    key = client.post("/api/auth/keys", json={"label": "integration"}).json()["token"]
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get(
            "/api/auth/me", headers={"authorization": "Bearer " + key}
        ).status_code
        == 200
    )
    keys = client.get(
        "/api/auth/keys", headers={"authorization": "Bearer " + key}
    ).json()
    assert (
        client.delete(
            "/api/auth/keys/" + keys[0]["digest"],
            headers={"authorization": "Bearer " + key},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/auth/me", headers={"authorization": "Bearer " + key}
        ).status_code
        == 401
    )


def test_password_and_duplicate_account(client):
    signup(client)
    assert (
        client.post(
            "/api/auth/register",
            json={"username": "alice", "password": "ValidPassword!2026"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "alice", "password": "WrongPassword!2026"},
        ).status_code
        == 401
    )


TABLES = ["beta_jobs", "beta_sessions", "beta_users", "beta_limits"]


def test_owned_jobs_and_idempotency(client):
    signup(client)
    body = {
        "task": "sha256",
        "payload": "hello",
        "delay_seconds": 3600,
        "idempotency_key": "test-key-123",
    }
    job = client.post("/api/jobs", json=body).json()
    assert client.post("/api/jobs", json=body).json()["id"] == job["id"]
    assert (
        client.post("/api/jobs", json={**body, "payload": "different"}).status_code
        == 409
    )
    assert (
        client.post("/api/jobs", json={**body, "delay_seconds": 0}).status_code == 409
    )
    other_user(client)
    assert client.get("/api/jobs").json() == []
    assert client.post("/api/jobs/" + job["id"] + "/cancel").status_code == 409
    assert client.post("/api/jobs/" + job["id"] + "/retry").status_code == 409


def test_processing_and_dead_letter(client):
    user = signup(client)
    good = client.post(
        "/api/jobs",
        json={
            "task": "text_stats",
            "payload": "two words",
            "idempotency_key": "good-key-123",
        },
    ).json()
    assert client.get("/api/jobs").json()[0]["status"] == "succeeded"
    bad = client.post(
        "/api/jobs",
        json={"task": "sum", "payload": "not-json", "idempotency_key": "bad-key-123"},
    ).json()
    for _ in range(2):
        with app.engine.begin() as db:
            db.execute(
                text("UPDATE beta_jobs SET available=0 WHERE id=:id"), {"id": bad["id"]}
            )
        app.product.tick()
    rows = client.get("/api/jobs").json()
    failed = next(j for j in rows if j["id"] == bad["id"])
    assert failed["status"] == "dead" and failed["attempts"] == 3


def test_expired_worker_fencing(client):
    user = signup(client)
    job = client.post(
        "/api/jobs",
        json={
            "task": "sum",
            "payload": "[1,2]",
            "delay_seconds": 3600,
            "idempotency_key": "lease-key-123",
        },
    ).json()
    with app.engine.begin() as db:
        db.execute(
            text("UPDATE beta_jobs SET available=0 WHERE id=:id"), {"id": job["id"]}
        )
    first = app.product.claim(user["id"])
    with app.engine.begin() as db:
        db.execute(text("UPDATE beta_jobs SET lease=0 WHERE id=:id"), {"id": job["id"]})
    second = app.product.claim(user["id"])
    assert first["token"] != second["token"]
    assert not app.product.finish(first, 100)
    assert app.product.finish(second, 3)
