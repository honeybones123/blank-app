from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
INPUTS_PAGE = ROOT / "inputs_page.py"
PUBLICATION = ROOT / "design_brain" / "publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _extract_function(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        raise AssertionError(f"{name} not found")
    next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def main() -> None:
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    helper = _extract_function(source, "_shear_overdesign_contract_width_cleanup_item")
    live_helper = _extract_function(source, "_live_shear_overdesign_contract_width_cleanup_item")
    family_identity_helper = _extract_function(source, "_canonical_family_owned_shear_overdesign_apply_family")
    publication_contract_guard = _extract_function(
        publication_source,
        "enforce_family_selection_publication_contract",
    )
    render_branch_marker = "_render_residual_width_cleanup_item = _shear_low_util_target_cleanup_item("
    render_branch_start = source.find(render_branch_marker)
    if render_branch_start < 0:
        raise AssertionError("render residual width cleanup branch not found")
    render_branch_end = source.find("_render_residual_width_cleanup_contract = (", render_branch_start)
    if render_branch_end < 0:
        raise AssertionError("render residual width cleanup contract handoff not found")
    render_branch = source[render_branch_start:render_branch_end]
    accepted_green_marker = "residual_width_cleanup_item = _shear_low_util_target_cleanup_item("
    accepted_green_start = source.find(accepted_green_marker)
    if accepted_green_start < 0:
        raise AssertionError("accepted-green residual width cleanup branch not found")
    accepted_green_end = source.find('debug["local_cleanup_blocked_reason"] = "accepted_green_no_materially_overprovided_family"', accepted_green_start)
    if accepted_green_end < 0:
        raise AssertionError("accepted-green residual width cleanup handoff not found")
    accepted_green_branch = source[accepted_green_start:accepted_green_end]
    post_apply_terminal_marker = "_post_apply_residual_width_item = _shear_low_util_target_cleanup_item("
    post_apply_terminal_start = source.find(post_apply_terminal_marker)
    if post_apply_terminal_start < 0:
        raise AssertionError("post-apply terminal residual width cleanup branch not found")
    post_apply_terminal_end = source.find("_post_apply_terminal_is_residual_width_cleanup = bool(", post_apply_terminal_start)
    if post_apply_terminal_end < 0:
        raise AssertionError("post-apply terminal residual width cleanup handoff not found")
    post_apply_terminal_branch = source[post_apply_terminal_start:post_apply_terminal_end]
    post_cleanup_terminal_marker = "_post_cleanup_residual_width_item = _shear_low_util_target_cleanup_item("
    post_cleanup_terminal_start = source.find(post_cleanup_terminal_marker)
    if post_cleanup_terminal_start < 0:
        raise AssertionError("post-cleanup terminal residual width cleanup branch not found")
    post_cleanup_terminal_end = source.find("_post_cleanup_terminal_rendered_as_residual_width = bool(", post_cleanup_terminal_start)
    if post_cleanup_terminal_end < 0:
        raise AssertionError("post-cleanup terminal residual width cleanup handoff not found")
    post_cleanup_terminal_branch = source[post_cleanup_terminal_start:post_cleanup_terminal_end]

    checks = {
        "helper_exists": bool(helper),
        "helper_fills_missing_fields_from_live_shared_state": (
            "live_state = _guidance_state_snapshot(_shared_state_snapshot())" in helper
            and "if key not in state or state.get(key) in (None, \"\"):" in helper
            and "state[key] = value" in helper
        ),
        "helper_prefers_live_shared_geometry_and_actions": (
            "live_owned_keys = set(SHARED_DEFAULTS.keys())" in helper
            and "live_owned_keys.update(_SUMMARY_DESIGN_ACTION_RESULT_KEYS)" in helper
            and "\"uls_Mstar\"" in helper
            and "\"uls_Vstar\"" in helper
            and "for key in sorted(live_owned_keys):" in helper
            and "state[key] = live_state.get(key)" in helper
        ),
        "helper_does_not_let_default_shared_state_override_explicit_candidate_state": (
            "live_has_design_actions" in helper
            and "if live_has_design_actions:" in helper
            and "_local_float_or_zero" in helper
            and "\"load_Mstar_proxy\"" in helper
            and "\"inputs_load_Vstar_proxy\"" in helper
        ),
        "live_state_contract_width_cleanup_adapter_exists": (
            "_shared_state_snapshot()" in live_helper
            and "_collect_design_overview(" in live_helper
            and "_shear_overdesign_contract_width_cleanup_item(" in live_helper
            and "allow_best_safe_below_threshold=allow_best_safe_below_threshold" in live_helper
        ),
        "contract_candidates_filtered_to_width_before_iteration": (
            "contract_width_candidates" in helper
            and "lane_id == \"WIDTH_REDUCTION\"" in helper
            and "for contract_candidate in contract_width_candidates[:128]" in helper
        ),
        "inactive_shear_width_cleanup_strips_redundant_ligature_removal_updates": (
            "if not _shear_reinforcement_is_active(state):" in helper
            and "for redundant_shear_key in (\"lig_legs\", \"lig_d\", \"s_lig\"):" in helper
            and "updates.pop(redundant_shear_key, None)" in helper
        ),
        "rectangular_width_cleanup_keeps_web_width_consistent": (
            "if \"b\" in updates and \"bw\" not in updates:" in helper
            and "abs(float(current_web_width) - float(current_width)) <= 1e-9" in helper
            and "updates[\"bw\"] = updates.get(\"b\")" in helper
        ),
        "no_pre_filter_candidate_cap": (
            "for contract_candidate in list(contract_projection.get(\"candidates\") or [])[:96]" not in helper
        ),
        "canonical_trial_rebuild_before_evaluation": (
            "_build_canonical_design_state_pack" in helper
            and "_overlay_current_normalized_shear_truth(trial_state)" in helper
            and "_canonical_pack_is_valid(canonical_trial_state)" in helper
            and "_design_state_coherence_check(canonical_trial_state)" in helper
        ),
        "canonical_trial_preserves_design_actions_before_evaluation": (
            "for action_key in _SUMMARY_DESIGN_ACTION_RESULT_KEYS:" in helper
            and "canonical_trial_state[action_key] = trial_state.get(action_key)" in helper
            and "\"uls_Mstar\"" in helper
            and "\"load_Mstar_proxy\"" in helper
            and "\"uls_Vstar\"" in helper
        ),
        "evaluation_uses_rebuilt_trial_state": (
            "evaluate_candidate_full(" in helper
            and "canonical_trial_state" in helper
            and "updates=updates" in helper
        ),
        "objective_uses_explicit_bending_demand_util": "_candidate_bending_demand_util(candidate)" in helper,
        "depth_reduction_still_rejected": "depth_reduction" in helper and "continue" in helper,
        "contract_runtime_authority_stamped": "run_shear_overdesign_governs_runtime" in helper,
        "render_branch_falls_back_when_primary_item_not_actionable": (
            "_render_residual_width_primary_actionable" in render_branch
            and "_design_guide_button_contract_enabled(_render_residual_width_primary_contract)" in render_branch
            and "not _updates_match_state(guidance_disp_state, _render_residual_width_primary_updates)" in render_branch
            and "if not _render_residual_width_primary_actionable:" in render_branch
            and "_shear_overdesign_contract_width_cleanup_item(" in render_branch
            and "_live_shear_overdesign_contract_width_cleanup_item(" in render_branch
            and "_render_residual_width_match_state = _guidance_state_snapshot(_shared_state_snapshot())" in render_branch
            and "not _updates_match_state(_render_residual_width_match_state, _render_residual_width_cleanup_updates)" in source
        ),
        "accepted_green_gate_falls_back_when_primary_item_not_actionable": (
            "residual_width_primary_actionable" in accepted_green_branch
            and "_design_guide_button_contract_enabled(residual_width_contract)" in accepted_green_branch
            and "not _updates_match_state(state, residual_width_updates)" in accepted_green_branch
            and "if not residual_width_primary_actionable:" in accepted_green_branch
            and "_shear_overdesign_contract_width_cleanup_item(" in accepted_green_branch
            and "_live_shear_overdesign_contract_width_cleanup_item(" in accepted_green_branch
            and "residual_width_match_state = _guidance_state_snapshot(_shared_state_snapshot())" in accepted_green_branch
            and "not _updates_match_state(residual_width_match_state, residual_width_updates)" in accepted_green_branch
        ),
        "post_apply_terminal_gate_falls_back_to_contract_width_cleanup": (
            "_post_apply_residual_width_primary_actionable" in post_apply_terminal_branch
            and "_shear_overdesign_contract_width_cleanup_item(" in post_apply_terminal_branch
            and "_live_shear_overdesign_contract_width_cleanup_item(" in post_apply_terminal_branch
            and "_post_apply_residual_width_match_state = _guidance_state_snapshot(_shared_state_snapshot())" in post_apply_terminal_branch
            and "not _updates_match_state(_post_apply_residual_width_match_state, _post_apply_residual_width_updates)" in source
        ),
        "post_cleanup_terminal_gate_falls_back_to_contract_width_cleanup": (
            "_post_cleanup_residual_width_primary_actionable" in post_cleanup_terminal_branch
            and "_shear_overdesign_contract_width_cleanup_item(" in post_cleanup_terminal_branch
            and "_live_shear_overdesign_contract_width_cleanup_item(" in post_cleanup_terminal_branch
            and "_post_cleanup_residual_width_match_state = _guidance_state_snapshot(_shared_state_snapshot())" in post_cleanup_terminal_branch
            and "not _updates_match_state(_post_cleanup_residual_width_match_state, _post_cleanup_residual_width_updates)" in source
        ),
        "enabled_final_publication_contract_overrides_stale_no_action_recommendation": (
            'rec_status_for_contract in {"blocked", "advisory", "disabled", "no_action"}' in source
            and "contract_commit_authoritative" in source
            and '"_source": "final_publication_cta_contract"' in source
        ),
        "shear_width_cleanup_keeps_shear_overdesign_family_identity": (
            '"matched_family_ids"' in family_identity_helper
            and 'update_keys.issubset(_COMPOUND_SHEAR_UPDATE_KEYS | {"b", "bw"})' in family_identity_helper
            and 'return "SHEAR_OVERDESIGN_GOVERNS"' in family_identity_helper
            and "_canonical_family_owned_shear_overdesign_apply_family(" in source[source.find("def _fast_guidance_card_data_attrs_html"):source.find("def _guidance_before_after_text")]
        ),
        "post_apply_exhausted_shear_cleanup_terminalises_in_publication_guard": (
            "diagnostics_cleanup_terminal_proven" in publication_contract_guard
            and "selected_family_id in cleanup_recovery_family_ids" in publication_contract_guard
            and "not cleanup_recovery_payload" in publication_contract_guard
            and "not active_failures" in publication_contract_guard
            and 'not diagnostics_raw_state.get("shear_cleanup_possible")' in publication_contract_guard
            and 'not diagnostics_raw_state.get("unnecessary_shear_reinforcement_exists")' in publication_contract_guard
            and 'selected_family_id == "SHEAR_OVERDESIGN_GOVERNS"' in publication_contract_guard
            and '"cleanup_terminal_no_remaining_shear_cleanup_normalised"' in publication_contract_guard
            and '"cleanup_family_terminal_exhaustion_normalised_to_target_band": True' in publication_contract_guard
            and '"cleanup_terminal_source_family_id": selected_family_id' in publication_contract_guard
            and "_target_band_reached_publication_item(primary, accepted_diagnostics)" in publication_contract_guard
        ),
    }
    passed = all(bool(value) for value in checks.values())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema": "shear_overdesign_live_width_publication_regression.v1",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "failure_guard": {
            "root_cause": "publication helper previously capped contract candidates before width-lane filtering",
            "required_behavior": (
                "filter WIDTH_REDUCTION candidates first, then canonical-rebuild each width trial "
                "before candidate evaluation"
            ),
        },
    }
    json_path = ARTIFACT_DIR / f"shear_overdesign_live_width_publication_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_live_width_publication_regression_{stamp}.md"
    json_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_OVERDESIGN_GOVERNS Live Width Publication Regression",
                "",
                f"Status: **{artifact['status']}**",
                "",
                "This verifier locks the live publication boundary that previously allowed "
                "a wide post-click accepted state to bypass later contract width candidates.",
                "It also locks the render handoff so a disabled/no-op primary shear cleanup "
                "item cannot suppress the contract-owned width cleanup lane.",
                "",
                "## Checks",
                *[
                    f"- {'PASS' if ok else 'FAIL'} `{name}`"
                    for name, ok in checks.items()
                ],
                "",
                f"JSON artifact: `{json_path}`",
            ]
        ),
        encoding="utf-8",
    )
    if not passed:
        raise SystemExit(f"SHEAR_OVERDESIGN live width publication regression FAIL: {json_path}")
    print("SHEAR_OVERDESIGN live width publication regression PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
