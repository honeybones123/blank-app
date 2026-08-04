"""Lock parallel family-fuzz run_end correlation to the clicked CTA updates."""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.helpers import browser_one_click_regression as trace_owner  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"


def _event(
    event: str,
    run_id: str,
    timestamp_ms: int,
    updates: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "event": event,
        "run_id": run_id,
        "timestamp_ms": timestamp_ms,
        "source": "primary_apply_button",
    }
    if event == "run_end":
        payload["data"] = {
            "status": "pass",
            "final_updates": dict(updates or {}),
            "last_apply_route": {
                "applied_updates": dict(updates or {}),
            },
        }
    return payload


def main() -> int:
    foreign_updates = {"D": 925.0, "b": 500.0, "s_lig": 125.0}
    clicked_updates = {"lig_legs": 6, "s_lig": 100.0}
    rows = [
        _event("run_start", "combined-run", 1001),
        _event("run_end", "combined-run", 1002, foreign_updates),
        _event("run_start", "shear-run", 1003),
        _event("run_end", "shear-run", 1004, clicked_updates),
    ]
    original_path = trace_owner.TRACER_PATH
    with tempfile.TemporaryDirectory() as temp_dir:
        trace_path = Path(temp_dir) / "parallel-trace.jsonl"
        trace_path.write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
        trace_owner.TRACER_PATH = trace_path
        try:
            correlated, _ = trace_owner._wait_for_run_end(
                0,
                timeout_s=1.0,
                start_time_ms=1000,
                expected_updates=clicked_updates,
            )
            legacy, _ = trace_owner._wait_for_run_end(
                0,
                timeout_s=1.0,
                start_time_ms=1000,
            )
        finally:
            trace_owner.TRACER_PATH = original_path

    checks = {
        "correlated_wait_selects_clicked_shear_run": (
            isinstance(correlated, dict)
            and correlated.get("run_id") == "shear-run"
        ),
        "correlated_wait_rejects_foreign_combined_run": (
            isinstance(correlated, dict)
            and correlated.get("run_id") != "combined-run"
        ),
        "legacy_uncorrelated_behavior_preserved": (
            isinstance(legacy, dict)
            and legacy.get("run_id") == "combined-run"
        ),
        "selected_run_contains_requested_updates": trace_owner._run_end_contains_expected_updates(
            dict(correlated or {}),
            clicked_updates,
        ),
    }
    payload = {
        "schema": "family_fuzz.parallel_trace_correlation_contract.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "foreign_updates": foreign_updates,
        "clicked_updates": clicked_updates,
        "selected_run_id": (correlated or {}).get("run_id"),
        "legacy_selected_run_id": (legacy or {}).get("run_id"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    artifact = ARTIFACT_DIR / f"family_fuzz_parallel_trace_correlation_contract_{stamp}.json"
    artifact.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{payload['status']}: {artifact}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
