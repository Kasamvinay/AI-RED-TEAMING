"""
api/app.py

REST API for the Version 3 demo. This file contains NO attack-pipeline
logic — it only exposes the existing framework (via runner.py /
api/run_manager.py) over HTTP so a frontend can visualize execution.

Endpoints:
    POST /api/runs                start a new attack run
    GET  /api/status               live status of the active/last run
    GET  /api/runs                 all previous runs
    GET  /api/reports              report metadata for all runs
    GET  /api/mitigation/<run_id>  download the Executive Mitigation PDF
    GET  /api/reports/<run_id>/technical/<fmt>   download technical report (md|json)
    GET  /api/history/<run_id>     every attack performed during a run
    GET  /api/objectives           available objective profiles (for the UI's dropdown)
    GET  /api/health               basic health check

The frontend (frontend/index.html) talks ONLY to this API — it never
calls the target Customer Support Bot directly.

Framework: Flask, chosen because it's what's actually available/testable
in this environment without network access to install packages. FastAPI
would work equally well if you prefer it and can `pip install fastapi
uvicorn` — the run_manager/runner layer underneath is framework-agnostic,
so swapping the HTTP layer later only means rewriting this one file.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request, send_file, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from api.run_manager import RunManager
from config.settings import load_config
from core.memory import JsonlExperienceMemory
from objectives.profiles import list_available_objectives

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = Flask(__name__)


@app.after_request
def _add_cors_headers(response):
    # The demo frontend (frontend/index.html) is a static file typically
    # opened from a different origin than this API — allow it through.
    # For a production deployment, restrict this to a known origin.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


_config = load_config()
run_manager = RunManager(
    registry_path="output/runs_registry.jsonl",
    reports_dir=_config["output"]["report_dir"],
)


@app.get("/")
def frontend():
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
    return send_from_directory(frontend_dir, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/objectives")
def objectives():
    return jsonify({"objectives": list_available_objectives()})


@app.post("/api/runs")
def start_run():
    body = request.get_json(silent=True) or {}
    try:
        record = run_manager.start_run(
            objective_name=body.get("objective"),
            target_name=body.get("target"),
            prompt_generator_kind=body.get("prompt_generator"),
            max_iterations=body.get("max_iterations"),
            max_llm_calls=body.get("max_llm_calls"),
            run_name=body.get("run_name", "prompt_injection_run"),
            fresh_kb=bool(body.get("fresh_kb", False)),
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409
    # Note: configuration errors (unknown objective, missing LLM API key for
    # the selected provider, unknown adapter name, etc.) happen inside
    # build_pipeline(), which runs in the background thread — they surface
    # via GET /status (state="failed", "error": "...") rather than here,
    # since pipeline construction is intentionally never on the request path.

    return jsonify({
        "run_id": record.run_id,
        "run_name": record.run_name,
        "status": record.status,
    }), 202


@app.get("/api/status")
def status():
    return jsonify(run_manager.get_status())


@app.get("/api/runs")
def list_runs():
    runs = run_manager.registry.all_runs()
    return jsonify({"runs": [_run_to_dict(r) for r in runs]})


@app.get("/api/reports")
def list_reports():
    runs = [r for r in run_manager.registry.all_runs() if r.status == "completed"]
    return jsonify({"reports": [
        {
            "run_id": r.run_id,
            "run_name": r.run_name,
            "completed_at": r.completed_at,
            "highest_severity": r.highest_severity,
            "total_attacks": r.total_attacks,
            "successful_attacks": r.successful_attacks,
            "has_mitigation_pdf": bool(r.mitigation_report_pdf),
            "has_technical_report": bool(r.technical_report_md),
        }
        for r in runs
    ]})


@app.get("/api/mitigation/<run_id>")
def download_mitigation(run_id: str):
    record = run_manager.registry.get(run_id)
    if record is None or not record.mitigation_report_pdf:
        return jsonify({"error": "Mitigation report not found for this run_id."}), 404
    abs_path = os.path.abspath(record.mitigation_report_pdf)
    if not os.path.exists(abs_path):
        return jsonify({"error": "Report file is missing on disk."}), 404
    return send_file(abs_path, as_attachment=True,
                      download_name=f"{record.run_name}_mitigation_report.pdf")


@app.get("/api/reports/<run_id>/technical/<fmt>")
def download_technical(run_id: str, fmt: str):
    record = run_manager.registry.get(run_id)
    if record is None:
        return jsonify({"error": "Unknown run_id."}), 404
    if fmt not in ("md", "json"):
        return jsonify({"error": "Use fmt=md or fmt=json."}), 400
    path = record.technical_report_md if fmt == "md" else record.technical_report_json
    if not path:
        return jsonify({"error": "Technical report not available for this run_id/fmt."}), 404
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return jsonify({"error": "Technical report file not found."}), 404
    return send_file(abs_path, as_attachment=True, download_name=os.path.basename(abs_path))


@app.get("/api/history/<run_id>")
def history(run_id: str):
    record = run_manager.registry.get(run_id)
    if record is None:
        return jsonify({"error": "Unknown run_id."}), 404

    experience_memory = JsonlExperienceMemory(path=_config["output"]["experience_memory_path"])
    run_experiences = experience_memory.get_run_experiences(run_id)

    return jsonify({
        "run_id": run_id,
        "count": len(run_experiences),
        "attacks": [
            {
                "iteration": i + 1,
                "strategy": e.strategy,
                "technique": e.prompt.technique,
                "source": e.prompt.source,
                "outcome": e.analysis.outcome,
                "severity": e.analysis.severity.value,
                "score": e.analysis.score,
                "confidence": e.analysis.confidence,
                "reward": e.reward,
                "explanation": e.analysis.explanation,
                "recommendation": e.analysis.recommendation,
                "prompt": e.prompt.text,
                "response": e.response.text,
                "timestamp": e.timestamp,
            }
            for i, e in enumerate(run_experiences)
        ],
    })


def _run_to_dict(record) -> dict:
    from dataclasses import asdict
    return asdict(record)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
