from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from tools.verification.source_fingerprint import compute_source_fingerprint


REPO = Path(__file__).resolve().parents[2]

ARTIFACT_CONTRACT_VERSION = "2026-05-23.1"

PHASE_TIMING_KEYS: tuple[str, ...] = (
    "streamlit_ready_ms",
    "page_route_ready_ms",
    "widget_sync_ms",
    "replay_apply_ms",
    "post_apply_settle_ms",
    "browser_probe_publish_ms",
    "timeline_capture_ms",
    "page_cycle_check_ms",
    "browser_context_create_ms",
    "browser_context_teardown_ms",
)

TIMING_WARNING_THRESHOLDS_MS: dict[str, int] = {
    "replay_apply_ms": 180_000,
    "post_apply_settle_ms": 120_000,
    "page_cycle_check_ms": 120_000,
    "design_guide_build_ms": 60_000,
}

REQUIRED_COMPLETION_FILES: tuple[str, ...] = (
    "run_summary.json",
    "lifecycle_events.jsonl",
    "lifecycle_heartbeat.json",
)

FAILURE_CLASSIFICATION_BUCKETS: dict[str, str] = {
    "streamlit_runtime_reconnect_during_verification": "runtime-orchestration",
    "browser_probe_attach_during_teardown": "runtime-orchestration",
    "browser_probe_timeout_before_timeline": "runtime-orchestration",
    "browser_probe_marker_missing": "verifier-readiness",
    "inputs_content_not_ready_before_browser_probe": "verifier-readiness",
    "replay_input_application_runtime_stall": "runtime-orchestration",
    "verifier_disabled_input_edit_attempt": "verifier-readiness",
    "page_cycle_navigation_timeout": "page-cycle-render",
    "ghost_or_empty_ui_render_after_page_cycle": "page-cycle-render",
    "bending_ready_gate_timeout": "page-cycle-render",
    "page_cycle_failure_capture_unavailable": "runtime-orchestration",
    "phase_not_reached": "phase_not_reached",
}


def repo_relative(path: Path | str | None) -> str:
    if path is None:
        return ""
    try:
        return str(Path(path).resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _hash_path(path: Path | str | None) -> dict[str, Any]:
    if path is None:
        return {"path": "", "exists": False, "sha256": None, "size": None}
    target = Path(path)
    if not target.is_absolute():
        target = (REPO / target).resolve()
    if not target.exists() or not target.is_file():
        return {"path": repo_relative(target), "exists": False, "sha256": None, "size": None}
    data = target.read_bytes()
    return {
        "path": repo_relative(target),
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def environment_marker(*, port: int | None = None) -> dict[str, Any]:
    return {
        "python_version": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "pid": os.getpid(),
        "port": port,
        "codex_browser_test_mode": os.environ.get("CODEX_BROWSER_TEST_MODE"),
    }


def build_run_metadata(
    *,
    artifact_dir: Path,
    command_line: str,
    port: int | None,
    started_at: str | None = None,
    finished_at: str | None = None,
    replay_source: str | Path | None = None,
    repo: Path | None = None,
) -> dict[str, Any]:
    source_fingerprint = compute_source_fingerprint(repo=repo or REPO)
    return {
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "artifact_dir": str(Path(artifact_dir)),
        "command_line": command_line,
        "started_at": started_at,
        "finished_at": finished_at,
        "port": port,
        "environment": environment_marker(port=port),
        "source_fingerprint": source_fingerprint,
        "correctness_fingerprint": source_fingerprint.get("correctness_fingerprint"),
        "diagnostic_fingerprint": source_fingerprint.get("diagnostic_fingerprint"),
        "verifier_runtime_fingerprint": source_fingerprint.get("verifier_runtime_fingerprint"),
        "verifier_code_fingerprint": source_fingerprint.get("diagnostic_fingerprint"),
        "app_source_fingerprint": source_fingerprint.get("correctness_fingerprint"),
        "replay_source_fingerprint": _hash_path(replay_source) if replay_source else None,
    }


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(float(value))
    except Exception:
        return None


def normalize_phase_timings(stage_timing_summary: dict[str, Any] | None) -> dict[str, Any]:
    timings = dict(stage_timing_summary or {})
    reached = {key: key in timings for key in PHASE_TIMING_KEYS}
    normalized = {}
    for key in PHASE_TIMING_KEYS:
        normalized[key] = _as_int(timings.get(key)) if key in timings else "phase_not_reached"
    return {
        "version": ARTIFACT_CONTRACT_VERSION,
        "phase_timings": normalized,
        "phase_reached": reached,
        "raw_stage_timing_summary": timings,
    }


def _collect_design_guide_build_ms(artifact_dir: Path) -> int | None:
    profile = artifact_dir / "design_guide_build_profile.json"
    if not profile.exists():
        return None
    try:
        data = json.loads(profile.read_text(encoding="utf-8"))
    except Exception:
        return None
    candidates = []
    if isinstance(data, dict):
        candidates.extend(
            [
                data.get("total_design_guide_build_ms"),
                data.get("design_guide_build_ms"),
                data.get("total_build_ms"),
            ]
        )
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                candidates.extend(
                    [
                        item.get("total_design_guide_build_ms"),
                        item.get("design_guide_build_ms"),
                        item.get("total_build_ms"),
                    ]
                )
    ints = [_as_int(item) for item in candidates]
    ints = [item for item in ints if item is not None]
    return max(ints) if ints else None


def timing_budget_warnings(
    stage_timing_summary: dict[str, Any] | None,
    *,
    artifact_dir: Path | None = None,
) -> list[dict[str, Any]]:
    timings = dict(stage_timing_summary or {})
    observed = {key: _as_int(value) for key, value in timings.items()}
    if artifact_dir is not None:
        build_ms = _collect_design_guide_build_ms(Path(artifact_dir))
        if build_ms is not None:
            observed["design_guide_build_ms"] = build_ms
    warnings = []
    for key, threshold in TIMING_WARNING_THRESHOLDS_MS.items():
        value = observed.get(key)
        if value is not None and value > threshold:
            warnings.append(
                {
                    "classification": "timing_budget_warning",
                    "phase": key,
                    "observed_ms": value,
                    "threshold_ms": threshold,
                    "message": f"{key} exceeded diagnostic timing budget.",
                }
            )
    return warnings


def classify_failure_family(classification: str | None) -> str:
    value = str(classification or "").strip()
    if not value:
        return ""
    for prefix, family in FAILURE_CLASSIFICATION_BUCKETS.items():
        if value == prefix or value.startswith(f"{prefix}:"):
            return family
    if value.startswith("design_guide_") or value.startswith("failed_") or "contradiction" in value:
        return "product issue"
    if "timeout" in value or "runtime" in value:
        return "runtime-orchestration"
    if "page_cycle" in value or "render" in value:
        return "page-cycle-render"
    if "ready" in value or "readiness" in value or "input" in value:
        return "verifier-readiness"
    return "unclear"


def product_visible_contradiction(summary: dict[str, Any]) -> bool:
    failures = summary.get("failures")
    if isinstance(failures, list):
        for failure in failures:
            if not isinstance(failure, dict):
                continue
            diagnosis = failure.get("diagnosis") if isinstance(failure.get("diagnosis"), dict) else {}
            if diagnosis.get("product_bug_likely") is True:
                return True
            if failure.get("product_visible_contradiction") is True:
                return True
    return bool(summary.get("product_visible_contradiction_proven") is True)


def enrich_run_summary(
    summary: dict[str, Any],
    *,
    artifact_dir: Path,
    command_line: str,
    port: int | None,
    started_at: str | None = None,
    finished_at: str | None = None,
    replay_source: str | Path | None = None,
) -> dict[str, Any]:
    out = dict(summary)
    metadata = build_run_metadata(
        artifact_dir=Path(artifact_dir),
        command_line=command_line,
        port=port,
        started_at=started_at,
        finished_at=finished_at,
        replay_source=replay_source or out.get("replay_source"),
    )
    out["verifier_metadata"] = metadata
    out.setdefault("command_line", command_line)
    out.setdefault("started_at", started_at)
    out["finished_at"] = finished_at or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out.setdefault("port", port)
    out.setdefault("source_fingerprint", metadata.get("source_fingerprint"))
    out.setdefault("correctness_fingerprint", metadata.get("correctness_fingerprint"))
    out.setdefault("diagnostic_fingerprint", metadata.get("diagnostic_fingerprint"))
    out.setdefault("verifier_runtime_fingerprint", metadata.get("verifier_runtime_fingerprint"))
    out.setdefault("replay_source_fingerprint", metadata.get("replay_source_fingerprint"))
    out["phase_timing_contract"] = normalize_phase_timings(out.get("stage_timing_summary"))
    out["timing_budget_warnings"] = timing_budget_warnings(out.get("stage_timing_summary"), artifact_dir=Path(artifact_dir))
    classification = out.get("failure_classification")
    if not classification and isinstance(out.get("failures"), list) and out["failures"]:
        first = out["failures"][0]
        if isinstance(first, dict):
            classification = first.get("failure_classification") or first.get("classification")
    out["failure_classification"] = classification or ("" if out.get("verdict") == "PASS" else "unclassified_failure")
    out["classification_family"] = classify_failure_family(out.get("failure_classification"))
    out["product_visible_contradiction_proven"] = product_visible_contradiction(out)
    return out


def _json_file_exists(artifact_dir: Path, name: str) -> bool:
    path = artifact_dir / name
    return path.exists() and path.is_file() and path.stat().st_size > 0


def validate_replay_artifact(artifact_dir: Path | str) -> dict[str, Any]:
    artifact = Path(artifact_dir)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    file_status = {name: _json_file_exists(artifact, name) for name in REQUIRED_COMPLETION_FILES}
    for name, ok in file_status.items():
        if not ok:
            errors.append(
                {
                    "classification": "artifact_contract_missing_required_file",
                    "field": name,
                    "message": f"Required artifact file is missing or empty: {name}",
                }
            )
    summary: dict[str, Any] = {}
    if file_status.get("run_summary.json"):
        try:
            summary = json.loads((artifact / "run_summary.json").read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(
                {
                    "classification": "artifact_contract_unreadable_run_summary",
                    "field": "run_summary.json",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
    required_summary_fields = (
        "verdict",
        "artifact_dir",
        "cases_run",
        "pass_count",
        "fail_count",
        "stage_timing_summary",
        "lifecycle_events_path",
        "lifecycle_heartbeat_path",
        "command_line",
        "started_at",
        "finished_at",
        "port",
        "source_fingerprint",
        "correctness_fingerprint",
        "diagnostic_fingerprint",
        "verifier_runtime_fingerprint",
        "phase_timing_contract",
        "product_visible_contradiction_proven",
    )
    for field in required_summary_fields:
        if summary and field not in summary:
            errors.append(
                {
                    "classification": "artifact_contract_missing_required_field",
                    "field": field,
                    "message": f"run_summary.json is missing required field: {field}",
                }
            )
    verdict = str(summary.get("verdict") or "")
    if verdict and verdict != "PASS" and not summary.get("failure_classification"):
        errors.append(
            {
                "classification": "artifact_contract_missing_failure_classification",
                "field": "failure_classification",
                "message": "Non-PASS replay summary must include a failure classification.",
            }
        )
    timing_contract = summary.get("phase_timing_contract") if isinstance(summary.get("phase_timing_contract"), dict) else {}
    if summary and not timing_contract:
        errors.append(
            {
                "classification": "artifact_contract_missing_phase_timing_contract",
                "field": "phase_timing_contract",
                "message": "Replay summary must include explicit phase timings or phase_not_reached markers.",
            }
        )
    warnings.extend(timing_budget_warnings(summary.get("stage_timing_summary"), artifact_dir=artifact))
    return {
        "status": "PASS" if not errors else "FAIL",
        "artifact_dir": str(artifact),
        "contract_version": ARTIFACT_CONTRACT_VERSION,
        "required_files": file_status,
        "errors": errors,
        "warnings": warnings,
        "failure_classification": errors[0]["classification"] if errors else "",
    }


def validate_artifact_payload(payload: dict[str, Any], *, required_failure: bool = False) -> dict[str, Any]:
    artifact = Path(str(payload.get("artifact_dir") or ""))
    temp = artifact if artifact else Path(".")
    summary = enrich_run_summary(
        dict(payload),
        artifact_dir=temp,
        command_line=str(payload.get("command_line") or "canary"),
        port=_as_int(payload.get("port")),
        started_at=str(payload.get("started_at") or "canary-start"),
        finished_at=str(payload.get("finished_at") or "canary-finish"),
        replay_source=payload.get("replay_source"),
    )
    errors = []
    if required_failure and summary.get("verdict") == "PASS":
        errors.append(
            {
                "classification": "artifact_contract_expected_failure_payload",
                "message": "Canary payload was expected to represent a rejected condition.",
            }
        )
    if summary.get("verdict") != "PASS" and not summary.get("failure_classification"):
        errors.append(
            {
                "classification": "artifact_contract_missing_failure_classification",
                "message": "Non-PASS payload must include failure classification.",
            }
        )
    if summary.get("verdict") == "PASS" and summary.get("product_visible_contradiction_proven"):
        errors.append(
            {
                "classification": "artifact_contract_contradictory_green_payload",
                "message": "PASS payload cannot also mark a product-visible contradiction as proven.",
            }
        )
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "summary": summary}
