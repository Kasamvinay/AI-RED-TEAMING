"""
Tests for app/api/routes.py via FastAPI's TestClient. We swap in a
FakeQwenClient-backed SupportAgent after import so no Ollama server is
required.
"""
from fastapi.testclient import TestClient

import app.main as main_module
from app.api import routes
from app.chatbot.agent import SupportAgent
from app.services.qwen_client import FakeQwenClient


def make_client(canned="Hello, how can I help?", mode="vulnerable"):
    fake_client = FakeQwenClient(canned_response=canned)
    agent = SupportAgent(model_client=fake_client, mode=mode)
    routes.bind_agent(agent)
    return TestClient(main_module.app), fake_client


def test_health_endpoint():
    client, _ = make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_chat_happy_path_shape():
    client, _ = make_client(canned="You can request a refund within 14 days.")
    resp = client.post("/chat", json={"message": "What's your refund policy?", "session_id": "t1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "You can request a refund within 14 days."
    assert body["session_id"] == "t1"
    assert body["mode"] == "vulnerable"
    assert "processing_time" in body
    assert body["metadata"]["intent"] == "policy_question"
    assert "internal_policies" in body["metadata"]["tables_used"]


def test_chat_rejects_empty_message():
    client, _ = make_client()
    resp = client.post("/chat", json={"message": "   ", "session_id": "t1"})
    assert resp.status_code == 400


def test_chat_rejects_empty_session_id():
    client, _ = make_client()
    resp = client.post("/chat", json={"message": "hi", "session_id": ""})
    assert resp.status_code == 400


def test_reset_by_path():
    client, _ = make_client()
    client.post("/chat", json={"message": "hi", "session_id": "reset-path"})
    resp = client.post("/reset/reset-path")
    assert resp.status_code == 200
    assert resp.json()["existed"] is True


def test_reset_by_body():
    client, _ = make_client()
    client.post("/chat", json={"message": "hi", "session_id": "reset-body"})
    resp = client.post("/reset", json={"session_id": "reset-body"})
    assert resp.status_code == 200
    assert resp.json()["existed"] is True


def test_diagnostics_present_when_requested():
    client, _ = make_client()
    resp = client.post(
        "/chat", json={"message": "hi", "session_id": "d1", "diagnostics": True}
    )
    body = resp.json()
    assert body["diagnostics"] is not None
    assert "canary_leaked" in body["diagnostics"]


def test_diagnostics_included_by_default_when_globally_enabled():
    """DIAGNOSTICS_ENABLED defaults to true in the test environment, so a
    request that doesn't mention diagnostics at all still gets them --
    the global setting is the default, not an opt-in per request."""
    client, _ = make_client()
    resp = client.post("/chat", json={"message": "hi", "session_id": "d2"})
    body = resp.json()
    assert body["diagnostics"] is not None


def test_diagnostics_can_be_opted_out_per_request():
    client, _ = make_client()
    resp = client.post(
        "/chat", json={"message": "hi", "session_id": "d3", "diagnostics": False}
    )
    body = resp.json()
    assert body["diagnostics"] is None


def test_diagnostics_absent_when_globally_disabled_even_if_requested():
    client, _ = make_client()
    main_module.settings.DIAGNOSTICS_ENABLED = False
    try:
        resp = client.post(
            "/chat", json={"message": "hi", "session_id": "d4", "diagnostics": True}
        )
        body = resp.json()
        assert body["diagnostics"] is None
    finally:
        main_module.settings.DIAGNOSTICS_ENABLED = True
