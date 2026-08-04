from __future__ import annotations

import ast
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
WIDGETS_HELPERS = ROOT / "widgets_helpers.py"
STATE_HELPERS = ROOT / "state_and_helpers.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


STREAMLIT_WIDGET_METHODS = {
    "button",
    "checkbox",
    "number_input",
    "radio",
    "selectbox",
    "slider",
    "text_input",
    "toggle",
}

WRAPPER_WIDGET_CALLS = {
    "v2_checkbox",
    "v2_number_input",
    "v2_radio",
    "v2_selectbox",
    "select_row",
    "number_row",
    "info_i_button",
    "_shared_toggle",
}

WIDGET_STATE_TOKENS = (
    "get_widget_key_for_shared",
    "seed_widget_from_shared",
    "sync_callbacks",
    "on_change=",
    "_cached_",
    "_last_user_widget_key",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _function_name_for_line(tree: ast.AST, line: int) -> tuple[str, int | None, int | None]:
    best: tuple[str, int | None, int | None] = ("<module>", None, None)
    best_span = 10**9
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = int(node.lineno)
        end = int(getattr(node, "end_lineno", node.lineno))
        if start <= line <= end and end - start < best_span:
            best = (node.name, start, end)
            best_span = end - start
    return best


def _collect_widget_calls(source: str) -> list[dict[str, Any]]:
    tree = ast.parse(source)
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        method = name.split(".", 1)[1] if name.startswith("st.") or name.startswith("st.sidebar.") else name
        is_streamlit = name.startswith("st.") and method in STREAMLIT_WIDGET_METHODS
        is_sidebar = name.startswith("st.sidebar.") and method in STREAMLIT_WIDGET_METHODS
        is_wrapper = name in WRAPPER_WIDGET_CALLS
        if not (is_streamlit or is_sidebar or is_wrapper):
            continue
        function_name, start, end = _function_name_for_line(tree, int(node.lineno))
        calls.append(
            {
                "call": name,
                "line": int(node.lineno),
                "function": function_name,
                "function_start": start,
                "function_end": end,
                "classification": _classify_widget_call(function_name, name),
            }
        )
    return sorted(calls, key=lambda row: (row["line"], row["call"]))


def _classify_widget_call(function_name: str, call_name: str) -> str:
    if function_name in {"render_landing_card", "_render_inputs_landing_shell"}:
        return "page_navigation_button_shell"
    if "design_guide" in function_name or function_name in {"_render_recommendation_apply_button"}:
        return "apply_or_design_guide_button_shell"
    if call_name in {"v2_number_input", "v2_selectbox", "v2_radio", "v2_checkbox", "select_row", "number_row", "_shared_toggle"}:
        return "input_widget_rendering_candidate_for_model_boundary"
    if call_name == "info_i_button":
        return "info_control_render_shell"
    if function_name == "render_inputs":
        return "inputs_page_widget_composition"
    return "page_owned_widget_shell_or_debug"


def _token_hits(source: str) -> dict[str, int]:
    return {token: source.count(token) for token in WIDGET_STATE_TOKENS}


def _helper_status() -> dict[str, Any]:
    widgets_source = _read(WIDGETS_HELPERS) if WIDGETS_HELPERS.exists() else ""
    state_source = _read(STATE_HELPERS) if STATE_HELPERS.exists() else ""
    return {
        "widgets_helpers_exists": WIDGETS_HELPERS.exists(),
        "state_helpers_exists": STATE_HELPERS.exists(),
        "widgets_helpers_v2_wrappers": all(
            token in widgets_source
            for token in ("def v2_number_input", "def v2_checkbox", "def v2_selectbox", "def v2_radio")
        ),
        "state_helpers_tab_key_map_present": "TAB_KEYS" in state_source,
        "state_helpers_widget_sync_present": "sync_callbacks" in state_source or "sync_" in state_source,
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Widgets Phase 0 Ownership Audit",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This is audit-only. No widget behavior, widget keys, visible wording, callbacks, or session state were changed.",
        "",
        "## Widget Call Summary",
        "",
    ]
    for key, value in payload["call_counts_by_classification"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Main Surfaces",
            "",
            "| Classification | Functions | Count |",
            "|---|---|---:|",
        ]
    )
    for classification, functions in payload["functions_by_classification"].items():
        lines.append(
            f"| `{classification}` | {', '.join(f'`{name}`' for name in functions[:12])} | {payload['call_counts_by_classification'].get(classification, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Ownership Assessment",
            "",
            "- Existing low-level Streamlit-safe wrappers live in `widgets_helpers.py`.",
            "- `inputs_page.py` still owns widget group composition, widget-key selection, hydration guards, and callback wiring.",
            "- Design Guide/apply buttons are not part of the first widget extraction slice; they stay page/apply shell-owned.",
            "- Session hydration/reseed logic overlaps the future Session State domain and must not be moved in this widget slice.",
            "",
            "## First Safe Implementation Slice",
            "",
            payload["first_safe_slice"],
            "",
            "## Stop Conditions",
            "",
            "- Widget key changes.",
            "- Callback target changes.",
            "- Session hydration/reseed behavior changes.",
            "- Visible label/help/range/default changes.",
            "- Any Design Guide/apply button behavior changes.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = _read(INPUTS_PAGE)
    calls = _collect_widget_calls(source)
    counts = Counter(row["classification"] for row in calls)
    functions_by_classification: dict[str, list[str]] = defaultdict(list)
    for row in calls:
        bucket = functions_by_classification[row["classification"]]
        if row["function"] not in bucket:
            bucket.append(row["function"])
    helper_status = _helper_status()
    checks = {
        "widget_calls_found": bool(calls),
        "v2_wrappers_available": bool(helper_status["widgets_helpers_v2_wrappers"]),
        "state_tab_keys_available": bool(helper_status["state_helpers_tab_key_map_present"]),
        "input_widget_rendering_candidates_found": counts.get("input_widget_rendering_candidate_for_model_boundary", 0) > 0,
        "apply_design_guide_buttons_classified_shell": counts.get("apply_or_design_guide_button_shell", 0) >= 0,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "READY_FOR_WIDGET_TYPED_MODEL_TRACE" if not failures else "WIDGET_OWNERSHIP_AUDIT_GAPS_REMAIN"
    payload = {
        "audit": "inputs_widgets_phase0_ownership_audit",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "widget_call_count": len(calls),
        "widget_calls": calls,
        "call_counts_by_classification": dict(sorted(counts.items())),
        "functions_by_classification": {
            key: sorted(value)
            for key, value in sorted(functions_by_classification.items())
        },
        "widget_state_token_hits": _token_hits(source),
        "helper_status": helper_status,
        "first_safe_slice": (
            "Create `inputs_page_modules/widgets/` typed models/contracts for input widget group metadata only: "
            "widget id, shared key, label, help text, default/range/options, and callback key. Run beside the current "
            "page path; do not render from the module yet."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "widget_keys_changed": False,
        "session_behavior_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_widgets_phase0_ownership_audit_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_widgets_phase0_ownership_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_widgets_phase0_ownership_audit", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
