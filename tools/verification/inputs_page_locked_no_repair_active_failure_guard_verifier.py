from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_locked_no_repair_active_failure_guard_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_locked_no_repair_active_failure_guard_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _run_case(
        name: str,
        *,
        active_keys: set[str],
        locked: bool,
        debug: dict | None = None,
    ) -> tuple[dict, set]:
        result = inputs_page.render_design_guide_locked_no_repair_active_failure_guard(
            guidance_debug=dict(debug or {}),
            active_fail_keys_for_render=set(active_keys),
            primary_guard_is_locked_no_repair=locked,
        )
        cases.append(
            {
                "name": name,
                "input_active_keys": sorted(active_keys),
                "locked": locked,
                "result_debug": dict(result[0]),
                "result_active_keys": sorted(result[1]),
            }
        )
        return result

    active_locked = _run_case(
        "active_locked_no_repair_preserves_locked_publication",
        active_keys={"bending"},
        locked=True,
    )
    if active_locked[1] != set():
        failures.append(f"active_locked_keys_not_cleared:{active_locked[1]}")
    if active_locked[0].get("active_failure_visible_truth_suppressed_by_locked_no_repair") is not True:
        failures.append(f"active_locked_suppression_flag_missing:{active_locked[0]}")
    if active_locked[0].get("locked_no_repair_render_publication_preserved") is not True:
        failures.append(f"active_locked_publication_flag_missing:{active_locked[0]}")

    active_unlocked = _run_case(
        "active_unlocked_noop",
        active_keys={"bending"},
        locked=False,
        debug={"existing": True},
    )
    if active_unlocked[1] != {"bending"}:
        failures.append(f"active_unlocked_keys_changed:{active_unlocked[1]}")
    if active_unlocked[0] != {"existing": True}:
        failures.append(f"active_unlocked_debug_changed:{active_unlocked[0]}")

    inactive_locked = _run_case(
        "inactive_locked_noop",
        active_keys=set(),
        locked=True,
        debug={"existing": True},
    )
    if inactive_locked[1] != set():
        failures.append(f"inactive_locked_keys_changed:{inactive_locked[1]}")
    if inactive_locked[0] != {"existing": True}:
        failures.append(f"inactive_locked_debug_changed:{inactive_locked[0]}")

    payload = {
        "verifier": "inputs_page_locked_no_repair_active_failure_guard_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Locked No Repair Active Failure Guard Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}` active={case['result_active_keys']}" for case in cases),
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
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
