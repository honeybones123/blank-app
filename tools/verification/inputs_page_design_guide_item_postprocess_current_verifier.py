from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            matches.append((node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_item_postprocess_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_item_postprocess_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    shell_source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_item_postprocess_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(shell_source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("item_postprocess_current_coordinator_missing")
    if coordinator_size > 290:
        failures.append(f"item_postprocess_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_dedupe_guidance_items_for_display(",
        "_collapse_to_single_primary_guidance_item(",
        "\"_design_guide_single_primary_debug\"",
        "_recommendation_result_for_primary_guidance_card(",
        "_suppress_redundant_guidance_items(",
        "_consolidate_guidance_items_by_family(",
        "_maybe_promote_safe_local_cleanup_primary(",
        "_prefer_target_band_guidance_item_order(",
        "_align_guidance_items_to_candidate_search_evidence(",
        "_design_guide_apply_copy_model_to_items(",
        "_design_guide_apply_button_contracts_to_items(",
        "_design_guide_apply_display_truth_to_items(",
        "_post_click_accepted_green_audit(",
        "\"post_apply_local_cleanup_accepted\"",
        "\"design_guide_overlap_suppressed\"",
        "\"design_guide_family_consolidation_item_debug\"",
        "\"primary_card_family_tag\"",
        "\"surfaced_secondary_card_source\"",
        "\"_design_guide_overlap_suppression_debug\"",
        "\"_design_guide_family_suppression_debug\"",
        "\"guidance_dedupe_meta\": dict(guidance_dedupe_meta or {})",
        "\"collapse_meta\": dict(collapse_meta or {})",
        "\"redundancy_meta\": dict(redundancy_meta or {})",
        "\"family_suppression_meta\": dict(family_suppression_meta or {})",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    if legacy_source:
        for required in [
            "render_design_guide_item_postprocess_current_coordinator(",
            "guidance_items_raw=guidance_items_raw",
            "guidance_disp_state=guidance_disp_state",
            "guidance_debug=guidance_debug",
            "_stage=_stage",
            "guidance_items = list(_item_postprocess[\"guidance_items\"] or [])",
            "guidance_dedupe_meta = dict(_item_postprocess[\"guidance_dedupe_meta\"] or {})",
            "collapse_meta = dict(_item_postprocess[\"collapse_meta\"] or {})",
            "_branch_for_rr = _item_postprocess[\"_branch_for_rr\"]",
            "_recommendation_result = _item_postprocess[\"_recommendation_result\"]",
            "redundancy_meta = dict(_item_postprocess[\"redundancy_meta\"] or {})",
            "family_suppression_meta = dict(_item_postprocess[\"family_suppression_meta\"] or {})",
        ]:
            if required not in legacy_source:
                failures.append(f"legacy_missing_{required}")
    for stale in [
        "guidance_items, guidance_dedupe_meta = _dedupe_guidance_items_for_display(",
        "_collapse_to_single_primary_guidance_item(",
        "_suppress_redundant_guidance_items(",
        "_consolidate_guidance_items_by_family(",
        "_maybe_promote_safe_local_cleanup_primary(",
        "_post_click_accepted_green_audit(",
        "guidance_debug[\"design_guide_family_consolidation_item_debug\"]",
        "st.session_state[\"_design_guide_family_suppression_debug\"]",
    ]:
        if stale in legacy_source:
            failures.append(f"legacy_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_item_postprocess_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Item Postprocess Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Legacy coordinator size: `{legacy_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
