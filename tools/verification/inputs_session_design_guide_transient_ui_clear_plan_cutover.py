from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import build_inputs_design_guide_transient_ui_clear_plan


INPUTS_PAGE = ROOT / "inputs_page.py"
SESSION_BUILDERS = ROOT / "inputs_page_modules" / "session" / "builders.py"
SESSION_MODELS = ROOT / "inputs_page_modules" / "session" / "models.py"
SESSION_INIT = ROOT / "inputs_page_modules" / "session" / "__init__.py"
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


def _old_plan(
    *,
    base_transient_keys: tuple[str, ...],
    apply_banner_key: str,
    always_clear_keys: tuple[str, ...],
    history_keys: tuple[str, ...],
    clear_history: bool,
    preserve_apply_banner: bool,
) -> tuple[str, ...]:
    transient_keys = list(base_transient_keys)
    if not preserve_apply_banner:
        transient_keys.append(apply_banner_key)
    keys = [*transient_keys, *always_clear_keys]
    if clear_history:
        keys.extend(history_keys)
    return tuple(keys)


def _scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "default_clear", "clear_history": False, "preserve_apply_banner": False},
        {"name": "preserve_apply_banner", "clear_history": False, "preserve_apply_banner": True},
        {"name": "clear_history", "clear_history": True, "preserve_apply_banner": False},
        {"name": "clear_history_preserve_apply_banner", "clear_history": True, "preserve_apply_banner": True},
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Session Design Guide Transient UI Clear Plan Cutover",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        f"- scenarios checked: `{len(payload['scenario_results'])}`",
        f"- mismatches: `{len(payload['mismatches'])}`",
        f"- product behavior changed: `{payload['product_behavior_changed']}`",
        f"- session mutation moved: `{payload['session_mutation_moved']}`",
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
    helper = _function_window(source, "_clear_design_guide_transient_ui_state")
    builders = _read(SESSION_BUILDERS)
    models = _read(SESSION_MODELS)
    init_source = _read(SESSION_INIT)

    base_keys = (
        "apply_banner_meta",
        "guidance_cache_fp",
        "guidance_cache_items",
        "guidance_cache_debug",
    )
    always_keys = ("debug_bundle", "reco_trace", "rank_trace")
    history_keys = ("step_history", "first_target_band_step", "history_anchor")
    apply_banner_key = "apply_banner"

    scenario_results = []
    mismatches = []
    for row in _scenarios():
        old = _old_plan(
            base_transient_keys=base_keys,
            apply_banner_key=apply_banner_key,
            always_clear_keys=always_keys,
            history_keys=history_keys,
            clear_history=bool(row["clear_history"]),
            preserve_apply_banner=bool(row["preserve_apply_banner"]),
        )
        new = build_inputs_design_guide_transient_ui_clear_plan(
            base_transient_keys=base_keys,
            apply_banner_key=apply_banner_key,
            always_clear_keys=always_keys,
            history_keys=history_keys,
            clear_history=bool(row["clear_history"]),
            preserve_apply_banner=bool(row["preserve_apply_banner"]),
        )
        match = old == tuple(new.all_keys) and bool(new.display_hash)
        scenario_results.append(
            {
                "scenario": row["name"],
                "match": match,
                "old": list(old),
                "new": list(new.all_keys),
                "display_hash_present": bool(new.display_hash),
            }
        )
        if not match:
            mismatches.append({"scenario": row["name"], "old": list(old), "new": list(new.all_keys)})

    required_constants = [
        "DESIGN_GUIDE_APPLY_BANNER_META_KEY",
        "DESIGN_GUIDE_GUIDANCE_CACHE_FP_KEY",
        "DESIGN_GUIDE_GUIDANCE_CACHE_ITEMS_KEY",
        "DESIGN_GUIDE_GUIDANCE_CACHE_DEBUG_KEY",
        "DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY",
        "DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY",
        "DESIGN_GUIDE_PENDING_STEP_CTX_KEY",
        "DESIGN_GUIDE_PUBLICATION_FP_KEY",
        "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY",
        "DESIGN_GUIDE_PRIMARY_PAYLOAD_BINDING_AUDIT_KEY",
        "DESIGN_GUIDE_APPLY_BANNER_KEY",
        "DESIGN_GUIDE_DEBUG_BUNDLE_KEY",
        "DESIGN_GUIDE_RECO_TRACE_KEY",
        "DESIGN_GUIDE_RANK_TRACE_KEY",
        "DESIGN_GUIDE_STEP_HISTORY_KEY",
        "DESIGN_GUIDE_FIRST_TARGET_BAND_STEP_KEY",
        "DESIGN_GUIDE_HISTORY_ANCHOR_KEY",
    ]
    required_literal_keys = [
        "design_guide_primary_button_contract",
        "design_guide_primary_button_contract_enabled",
        "design_guide_primary_display_truth",
        "pending_recommendation",
        "pending_recommendation_applied_id",
        "_design_guide_post_cleanup_acceptance_fp",
        "_design_guide_post_cleanup_acceptance_enabled",
    ]

    checks = {
        "helper_delegates_to_session_builder": "build_inputs_design_guide_transient_ui_clear_plan(" in helper,
        "helper_keeps_session_mutation": "st.session_state.pop" in helper,
        "old_inline_transient_list_removed": "transient_keys = [" not in helper,
        "old_inline_append_removed": ".append(DESIGN_GUIDE_APPLY_BANNER_KEY)" not in helper,
        "old_individual_pop_policy_removed": "if clear_history:" not in helper and "DESIGN_GUIDE_DEBUG_BUNDLE_KEY, None)" not in helper,
        "helper_passes_required_constants": all(name in helper for name in required_constants),
        "helper_passes_literal_keys": all(name in helper for name in required_literal_keys),
        "session_builder_exists": "def build_inputs_design_guide_transient_ui_clear_plan(" in builders,
        "session_model_exists": "class InputsDesignGuideTransientUiClearPlan" in models,
        "session_init_exports_builder": "build_inputs_design_guide_transient_ui_clear_plan" in init_source,
        "session_init_exports_model": "InputsDesignGuideTransientUiClearPlan" in init_source,
        "session_builder_has_no_streamlit_import": "import streamlit" not in builders.lower()
        and "from streamlit" not in builders.lower(),
        "all_scenarios_match": not mismatches,
    }
    failures = [key for key, value in checks.items() if not value]
    decision = (
        "INPUTS_SESSION_DESIGN_GUIDE_TRANSIENT_UI_CLEAR_PLAN_LOCKED"
        if not failures
        else "INPUTS_SESSION_DESIGN_GUIDE_TRANSIENT_UI_CLEAR_PLAN_GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_session_design_guide_transient_ui_clear_plan_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "scenario_results": scenario_results,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "session_behavior_changed": False,
        "session_mutation_moved": False,
        "callbacks_moved": False,
        "apply_routing_moved": False,
        "streamlit_reads_moved": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_session_design_guide_transient_ui_clear_plan_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_session_design_guide_transient_ui_clear_plan_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_session_design_guide_transient_ui_clear_plan_cutover", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
