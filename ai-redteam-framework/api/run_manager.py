"""
api/run_manager.py

Runs one attack pipeline in a background thread and tracks live status
for GET /status, using the on_event callback already added (additively)
to core/orchestrator.py::AutonomousOrchestrator. This file contains no
attack-pipeline logic of its own — it only calls runner.build_pipeline()
(the same function main.py uses) and listens to the events it emits.

Deliberately simple: ONE run can be active at a time (matches the spec's
"do not over-engineer" — a technical demo doesn't need concurrent runs),
tracked with a plain lock. Starting a new run while one is active is
rejected with a clear error rather than silently queuing or racing.
"""

from __future__ import annotations

import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Optional

from config.settings import load_config
from reporting.mitigation_report_generator import MitigationReportGenerator
from reporting.run_registry import RunRecord, RunRegistry
from runner import build_pipeline

logger = logging.getLogger("redteam.api.run_manager")

_STAGE_CHECKLIST_TEMPLATE = {
    "strategy_selected": False,
    "prompt_generated": False,
    "attack_sent": False,
    "response_received": False,
    "judge_completed": False,
    "knowledge_updated": False,
}


class RunManager:
    def __init__(self, registry_path: str = "output/runs_registry.jsonl",
                 reports_dir: str = "output/reports"):
        self.registry = RunRegistry(path=registry_path)
        self.mitigation_generator = MitigationReportGenerator(output_dir=reports_dir)
        self._lock = threading.Lock()
        self._active_run_id: Optional[str] = None
        self._status: dict = {"state": "idle"}
        self._thread: Optional[threading.Thread] = None

    # -- public API used by api/app.py --------------------------------

    def is_active(self) -> bool:
        with self._lock:
            return self._active_run_id is not None

    def get_status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def start_run(
        self,
        objective_name: Optional[str] = None,
        target_name: Optional[str] = None,
        prompt_generator_kind: Optional[str] = None,
        max_iterations: Optional[int] = None,
        max_llm_calls: Optional[int] = None,
        run_name: str = "prompt_injection_run",
        fresh_kb: bool = False,
    ) -> RunRecord:
        if self.is_active():
            raise RuntimeError(
                "A run is already in progress. Wait for it to finish (see GET /status) "
                "before starting another — this demo runs one attack session at a time."
            )

        config = load_config()
        objective_for_record = objective_name or config["objective"]
        target_for_record = target_name or config["target"]["adapter"]
        max_iter_for_record = max_iterations or config["run"]["max_iterations"]

        record = self.registry.create(
            run_name=run_name,
            objective=objective_for_record,
            target_adapter=target_for_record,
            max_iterations=max_iter_for_record,
        )

        with self._lock:
            self._active_run_id = record.run_id
            self._status = {
                "state": "running",
                "run_id": record.run_id,
                "run_name": run_name,
                "objective": objective_for_record,
                "target": target_for_record,
                "iteration": 0,
                "max_iterations": max_iter_for_record,
                "stage": None,
                "strategy": None,
                "current_attack_preview": None,
                "stage_checklist": dict(_STAGE_CHECKLIST_TEMPLATE),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }

        thread = threading.Thread(
            target=self._run_in_background,
            args=(record.run_id, config, objective_name, target_name, prompt_generator_kind,
                  max_iterations, max_llm_calls, run_name, fresh_kb),
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return record

    # -- background execution --------------------------------------------

    def _on_event(self, event: str, **fields) -> None:
        with self._lock:
            if self._status.get("state") != "running":
                return
            if event == "strategy_selected":
                self._status["stage_checklist"] = dict(_STAGE_CHECKLIST_TEMPLATE)
                self._status["iteration"] = fields.get("iteration", self._status["iteration"])
                self._status["strategy"] = fields.get("strategy")
            if event in self._status["stage_checklist"]:
                self._status["stage_checklist"][event] = True
            self._status["stage"] = event
            if event == "prompt_generated":
                self._status["current_attack_preview"] = fields.get("prompt_preview")
            if event == "report_generated":
                self._status["stage"] = "report_generated"

    def _run_in_background(
        self, run_id, config, objective_name, target_name, prompt_generator_kind,
        max_iterations, max_llm_calls, run_name, fresh_kb,
    ) -> None:
        try:
            pipeline = build_pipeline(
                config=config,
                objective_name=objective_name,
                target_name=target_name,
                prompt_generator_kind=prompt_generator_kind,
                max_iterations=max_iterations,
                max_llm_calls=max_llm_calls,
                fresh_kb=fresh_kb,
                on_event=self._on_event,
            )
            technical_md_path = pipeline.orchestrator.run(run_name=run_name, run_id=run_id)

            run_experiences = pipeline.orchestrator.experience_memory.get_run_experiences(run_id)

            total = len(run_experiences)
            successes = sum(1 for e in run_experiences if e.analysis.outcome == "success")
            partials = sum(1 for e in run_experiences if e.analysis.outcome == "partial")
            severities = [e.analysis.severity.value for e in run_experiences if e.analysis.outcome != "failure"]
            severity_order = ["critical", "high", "medium", "low", "info", "none"]
            highest = next((s for s in severity_order if s in severities), "none")

            technical_json_path = technical_md_path[:-3] + ".json"

            mitigation_path = self.mitigation_generator.generate(
                experiences=run_experiences,
                target_name=target_name or config["target"]["adapter"],
                run_name=f"{run_name}_{run_id}",
            )

            self.registry.mark_completed(
                run_id=run_id,
                total_attacks=total,
                successful_attacks=successes,
                partial_attacks=partials,
                highest_severity=highest,
                technical_report_md=technical_md_path,
                technical_report_json=technical_json_path,
                mitigation_report_pdf=mitigation_path,
            )

            with self._lock:
                self._status["state"] = "completed"
                self._status["stage"] = "completed"

            pipeline.knowledge_base.close()

        except Exception as exc:  # noqa: BLE001 — never let a run crash the API process
            logger.error("Run %s failed: %s\n%s", run_id, exc, traceback.format_exc())
            self.registry.mark_failed(run_id, str(exc))
            with self._lock:
                self._status["state"] = "failed"
                self._status["error"] = str(exc)
        finally:
            with self._lock:
                self._active_run_id = None
