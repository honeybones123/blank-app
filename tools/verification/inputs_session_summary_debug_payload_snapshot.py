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


def _legacy_summary_debug_payload(
    *,
    base: dict[str, Any],
    resolved: dict[str, Any],
    overlay_applied: dict[str, dict[str, Any]],
    shear_overlay_debug: dict[str, Any],
    design_action_result_overlay: dict[str, dict[str, Any]],
    shared_only_mode: bool,
    shared_only_reason: str,
    design_guide_fingerprint: Any,
    subset_keys: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    compact_diffs: dict[str, dict[str, Any]] = {}
    for key in subset_keys:
        if key in overlay_applied:
            compact_diffs[key] = dict(overlay_applied[key])
        elif base.get(key) != resolved.get(key):
            compact_diffs[key] = {"from": base.get(key), "to": resolved.get(key), "widget_key": None}

    debug_payload = {
        "summary_uses_resolved_inputs_state": True,
        "summary_state_source": "shared_only_canonical_state" if shared_only_mode else "shared_plus_inputs_widget_overlay",
        "summary_render_state_source": "lightweight_overlay_state",
        "summary_cache_fp_source": "resolved_inputs_summary_state",
        "summary_shared_vs_widget_diffs": compact_diffs,
        "overlay_count": len(overlay_applied),
        "summary_shared_only_mode": bool(shared_only_mode),
        "summary_shared_only_reason": shared_only_reason,
        "summary_overlay_suppressed": bool(shared_only_mode),
        "shear_widget_overlay_applied": shear_overlay_debug.get("shear_widget_overlay_applied"),
        "shear_widget_overlay_source": shear_overlay_debug.get("shear_widget_overlay_source"),
        "overlay_s_lig": shear_overlay_debug.get("overlay_s_lig"),
        "overlay_lig_d": shear_overlay_debug.get("overlay_lig_d"),
        "overlay_lig_legs": shear_overlay_debug.get("overlay_lig_legs"),
        "summary_shear_widget_overlay_applied": shear_overlay_debug.get("shear_widget_overlay_applied"),
        "summary_overlay_s_lig": shear_overlay_debug.get("overlay_s_lig"),
        "summary_overlay_lig_d": shear_overlay_debug.get("overlay_lig_d"),
        "summary_overlay_lig_legs": shear_overlay_debug.get("overlay_lig_legs"),
        "summary_design_action_result_overlay_count": len(design_action_result_overlay),
        "summary_design_action_result_overlay_keys": list(design_action_result_overlay.keys()),
        "summary_pack_cache_design_guide_fp": design_guide_fingerprint,
        "longitudinal_reo_truth_source": resolved.get("longitudinal_reo_truth_source"),
    }
    return debug_payload, compact_diffs


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Summary Debug Payload Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This snapshot compares module-owned compact debug payload assembly with legacy page semantics and verifies live delegation.",
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
            "- The live page delegates compact `debug_payload` assembly to `inputs_page_modules.session`.",
            "- Session writes, UX probe, derived recompute, normalized shear truth overlay, callbacks, Apply routing, and rendering remain page-owned.",
        ]
    )
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _module_inputs_page_free(module_source: str) -> bool:
    return not re.search(r"^\s*(from\s+inputs_page\b|import\s+inputs_page\b)", module_source, re.MULTILINE)


def _module_apply_routing_free(module_source: str) -> bool:
    return not re.search(r"\b(route_apply|apply_payload)\s*[=(]", module_source)


def _module_rendering_free(module_source: str) -> bool:
    return not (
        re.search(r"(?<![A-Za-z0-9_])st\.", module_source)
        or "streamlit" in module_source
        or re.search(r"\b(render_final|render_card)\s*\(", module_source)
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    page = _read(INPUTS_PAGE)
    summary_window = _function_window(page, "_resolved_inputs_summary_state")
    module_sources = {
        path.name: _read(path)
        for path in SESSION_ROOT.glob("*.py")
    }
    module_combined = "\n".join(module_sources.values())
    executable_module = "\n".join(
        source for name, source in module_sources.items() if name != "contracts.py"
    )

    from inputs_page_modules.session import build_inputs_summary_debug_payload_snapshot

    subset_keys = (
        "b", "D", "fc", "fsy",
        "uls_Mstar", "Mu_star", "uls_Vstar", "Vu_star", "Tu_star",
        "bot1_count", "bot2_count", "db_bot_1", "db_bot_2",
        "lig_d", "lig_legs", "s_lig",
        "Ast_bot", "d",
    )
    scenarios = [
        {
            "name": "normal_overlay_debug",
            "base": {"b": 300.0, "D": 600.0, "uls_Mstar": 100.0, "s_lig": 200.0},
            "resolved": {"b": 350.0, "D": 600.0, "uls_Mstar": 125.0, "s_lig": 150.0, "longitudinal_reo_truth_source": "rows"},
            "overlay": {"b": {"from": 300.0, "to": 350.0, "widget_key": "inputs_b"}},
            "shear": {
                "shear_widget_overlay_applied": True,
                "shear_widget_overlay_source": "inputs_widget",
                "overlay_s_lig": 150.0,
                "overlay_lig_d": 10.0,
                "overlay_lig_legs": 2,
            },
            "design_action": {"uls_Mstar": {"from": 100.0, "to": 125.0, "source": "design_action_result"}},
            "shared_only": False,
            "reason": "normal",
            "fp": "dg-fp-1",
        },
        {
            "name": "shared_only_debug",
            "base": {"b": 300.0, "D": 600.0, "s_lig": 200.0},
            "resolved": {"b": 300.0, "D": 600.0, "s_lig": 200.0},
            "overlay": {},
            "shear": {
                "shear_widget_overlay_applied": False,
                "shear_widget_overlay_source": "shared_only_suppressed",
                "overlay_s_lig": 200.0,
                "overlay_lig_d": 10.0,
                "overlay_lig_legs": 2,
            },
            "design_action": {},
            "shared_only": True,
            "reason": "pending_inputs_apply_refresh",
            "fp": None,
        },
    ]
    scenario_results: list[dict[str, Any]] = []
    for scenario in scenarios:
        legacy_payload, legacy_compact = _legacy_summary_debug_payload(
            base=scenario["base"],
            resolved=scenario["resolved"],
            overlay_applied=scenario["overlay"],
            shear_overlay_debug=scenario["shear"],
            design_action_result_overlay=scenario["design_action"],
            shared_only_mode=scenario["shared_only"],
            shared_only_reason=scenario["reason"],
            design_guide_fingerprint=scenario["fp"],
            subset_keys=subset_keys,
        )
        module_snapshot = build_inputs_summary_debug_payload_snapshot(
            base_state=scenario["base"],
            resolved_state=scenario["resolved"],
            overlay_applied=scenario["overlay"],
            shear_overlay_debug=scenario["shear"],
            design_action_result_overlay=scenario["design_action"],
            shared_only_mode=scenario["shared_only"],
            shared_only_reason=scenario["reason"],
            design_guide_fingerprint=scenario["fp"],
            subset_keys=subset_keys,
        )
        scenario_results.append(
            {
                "name": scenario["name"],
                "debug_payload_matches": module_snapshot.debug_payload == legacy_payload,
                "compact_diffs_matches": module_snapshot.compact_diffs == legacy_compact,
                "module_display_hash": module_snapshot.display_hash,
            }
        )

    checks = {
        "builder_exported": "build_inputs_summary_debug_payload_snapshot" in module_sources.get("__init__.py", ""),
        "model_exported": "InputsSummaryDebugPayloadSnapshot" in module_sources.get("__init__.py", ""),
        "builder_present": "def build_inputs_summary_debug_payload_snapshot(" in module_sources.get("builders.py", ""),
        "live_page_cut_over": "build_inputs_summary_debug_payload_snapshot(" in summary_window
        and "debug_payload = dict(_summary_debug_payload.debug_payload)" in summary_window
        and "inputs_summary_debug_payload_delegated" in summary_window,
        "inline_page_debug_payload_deleted": "debug_payload = {" not in summary_window
        and "compact_diffs: dict[str, dict]" not in summary_window
        and "summary_shared_vs_widget_diffs" not in summary_window
        and "summary_design_action_result_overlay_count" not in summary_window,
        "all_scenarios_match": all(
            row["debug_payload_matches"] and row["compact_diffs_matches"]
            for row in scenario_results
        ),
        "module_streamlit_free": "import streamlit" not in module_combined
        and "from streamlit" not in module_combined,
        "module_inputs_page_free": _module_inputs_page_free(module_combined),
        "module_session_mutation_free": "st.session_state" not in executable_module
        and ".session_state" not in executable_module,
        "module_apply_routing_free": _module_apply_routing_free(executable_module),
        "module_callback_execution_free": "on_change" not in executable_module
        and "sync_callback" not in executable_module,
        "module_rendering_free": _module_rendering_free(executable_module),
    }
    failures = [key for key, value in checks.items() if not value]
    decision = "SESSION_SUMMARY_DEBUG_PAYLOAD_DELEGATED" if not failures else "SESSION_SUMMARY_DEBUG_PAYLOAD_GAPS_REMAIN"
    payload = {
        "audit": "inputs_session_summary_debug_payload_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenarios": scenario_results,
        "live_page_cutover": True,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "next_safe_slice": "add/refresh boundary lock, then audit the next Session State sub-boundary",
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_summary_debug_payload_snapshot_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_summary_debug_payload_snapshot_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_summary_debug_payload_snapshot", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
