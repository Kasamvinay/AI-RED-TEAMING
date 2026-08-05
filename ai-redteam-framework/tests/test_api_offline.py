"""
tests/test_api_offline.py

Exercises the Flask API end-to-end using Flask's in-process test client
(no port binding, no real server process) — starts a real attack run
(mock target + template generator, so $0 cost and no API key needed),
polls it to completion, and checks every endpoint the demo frontend
depends on, including the two downloadable reports.

Run with: python -m pytest tests/ -v
or directly: python tests/test_api_offline.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_OUTPUT_DIR = "output/test_api"


def _reset_output():
    for name in ("knowledge_base.sqlite3", "experience_memory.jsonl", "runs_registry.jsonl"):
        p = os.path.join("output", name)
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(_TEST_OUTPUT_DIR):
        shutil.rmtree(_TEST_OUTPUT_DIR)


def test_full_api_driven_run():
    _reset_output()

    # Import after resetting so app.py's module-level RunManager doesn't
    # pick up stale state from a previous test run in the same process.
    from api.app import app, run_manager

    client = app.test_client()

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    objectives = client.get("/api/objectives")
    assert objectives.status_code == 200
    assert "customer_support" in objectives.get_json()["objectives"]

    start = client.post("/api/runs", json={
        "objective": "customer_support",
        "target": "mock",
        "prompt_generator": "template",
        "max_iterations": 6,
        "max_llm_calls": 0,
        "run_name": "api_test_run",
        "fresh_kb": True,
    })
    assert start.status_code == 202, start.get_json()
    run_id = start.get_json()["run_id"]

    # Starting a second run while one is active must be rejected.
    conflict = client.post("/api/runs", json={"target": "mock", "max_iterations": 2})
    assert conflict.status_code == 409

    # Poll status until the background thread finishes (bounded wait).
    deadline = time.time() + 30
    state = None
    while time.time() < deadline:
        status = client.get("/api/status").get_json()
        state = status.get("state")
        if state in ("completed", "failed"):
            break
        time.sleep(0.2)
    assert state == "completed", f"run did not complete in time (last state: {state})"

    runs = client.get("/api/runs").get_json()["runs"]
    assert any(r["run_id"] == run_id for r in runs)

    reports = client.get("/api/reports").get_json()["reports"]
    matching = [r for r in reports if r["run_id"] == run_id]
    assert len(matching) == 1
    assert matching[0]["has_mitigation_pdf"]
    assert matching[0]["has_technical_report"]

    history = client.get(f"/api/history/{run_id}").get_json()
    assert history["count"] == 6
    assert all("prompt" in a and "outcome" in a for a in history["attacks"])

    mitigation = client.get(f"/api/mitigation/{run_id}")
    assert mitigation.status_code == 200
    assert mitigation.data[:4] == b"%PDF", "downloaded file is not a valid PDF"

    technical_md = client.get(f"/api/reports/{run_id}/technical/md")
    assert technical_md.status_code == 200
    assert b"Autonomous Prompt Injection Report" in technical_md.data

    technical_json = client.get(f"/api/reports/{run_id}/technical/json")
    assert technical_json.status_code == 200
    parsed = json.loads(technical_json.data)
    assert "summary" in parsed and "strategy_performance" in parsed

    not_found = client.get("/api/mitigation/does-not-exist")
    assert not_found.status_code == 404

    frontend = client.get("/")
    assert frontend.status_code == 200
    assert b"ReactDOM.createRoot" in frontend.data

    _reset_output()
    print(f"OK: full API-driven run completed (run_id={run_id}), all endpoints verified")


if __name__ == "__main__":
    test_full_api_driven_run()
