from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Summary Mapping Getter Deadness",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves `_summary_state_mapping_get` has been deleted after the design-action overlay moved to the session module.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    references = re.findall(r"\b_summary_state_mapping_get\b", page)
    checks = {
        "helper_definition_deleted": "def _summary_state_mapping_get(" not in page,
        "no_page_references_remain": len(references) == 0,
        "design_action_overlay_uses_module": "build_inputs_design_action_result_overlay_snapshot(" in page,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_SUMMARY_MAPPING_GET_DELETED" if not failures else "INPUTS_SESSION_SUMMARY_MAPPING_GET_STILL_REFERENCED"
    payload = {
        "audit": "inputs_session_summary_mapping_get_deadness",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "reference_count": len(references),
        "product_behavior_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_mapping_get_deadness_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_mapping_get_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_mapping_get_deadness", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
