from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.design_guide import main_panel_status


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "design_guide" / "main_panel_status.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


class _FakeSt:
    def __init__(self, session_state: dict[str, Any], events: list[dict[str, Any]]) -> None:
        self.session_state = session_state
        self._events = events

    def caption(self, text: str) -> None:
        self._events.append({"kind": "caption", "text": str(text)})

    def warning(self, text: str) -> None:
        self._events.append({"kind": "warning", "text": str(text)})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _run_status_case(session_state: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    sync_calls: list[dict[str, Any]] = []

    def ux_probe_record(name: str, **kwargs: Any) -> None:
        events.append({"kind": "probe", "name": name, "kwargs": dict(kwargs)})

    main_panel_status.bind_main_panel_status_dependencies(
        {
            "AUTO_DESIGN_REQUEST_SOURCE_KEY": "_auto_design_request_source",
            "DESIGN_GUIDE_DEBUG_BUNDLE_KEY": "_design_guide_debug_bundle",
            "_sync_auto_design_invoke_pending_field": lambda: sync_calls.append({"called": True}),
            "st": _FakeSt(session_state, events),
            "ux_probe_record": ux_probe_record,
        }
    )
    main_panel_status._render_auto_design_main_panel_status()
    return {"events": events, "sync_calls": sync_calls}


def _case_results() -> list[dict[str, Any]]:
    cases = [
        {
            "name": "running_status_caption",
            "result": _run_status_case({"auto_design_status": "running"}),
            "expected_events": [
                {"kind": "caption", "text": "Auto-design is running on the current inputs."}
            ],
            "expected_sync": [],
        },
        {
            "name": "rejected_status_warning",
            "result": _run_status_case(
                {
                    "auto_design_status": "rejected",
                    "_solver_result": {"user_visible_commit_rejection": "Rejected for test"},
                }
            ),
            "expected_events": [{"kind": "warning", "text": "Rejected for test"}],
            "expected_sync": [],
        },
        {
            "name": "no_action_suppresses_legacy_reason_and_captions_rejection_summary",
            "result": _run_status_case(
                {
                    "auto_design_status": "no_action",
                    "_solver_result": {
                        "user_visible_no_action_reason": "legacy reason",
                        "user_visible_rejection_summary": "No safe action",
                    },
                }
            ),
            "expected_events": [
                {
                    "kind": "probe",
                    "name": "design_guide_legacy_no_action_info_banner_suppressed",
                    "kwargs": {"meta": {"source": "_solver_result"}},
                },
                {"kind": "caption", "text": "No safe action"},
            ],
            "expected_sync": [],
        },
        {
            "name": "passive_bundle_reason_is_suppressed_with_probe",
            "result": _run_status_case(
                {
                    "_design_guide_debug_bundle": {
                        "user_visible_no_action_reason": "passive",
                        "stop_reason": "budget",
                    }
                }
            ),
            "expected_events": [
                {
                    "kind": "probe",
                    "name": "design_guide_legacy_no_action_info_banner_suppressed",
                    "kwargs": {
                        "meta": {
                            "source": "_design_guide_debug_bundle",
                            "has_stop_reason": True,
                        }
                    },
                }
            ],
            "expected_sync": [],
        },
        {
            "name": "idle_reason_captions_with_request_source",
            "result": _run_status_case(
                {
                    "auto_design_idle_reason": "deferred_solver_running",
                    "_auto_design_request_source": "button",
                }
            ),
            "expected_events": [
                {
                    "kind": "caption",
                    "text": "Auto-design deferred: solver already running. (request: button)",
                }
            ],
            "expected_sync": [{"called": True}],
        },
        {
            "name": "cancelled_reason_does_not_append_request_source",
            "result": _run_status_case(
                {
                    "auto_design_idle_reason": "request_cancelled_by_guidance_commit",
                    "_auto_design_request_source": "button",
                }
            ),
            "expected_events": [{"kind": "caption", "text": "Auto-design request was cancelled."}],
            "expected_sync": [{"called": True}],
        },
    ]
    return [
        {
            "name": case["name"],
            "passed": case["result"]["events"] == case["expected_events"]
            and case["result"]["sync_calls"] == case["expected_sync"],
            "result": case["result"],
            "expected_events": case["expected_events"],
            "expected_sync": case["expected_sync"],
        }
        for case in cases
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Main Panel Status Extraction",
        "",
        f"## Decision: {payload['decision']}",
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
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    bridge_helper = _function_source(bridge_source, "_render_auto_design_main_panel_status")
    module_helper = _function_source(module_source, "_render_auto_design_main_panel_status")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_render_auto_design_main_panel_status_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 3,
        "bridge_binds_status_dependencies": "_bind_main_panel_status_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_render_auto_design_main_panel_status_extracted()" in bridge_helper,
        "bridge_removed_status_body": "Auto-design is running on the current inputs." not in bridge_helper
        and "deferred_solver_running" not in bridge_helper,
        "module_keeps_status_body": "Auto-design is running on the current inputs." in module_helper
        and "deferred_solver_running" in module_helper,
        "module_has_dependency_binder": "def bind_main_panel_status_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = "INPUTS_PAGE_MAIN_PANEL_STATUS_EXTRACTION_LOCKED" if not failures else "GAPS_REMAIN"
    payload = {
        "audit": "inputs_page_main_panel_status_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_main_panel_status_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_main_panel_status_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_main_panel_status_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
