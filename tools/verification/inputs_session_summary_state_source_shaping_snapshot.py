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
SESSION_ROOT = ROOT / "inputs_page_modules" / "session"
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


def _legacy_overlay(
    *,
    base: dict[str, Any],
    source: dict[str, Any],
    input_tab_keys: dict[str, str],
    skip_shared_keys: set[str],
    skip_longitudinal_keys: set[str],
    skip_prefixes: tuple[str, ...],
    deferred_overlay_keys: set[str],
    shared_only_mode: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    working = dict(base)
    overlay_applied: dict[str, dict[str, Any]] = {}
    if not shared_only_mode:
        for shared_key, widget_key in input_tab_keys.items():
            sk = str(shared_key or "")
            wk = str(widget_key or "")
            if not sk or not wk.startswith("inputs_"):
                continue
            if (
                sk.startswith("_")
                or sk in skip_shared_keys
                or sk in skip_longitudinal_keys
                or sk.startswith(skip_prefixes)
            ):
                continue
            if sk in deferred_overlay_keys:
                continue
            if wk not in source:
                continue
            wval = source.get(wk)
            if isinstance(wval, (dict, list, tuple, set)):
                continue
            bval = base.get(sk)
            if bval != wval:
                overlay_applied[sk] = {"from": bval, "to": wval, "widget_key": wk}
            working[sk] = wval
    return working, overlay_applied


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Summary State Source Shaping Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This verifier proves the new session module source-shaping builder matches the page-owned scalar widget overlay logic for `_resolved_inputs_summary_state`.",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Only pure source shaping and scalar widget overlay planning are represented.",
            "- The live page delegates the scalar source-shaping overlay loop to `inputs_page_modules.session`.",
            "- Shear mirror overlay, derived recompute, normalized shear truth overlay, UX probe, and session writes remain in `inputs_page.py`.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _module_inputs_page_free(module_source: str) -> bool:
    return not re.search(r"^\s*(from\s+inputs_page\b|import\s+inputs_page\b)", module_source, re.MULTILINE)


def _module_apply_callback_free(module_source: str) -> bool:
    return not re.search(r"\b(route_apply|apply_payload)\s*[=(]", module_source) and "on_change" not in module_source


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    helper_window = _function_window(page, "_resolved_inputs_summary_state")
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module_combined = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    from inputs_page_modules.session import build_inputs_summary_source_shaping_snapshot

    base = {
        "b": 300.0,
        "D": 600.0,
        "s_lig": 200.0,
        "lig_d": 10.0,
        "lig_legs": 2,
        "bot1_count": 3,
        "actions_mode": "design",
        "_solver_result": "stale",
    }
    source = {
        "inputs_b": 350.0,
        "inputs_D": 600.0,
        "inputs_s_lig": 125.0,
        "inputs_lig_d": 12.0,
        "inputs_lig_legs": 4,
        "inputs_bot1_count": 5,
        "inputs_custom_dict": {"skip": True},
    }
    input_tab_keys = {
        "b": "inputs_b",
        "D": "inputs_D",
        "s_lig": "inputs_s_lig",
        "lig_d": "inputs_lig_d",
        "lig_legs": "inputs_lig_legs",
        "bot1_count": "inputs_bot1_count",
        "_solver_result": "inputs_solver_result",
        "custom_dict": "inputs_custom_dict",
    }
    skip_shared = {"_solver_result"}
    skip_longitudinal = {"bot1_count"}
    skip_prefixes = ("bot_row_", "top_row_")
    deferred = {"s_lig", "lig_d", "lig_legs"}
    legacy_working, legacy_overlay = _legacy_overlay(
        base=base,
        source=source,
        input_tab_keys=input_tab_keys,
        skip_shared_keys=skip_shared,
        skip_longitudinal_keys=skip_longitudinal,
        skip_prefixes=skip_prefixes,
        deferred_overlay_keys=deferred,
        shared_only_mode=False,
    )
    module_snapshot = build_inputs_summary_source_shaping_snapshot(
        base_state=base,
        source_state=source,
        input_tab_keys=input_tab_keys,
        skip_shared_keys=skip_shared,
        skip_longitudinal_keys=skip_longitudinal,
        skip_prefixes=skip_prefixes,
        deferred_overlay_keys=deferred,
        shared_only_mode=False,
        shared_only_reason="normal_overlay",
    )
    shared_only_snapshot = build_inputs_summary_source_shaping_snapshot(
        base_state=base,
        source_state=source,
        input_tab_keys=input_tab_keys,
        skip_shared_keys=skip_shared,
        skip_longitudinal_keys=skip_longitudinal,
        skip_prefixes=skip_prefixes,
        deferred_overlay_keys=deferred,
        shared_only_mode=True,
        shared_only_reason="pending_inputs_apply_refresh",
    )
    checks = {
        "builder_exported": "build_inputs_summary_source_shaping_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsSummarySourceShapingSnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_summary_source_shaping_snapshot(" in module_sources.get("builders.py", ""),
        "page_imports_builder": "build_inputs_summary_source_shaping_snapshot" in page,
        "page_delegated_wiring_present": "inputs_summary_source_shaping_delegated" in helper_window
        and "live_page_cutover=True" in helper_window
        and "working = dict(_summary_source_shape.working_state)" in helper_window
        and "overlay_applied: dict[str, dict] = dict(_summary_source_shape.overlay_applied)" in helper_window,
        "page_authoritative_loop_deleted": "for shared_key, widget_key in INPUTS_PAGE_TAB_KEYS.items()" not in helper_window
        and "working[sk] = wval" not in helper_window
        and "inputs_summary_source_shaping_parity_error" not in helper_window,
        "module_working_matches_legacy": module_snapshot.working_state == legacy_working,
        "module_overlay_matches_legacy": module_snapshot.overlay_applied == legacy_overlay,
        "shared_only_suppresses_overlays": shared_only_snapshot.working_state == base
        and shared_only_snapshot.overlay_applied == {},
        "deferred_shear_keys_not_overlaid": "s_lig" not in module_snapshot.overlay_applied
        and "lig_d" not in module_snapshot.overlay_applied
        and "lig_legs" not in module_snapshot.overlay_applied,
        "longitudinal_keys_not_overlaid": "bot1_count" not in module_snapshot.overlay_applied,
        "dict_values_not_overlaid": "custom_dict" not in module_snapshot.overlay_applied,
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": _module_inputs_page_free(module_combined),
        "module_no_session_mutation": "st.session_state" not in module_combined
        and ".session_state" not in module_combined,
        "module_no_apply_or_callbacks": _module_apply_callback_free(executable_module_combined),
        "module_does_not_move_derived_recompute": "_recompute_summary_local_derived_fields" not in module_combined,
        "module_does_not_move_shear_truth_overlay": "_overlay_current_normalized_shear_truth" not in module_combined,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_SUMMARY_SOURCE_SHAPING_DELEGATED" if not failures else "SESSION_SUMMARY_SOURCE_SHAPING_DELEGATION_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_summary_state_source_shaping_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "legacy_overlay": legacy_overlay,
        "module_overlay": module_snapshot.overlay_applied,
        "module_display_hash": module_snapshot.display_hash,
        "live_page_cutover": True,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "derived_recompute_moved": False,
        "normalized_shear_truth_overlay_moved": False,
        "next_safe_slice": "prove deadness for any remaining source-shaping fallback consumers, then lock this sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_state_source_shaping_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_state_source_shaping_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_state_source_shaping_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
