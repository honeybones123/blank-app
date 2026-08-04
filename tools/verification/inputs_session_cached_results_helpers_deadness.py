from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

HELPERS = (
    "_get_cached_results",
    "_get_results_updated_at",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_present(source: str, name: str) -> bool:
    return f"def {name}(" in source


def _reference_count(source: str, name: str) -> int:
    return len(re.findall(rf"\b{re.escape(name)}\s*\(", source))


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Cached Results Helpers Deadness",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "## Helpers",
        "",
    ]
    for row in payload["helpers"]:
        lines.extend(
            [
                f"### `{row['helper']}`",
                f"- definition present: `{row['definition_present']}`",
                f"- reference count: `{row['reference_count']}`",
                f"- dead: `{row['dead']}`",
                "",
            ]
        )
    if payload["failures"]:
        lines.extend(["## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    helper_rows = []
    failures = []
    for helper in HELPERS:
        present = _function_present(source, helper)
        refs = _reference_count(source, helper)
        dead = (not present and refs == 0) or (present and refs == 1)
        helper_rows.append(
            {
                "helper": helper,
                "definition_present": present,
                "reference_count": refs,
                "dead": dead,
            }
        )
        if not dead:
            failures.append(f"{helper}_still_has_live_references")
    deleted = all(not row["definition_present"] and row["reference_count"] == 0 for row in helper_rows)
    decision = (
        "INPUTS_SESSION_CACHED_RESULTS_HELPERS_DELETED"
        if deleted and not failures
        else "INPUTS_SESSION_CACHED_RESULTS_HELPERS_DEAD_READY_TO_DELETE"
        if not failures
        else "INPUTS_SESSION_CACHED_RESULTS_HELPERS_DEADNESS_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_cached_results_helpers_deadness",
        "timestamp": timestamp,
        "decision": decision,
        "helpers": helper_rows,
        "failures": failures,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_cached_results_helpers_deadness_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_cached_results_helpers_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_cached_results_helpers_deadness", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
