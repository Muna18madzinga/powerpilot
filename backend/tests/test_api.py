import pytest
from fastapi.testclient import TestClient

from powerpilot import api


@pytest.fixture(scope="module")
def client():
    api.clock.running = False
    with TestClient(api.app) as test_client:
        test_client.post("/api/reset")
        yield test_client


def test_state_has_every_panel(client):
    body = client.get("/api/state").json()
    assert set(body) == {"meta", "fleet", "kpis", "sites", "recommendations", "log", "goals"}
    assert len(body["sites"]) == 30
    assert body["meta"]["clock"]["running"] is False


def test_site_detail_and_missing_site(client):
    assert client.get("/api/sites/GWE-001").json()["name"] == "Gweru CBD"
    assert client.get("/api/sites/NOPE").status_code == 404


def test_scenario_then_approve(client):
    client.post("/api/scenarios", json={"kind": "link_fault", "site_id": "ZVI-001"})
    client.post("/api/clock/step", params={"count": 2})
    recs = client.get("/api/recommendations").json()
    rec = next(r for r in recs if r["kind"] == "repair_link" and r["site_id"] == "ZVI-001")
    approved = client.post(f"/api/recommendations/{rec['id']}/approve").json()
    assert approved["status"] == "approved"
    assert client.post(f"/api/recommendations/{rec['id']}/approve").status_code == 409


def test_goal_and_settings(client):
    goal = client.post("/api/goals", json={"text": "Keep Zvishavane up tonight"}).json()
    assert goal["intent"] == "protect_uptime"
    settings = client.put("/api/settings", json={"autonomy": "autopilot", "stage": 2}).json()
    assert settings == {"autonomy": "autopilot", "stage": 2, "levels": ["advise", "assist", "autopilot"]}


def test_clock_rejects_unknown_speed(client):
    assert client.put("/api/clock", json={"speed": 3}).status_code == 422
    assert client.put("/api/clock", json={"speed": 4}).json()["speed"] == 4
