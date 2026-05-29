from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.verification.artifact_contract import (  # noqa: E402
    classify_failure_family,
    enrich_run_summary,
    validate_artifact_payload,
    validate_replay_artifact,
)


ARTIFACT_ROOT = REPO / "artifacts" / "verification"


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, default=str) for row in rows) + "\n", encoding="utf-8")


def _make_good_artifact(root: Path) -> Path:
    artifact = root / "known_good_replay_artifact"
    artifact.mkdir(parents=True, exist_ok=True)
    started = "2026-05-23T00:00:00+0000"
    summary = {
        "verdict": "PASS",
        "exit_code": 0,
        "artifact_dir": str(artifact),
        "replay_source": "artifacts/verification/canaries/known_good.json",
        "cases_run": 1,
        "pass_count": 1,
        "fail_count": 0,
        "stage_timing_summary": {
            "streamlit_ready_ms": 100,
            "page_route_ready_ms": 50,
            "widget_sync_ms": 200,
            "replay_apply_ms": 300,
            "post_apply_settle_ms": 400,
            "browser_probe_publish_ms": 100,
            "timeline_capture_ms": 100,
            "page_cycle_check_ms": 500,
        },
        "lifecycle_events_path": str(artifact / "lifecycle_events.jsonl"),
        "lifecycle_heartbeat_path": str(artifact / "lifecycle_heartbeat.json"),
    }
    summary = enrich_run_summary(
        summary,
        artifact_dir=artifact,
        command_line="python tools/verification/verifier_self_check.py",
        port=9301,
        started_at=started,
        finished_at="2026-05-23T00:00:01+0000",
    )
    _write_json(artifact / "run_summary.json", summary)
    _write_jsonl(
        artifact / "lifecycle_events.jsonl",
        [
            {"timestamp": started, "event": "stage_start", "stage": "canary"},
            {"timestamp": "2026-05-23T00:00:01+0000", "event": "stage_success", "stage": "canary"},
        ],
    )
    _write_json(artifact / "lifecycle_heartbeat.json", {"timestamp": "2026-05-23T00:00:01+0000", "current_stage": "done"})
    return artifact


def _make_missing_field_artifact(root: Path) -> Path:
    artifact = root / "missing_required_field_artifact"
    artifact.mkdir(parents=True, exist_ok=True)
    _write_json(
        artifact / "run_summary.json",
        {
            "verdict": "PASS",
            "artifact_dir": str(artifact),
            "cases_run": 1,
            "pass_count": 1,
            "fail_count": 0,
        },
    )
    _write_jsonl(artifact / "lifecycle_events.jsonl", [{"event": "stage_start"}])
    _write_json(artifact / "lifecycle_heartbeat.json", {"current_stage": "done"})
    return artifact


def _check(name: str, condition: bool, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if condition else "FAIL",
        "details": details,
    }


def run_self_check(*, artifact_root: Path) -> tuple[int, dict[str, Any]]:
    root = artifact_root / f"verifier_self_check_{_stamp()}"
    root.mkdir(parents=True, exist_ok=True)

    good_artifact = _make_good_artifact(root)
    missing_artifact = _make_missing_field_artifact(root)

    good_result = validate_replay_artifact(good_artifact)
    missing_result = validate_replay_artifact(missing_artifact)
    contradictory_result = validate_artifact_payload(
        {
            "verdict": "PASS",
            "artifact_dir": str(root / "contradictory_green"),
            "cases_run": 1,
            "pass_count": 1,
            "fail_count": 0,
            "product_visible_contradiction_proven": True,
            "stage_timing_summary": {"page_cycle_check_ms": 1},
            "command_line": "canary",
            "port": 9301,
        }
    )
    timeout_result = validate_artifact_payload(
        {
            "verdict": "ERROR",
            "artifact_dir": str(root / "timeout"),
            "cases_run": 0,
            "pass_count": 0,
            "fail_count": 1,
            "failure_classification": "page_cycle_navigation_timeout",
            "stage_timing_summary": {},
            "command_line": "canary",
            "port": 9301,
        },
        required_failure=True,
    )
    families = {
        "product issue": classify_failure_family("design_guide_card_button_colour_mismatch"),
        "verifier-readiness": classify_failure_family("inputs_content_not_ready_before_browser_probe"),
        "runtime-orchestration": classify_failure_family("streamlit_runtime_reconnect_during_verification"),
        "page-cycle-render": classify_failure_family("page_cycle_navigation_timeout"),
        "phase_not_reached": classify_failure_family("phase_not_reached"),
    }

    checks = [
        _check("known_good_artifact_accepted", good_result.get("status") == "PASS", good_result),
        _check("missing_required_field_rejected", missing_result.get("status") == "FAIL", missing_result),
        _check("contradictory_green_rejected", contradictory_result.get("status") == "FAIL", contradictory_result),
        _check(
            "timeout_classification_emitted",
            timeout_result.get("status") == "PASS"
            and timeout_result.get("summary", {}).get("classification_family") == "page-cycle-render",
            timeout_result,
        ),
        _check(
            "classification_families_distinct",
            families == {
                "product issue": "product issue",
                "verifier-readiness": "verifier-readiness",
                "runtime-orchestration": "runtime-orchestration",
                "page-cycle-render": "page-cycle-render",
                "phase_not_reached": "phase_not_reached",
            },
            {"families": families},
        ),
    ]
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    payload = {
        "status": status,
        "generated_at": _stamp(),
        "artifact_dir": str(root),
        "checks": checks,
        "repeatability_command": (
            'python tools/browser_live_design_guide_fuzz_verifier.py --replay-case '
            '"artifacts/verification/live_fuzz/overnight_failure_exports_2026-05-08T23-25-14/f005/failure_case.json" '
            "--port 9301"
        ),
        "repeatability_fields_to_compare": [
            "verdict",
            "failure_classification",
            "correctness_fingerprint.fingerprint",
            "diagnostic_fingerprint.fingerprint",
            "verifier_runtime_fingerprint.fingerprint",
            "stage_timing_summary.replay_apply_ms",
            "stage_timing_summary.post_apply_settle_ms",
            "stage_timing_summary.page_cycle_check_ms",
        ],
    }
    _write_json(root / "verifier_self_check_summary.json", payload)
    print(json.dumps(payload, indent=2, default=str))
    return (0 if status == "PASS" else 1), payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run verifier artifact-contract canaries.")
    parser.add_argument("--artifact-root", default=str(ARTIFACT_ROOT))
    args = parser.parse_args(argv)
    code, _ = run_self_check(artifact_root=Path(args.artifact_root))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
