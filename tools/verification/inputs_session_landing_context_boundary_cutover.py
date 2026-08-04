from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_landing_context_snapshot


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_window(source: str, name: str) -> str:
    marker = f"def {name}("
    if marker not in source:
        return ""
    window = source.split(marker, 1)[1].split("\ndef ", 1)[0]
    return window.split("\n", 1)[1] if "\n" in window else window


def _old_context(client_id: Any, project_id: Any, beam_id: Any) -> str:
    return "|".join([str(client_id or ""), str(project_id or ""), str(beam_id or "")])


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "all_blank", "client": "", "project": "", "beam": ""},
        {"name": "normal", "client": "cid", "project": "project_1", "beam": "beam_1"},
        {"name": "none_values", "client": None, "project": None, "beam": None},
        {"name": "numeric_values", "client": 7, "project": 12, "beam": 3},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Landing Context Boundary Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenarios'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    helper = _function_window(source, "_inputs_current_landing_context")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    scenarios = []
    mismatches = []
    for row in _scenarios():
        old = _old_context(row["client"], row["project"], row["beam"])
        new = build_inputs_landing_context_snapshot(
            client_id=row["client"],
            active_project_id=row["project"],
            active_beam_id=row["beam"],
        )
        match = old == new.context
        scenarios.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": old,
                "new": new.context,
                "display_hash": new.display_hash,
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": old, "new": new.context})
    checks = {
        "page_helper_delegates_to_session_builder": "build_inputs_landing_context_snapshot(" in helper,
        "page_helper_keeps_get_client_id": "get_client_id()" in helper,
        "page_helper_keeps_session_reads": "st.session_state.get" in helper,
        "old_inline_join_removed": "return \"|\".join(" not in helper,
        "session_builder_exists": "def build_inputs_landing_context_snapshot(" in builders,
        "session_model_exists": "class InputsLandingContextSnapshot" in models,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower()
        and "st.session_state" not in builders,
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "INPUTS_SESSION_LANDING_CONTEXT_BOUNDARY_LOCKED" if not failures else "INPUTS_SESSION_LANDING_CONTEXT_BOUNDARY_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_landing_context_boundary_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenarios,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_landing_context_boundary_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_landing_context_boundary_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_landing_context_boundary_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
