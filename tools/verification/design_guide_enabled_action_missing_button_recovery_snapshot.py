"""Regression for ACTION Design Guide cards missing their Apply button.

The failure mode this protects:
- FinalDesignGuidePublication/CTA has an enabled button contract.
- The card renders with ACTION text.
- A stale or pre-bound apply payload exists in session.
- The final panel mistakenly treats that payload as proof that a browser button
  was rendered, so no Apply button appears.

The correct rule is narrower: an apply payload is not a rendered widget. If the
actual card render probe does not prove a visible button, an enabled contract
must fall through to the final-panel recovery button.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _slice_between(source: str, start: str, end: str) -> str:
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def main() -> int:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    render_call_idx = source.rfind("design_guide_page.render_final_panel(")
    if render_call_idx < 0:
        raise RuntimeError("render_final_panel callsite not found")
    end_marker = "\n        st.session_state.pop(DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY, None)"
    end_idx = source.index(end_marker, render_call_idx)
    post_render_block = source[render_call_idx:end_idx]
    payload_bound_match = re.search(
        r"if \(\s*_rendered_primary_payload_matches_fallback(?P<body>.*?)"
        r"if \(\s*_design_guide_button_contract_enabled\(_fallback_contract\)",
        post_render_block,
        flags=re.DOTALL,
    )
    payload_bound_block = payload_bound_match.group("body") if payload_bound_match else ""
    recovery_start = post_render_block.find(
        "if (\n                _design_guide_button_contract_enabled(_fallback_contract)"
    )
    recovery_branch = post_render_block[recovery_start:] if recovery_start >= 0 else ""
    recovery_condition = recovery_branch.split("_fallback_title = str(", 1)[0]
    recovery_branch = recovery_branch.split(
        '_dg_bundle_after_render["actual_card_render_probe"] = {',
        1,
    )[0]
    render_items_block = _slice_between(
        source,
        "def _render_guidance_secondary_items(",
        "\ndef _resolve_recommendation_updates(",
    )
    restore_contract_match = re.search(
        r"_pre_render_item_button_contract = dict\(item.get\(\"button_contract\"\) or \{\}\)(?P<body>.*?)"
        r"if is_primary_guidance_card:\s*\n\s*_render_contract_family_initial",
        render_items_block,
        flags=re.DOTALL,
    )
    restore_contract_block = restore_contract_match.group("body") if restore_contract_match else ""
    in_render_fallback_match = re.search(
        r"if \(\s*is_primary_guidance_card\s*and not _primary_apply_button_rendered(?P<body>.*?)"
        r"\n\n\ndef _resolve_recommendation_updates",
        source,
        flags=re.DOTALL,
    )
    in_render_fallback = in_render_fallback_match.group("body") if in_render_fallback_match else ""

    checks = {
        "payload_match_no_longer_marks_shell_skipped": "fallback_enabled_contract_shell_skipped" not in payload_bound_block,
        "payload_match_records_not_render_proof": "visible_button_not_proven" in post_render_block,
        "enabled_contract_recovery_requires_missing_render_probe": (
            "_design_guide_button_contract_enabled(_fallback_contract)" in recovery_condition
            and "and not _actual_card_probe_is_rendered" in recovery_condition
        ),
        "payload_match_does_not_block_recovery_condition": "_rendered_primary_payload_matches_fallback" not in recovery_condition,
        "projected_cta_does_not_gate_recovery_condition": "_fallback_contract_projected_from_publication_cta" not in recovery_condition,
        "recovery_renders_streamlit_button": "st.button(" in recovery_branch,
        "recovery_button_uses_unique_key": 'key="apply_design_guide_missing_card_recovery"' in recovery_branch,
        "recovery_preserves_apply_queue_callback": "_queue_primary_design_guide_button_action" in recovery_branch,
        "recovery_preserves_apply_routing": "_fallback_primary_route_target" in recovery_branch,
        "normal_primary_button_key_unchanged": 'key="apply_design_guide"' in source,
        "primary_render_preserves_existing_enabled_card_contract": (
            "_pre_render_item_button_contract = dict(item.get(\"button_contract\") or {})" in render_items_block
            and "_design_guide_button_contract_enabled(_pre_render_item_button_contract)" in restore_contract_block
            and "restored_primary_button_contract_from_final_publication_card" in restore_contract_block
        ),
        "restored_contract_must_be_actionable_and_unblocked": (
            'str(_pre_render_item_button_contract.get("action_type") or "").strip()' in restore_contract_block
            and 'dict(_pre_render_item_button_contract.get("updates") or {})' in restore_contract_block
            and '_pre_render_item_button_contract.get("blocking_reason")' in restore_contract_block
            and '_pre_render_item_button_contract.get("disabled_reason")' in restore_contract_block
        ),
        "primary_render_tracks_apply_button_rendered": "_primary_apply_button_rendered = False" in render_items_block
        and "_primary_apply_button_rendered = True" in render_items_block,
        "primary_render_stamps_actual_button_probe": (
            "primary_design_guide_apply_button_rendered" in render_items_block
            and '"render_button_contract_enabled": True' in render_items_block
            and "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = dict(debug_payload)" in render_items_block
        ),
        "enabled_primary_cta_has_in_render_fallback": (
            "_design_guide_button_contract_enabled(button_contract)" in in_render_fallback
            and "dict(button_contract.get(\"updates\") or {})" in in_render_fallback
            and "st.button(" in in_render_fallback
        ),
        "in_render_fallback_uses_final_publication_cta_source": (
            "final_publication_cta_contract_render_fallback" in in_render_fallback
            and "FinalDesignGuidePublication.cta" in in_render_fallback
        ),
        "in_render_fallback_preserves_apply_routing": (
            "_queue_primary_design_guide_button_action" in in_render_fallback
            and "fallback_route_target" in in_render_fallback
        ),
        "in_render_fallback_marks_probe_rendered": (
            "primary_final_publication_cta_render_fallback" in in_render_fallback
            and '"render_button_contract_enabled": True' in in_render_fallback
        ),
        "in_render_fallback_uses_unique_streamlit_key": (
            'key="apply_design_guide_final_publication_cta_fallback"' in in_render_fallback
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_enabled_action_missing_button_recovery.v1",
        "status": status,
        "timestamp": _stamp(),
        "checks": checks,
        "failures": failures,
        "product_behaviour_intent": (
            "Enabled ACTION cards must show an Apply button. A bound apply payload "
            "does not prove a Streamlit button was rendered."
        ),
        "behaviour_changed": "Restores missing recovery Apply button for enabled contracts; does not change engineering decisions.",
    }

    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"design_guide_enabled_action_missing_button_recovery_{payload['timestamp']}.json"
    md_path = AUDIT_DIR / f"design_guide_enabled_action_missing_button_recovery_{payload['timestamp']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Enabled Action Missing Button Recovery",
                "",
                f"- Status: `{status}`",
                "- Protected bug: ACTION card rendered without visible Apply button.",
                "- Rule: session apply payload is not proof of a rendered button.",
                "",
                "## Checks",
                "",
                *[f"- {name}: `{'PASS' if ok else 'FAIL'}`" for name, ok in checks.items()],
                "",
                "## Scope",
                "",
                "This is a render/button recovery regression only. It does not change family runtimes, engineering decisions, CTA semantics, or apply routing.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_enabled_action_missing_button_recovery {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
