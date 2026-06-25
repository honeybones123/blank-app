"""Speed check for SHEAR_FAIL_GOVERNS product-path ownership."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = REPO / "artifacts" / "performance"
SCENARIO = "scenario_c1_pure_shear_underdesign_repair"


def _latest_gate_report(started_at: float) -> Path | None:
    verification_dir = REPO / "artifacts" / "verification"
    reports = sorted(
        verification_dir.glob("design_guide_product_path_gate_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in reports:
        if path.stat().st_mtime >= started_at - 1:
            return path
    return None


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _scenario(report: dict[str, Any]) -> dict[str, Any]:
    for row in report.get("results") or []:
        if isinstance(row, dict) and row.get("name") == SCENARIO:
            return dict(row)
    return {}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    port = "9475"
    if "--port" in argv:
        index = argv.index("--port")
        if index + 1 < len(argv):
            port = argv[index + 1]

    env = dict(os.environ)
    env.pop("CODEX_BROWSER_TEST_MODE", None)
    env["DESIGN_BRAIN_SHEAR_FAIL_FAMILY_ROUTING"] = "1"
    command = [
        sys.executable,
        "tools/verification/design_guide_product_path_gate.py",
        "--port",
        port,
        "--scenario",
        SCENARIO,
    ]
    started_clock = time.perf_counter()
    started_at = time.time()
    completed = subprocess.run(command, cwd=REPO, env=env, text=True, capture_output=True)
    elapsed = time.perf_counter() - started_clock
    gate_path = _latest_gate_report(started_at)
    gate_report = _load_json(gate_path)
    scenario = _scenario(gate_report)
    evidence = dict(scenario.get("evidence") or {})
    final_snapshot = dict(evidence.get("final_snapshot") or {})
    status = "PASS" if completed.returncode == 0 and scenario.get("status") == "PASS" else "FAIL"
    speed = {
        "schema": "shear_fail_governs_speed_check.v1",
        "family": "SHEAR_FAIL_GOVERNS",
        "scenario": SCENARIO,
        "status": status,
        "command": command,
        "returncode": completed.returncode,
        "gate_report": str(gate_path) if gate_path else None,
        "browser_test_mode": env.get("CODEX_BROWSER_TEST_MODE") or "unset",
        "before_timing_seconds": None,
        "after_timing_seconds": round(elapsed, 3),
        "delta_seconds": None,
        "classification": "baseline missing - after timing recorded",
        "approved_or_blocked": "blocked_for_full_completion_until_baseline_exists",
        "design_guide_resolve_time_seconds": round(elapsed, 3),
        "cta_click_rerun_time_seconds": None,
        "first_stable_design_guide_card_time_seconds": round(elapsed, 3),
        "candidate_evaluation_count": evidence.get("candidate_evaluation_count"),
        "page_collapse_or_jump_behaviour": {
            "window_scroll_y": final_snapshot.get("window_scroll_y"),
            "primary_scroll_top": final_snapshot.get("primary_scroll_top"),
            "document_height": final_snapshot.get("document_height"),
            "viewport_height": final_snapshot.get("viewport_height"),
        },
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-4000:],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"shear_fail_governs_speed_check_{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    path.write_text(json.dumps(speed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{speed['status']}: {path}")
    return 0 if speed["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
