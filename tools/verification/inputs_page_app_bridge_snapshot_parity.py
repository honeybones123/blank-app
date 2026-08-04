from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _run_shared_snapshot_case(session_values: dict[str, Any]) -> dict[str, Any]:
    import inputs_page_route_coordinators as route
    import inputs_page_app_contract_bridge as bridge

    originals = {"route_st": route.st, "bridge_st": bridge.st}
    try:
        route.st = SimpleNamespace(session_state=dict(session_values))
        bridge.st = SimpleNamespace(session_state=dict(session_values))
        route_value = route._shared_state_snapshot()
        bridge_value = bridge._shared_state_snapshot_for_summary_bridge()
    finally:
        route.st = originals["route_st"]
        bridge.st = originals["bridge_st"]
    return {"match": route_value == bridge_value, "route": route_value, "bridge": bridge_value}


def _run_guidance_snapshot_case(source_state: dict[str, Any] | None) -> dict[str, Any]:
    import inputs_page_route_coordinators as route
    import inputs_page_app_contract_bridge as bridge

    route_value = route._guidance_state_snapshot(source_state)
    bridge_value = bridge._guidance_state_snapshot_for_summary_bridge(source_state)
    return {"match": route_value == bridge_value, "route": route_value, "bridge": bridge_value}


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    shared_cases = {
        "empty_session_defaults": _run_shared_snapshot_case({}),
        "session_overrides": _run_shared_snapshot_case(
            {
                "b": 350,
                "D": 650,
                "fc": 50,
                "not_shared": "ignored",
            }
        ),
    }
    guidance_cases = {
        "none_state_defaults": _run_guidance_snapshot_case(None),
        "strips_stale_keys": _run_guidance_snapshot_case(
            {
                "b": 350,
                "pending_recommendation": {"stale": True},
                "_solver_result": {"stale": True},
                "_bend_pack": {"rows": []},
                "shear_truth_status": "STALE",
                "final_shear_truth_resolved": False,
                "published_result_spacing_mm": 999,
                "custom_key_survives": "yes",
            }
        ),
    }
    checks = {
        "all_shared_snapshots_match_legacy": all(case["match"] for case in shared_cases.values()),
        "all_guidance_snapshots_match_legacy": all(
            case["match"] for case in guidance_cases.values()
        ),
        "stale_keys_are_removed": all(
            key not in guidance_cases["strips_stale_keys"]["bridge"]
            for key in (
                "pending_recommendation",
                "_solver_result",
                "_bend_pack",
                "shear_truth_status",
                "final_shear_truth_resolved",
                "published_result_spacing_mm",
            )
        ),
    }
    bridge_source = (ROOT / "inputs_page_app_contract_bridge.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    checks["snapshot_helpers_do_not_delegate_to_old_page"] = all(
        needle not in bridge_source
        for needle in (
            "_legacy_inputs_page._shared_state_snapshot",
            "_legacy_inputs_page._guidance_state_snapshot",
        )
    )
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "audit": "inputs_page_app_bridge_snapshot_parity",
        "timestamp": timestamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "shared_cases": shared_cases,
        "guidance_cases": guidance_cases,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"inputs_page_app_bridge_snapshot_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_app_bridge_snapshot_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page App Bridge Snapshot Parity",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *(f"- `{name}`: `{passed}`" for name, passed in checks.items()),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
