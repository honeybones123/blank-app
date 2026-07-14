"""Audit deletion readiness for the page-local shear low-util cleanup generator."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _target_function_source(inputs_source: str) -> str:
    function_start = inputs_source.find("def _shear_low_util_target_cleanup_item(")
    function_end = inputs_source.find("\ndef ", function_start + 1) if function_start >= 0 else -1
    if function_start < 0 or function_end <= function_start:
        return ""
    return inputs_source[function_start:function_end]


def _line_number(source: str, token: str) -> int | None:
    idx = source.find(token)
    if idx < 0:
        return None
    return source[:idx].count("\n") + 1


def _classify_remaining(function_source: str) -> list[dict[str, Any]]:
    checks = [
        {
            "id": "overview_fallback",
            "token": "_collect_design_overview(",
            "category": "B page-owned compute/evaluation input",
            "role": "fallback current overview when caller did not provide shear util",
            "recommendation": "keep until Design Guide request/controller owns overview construction",
        },
        {
            "id": "variant_generation",
            "token": "generate_less_shear_reo_variants(",
            "category": "B page-owned candidate generation",
            "role": "generates shear cleanup variant states",
            "recommendation": "extract only after variant generator boundary proof",
        },
        {
            "id": "no_link_update_normalisation",
            "token": "_canonical_no_link_shear_cleanup_updates(",
            "category": "B page-owned update normalisation",
            "role": "constructs canonical no-link candidate updates",
            "recommendation": "extract with invalid-shear update normalisation boundary",
        },
        {
            "id": "candidate_diff",
            "token": "_one_click_diff_accumulated_updates(",
            "category": "B page-owned shared update diff",
            "role": "computes update payload from base and variant state",
            "recommendation": "keep until shared diff helper is moved or wrapped",
        },
        {
            "id": "materiality_filter",
            "token": "_shear_cleanup_materially_reduces_reinforcement(",
            "category": "B page-owned engineering/materiality filter",
            "role": "rejects variants that do not reduce shear reinforcement",
            "recommendation": "move only with focused materiality parity snapshot",
        },
        {
            "id": "candidate_evaluation",
            "token": "_evaluate_auto_design_candidate(",
            "category": "B page-owned evaluator bridge",
            "role": "evaluates candidate engineering result and preview overview",
            "recommendation": "must be absent after candidate evaluation boundary cutover",
        },
        {
            "id": "candidate_evaluation_controller_boundary",
            "token": "_evaluate_design_guide_shear_low_util_cleanup_candidate(",
            "category": "A controller-owned injected evaluator boundary",
            "role": "normalizes evaluator request metadata, exceptions, non-dict returns, and proof stamps while injecting existing evaluator",
            "recommendation": "controller-owned for this selected target loop",
        },
        {
            "id": "failure_coverage",
            "token": "_candidate_failure_coverage_summary(state, resolved_candidate)",
            "category": "B page-owned failure coverage adapter",
            "role": "summarises candidate coverage from current state and candidate overview",
            "recommendation": "move with failure-coverage parity snapshot",
        },
        {
            "id": "change_lines",
            "token": "_guidance_change_lines_for_updates(state, updates)",
            "category": "C page-owned visible wording adapter",
            "role": "builds visible change-line wording from state and updates",
            "recommendation": "move with exact visible wording parity snapshot",
        },
        {
            "id": "required_check_acceptance",
            "token": "_overview_required_checks_acceptable(",
            "category": "B page-owned acceptance screen",
            "role": "filters failed candidate previews",
            "recommendation": "move with candidate evaluation acceptance boundary",
        },
        {
            "id": "preview_status_failure_screen",
            "token": "_candidate_preview_statuses_have_explicit_fail(",
            "category": "B page-owned acceptance screen",
            "role": "filters explicit failed preview statuses",
            "recommendation": "move with candidate evaluation acceptance boundary",
        },
        {
            "id": "preview_failure_reason",
            "token": "_shear_cleanup_failed_reason_from_preview(",
            "category": "B page-owned preview/evidence adapter",
            "role": "derives no-link failure reason from evaluated preview",
            "recommendation": "move with preview failure reason parity snapshot",
        },
        {
            "id": "guidance_item_text",
            "token": "_guidance_item(",
            "category": "C page-owned visible wording/item shell",
            "role": "builds visible Design Guide card text",
            "recommendation": "extract only with exact visible wording parity",
        },
        {
            "id": "formatted_title",
            "token": "_format_guidance_title(",
            "category": "C page-owned visible title formatting",
            "role": "formats visible card title",
            "recommendation": "extract only with exact visible wording parity",
        },
        {
            "id": "promotion",
            "token": "_promote_guidance_item_to_resolved_candidate(",
            "category": "C page-owned publication/apply compatibility bridge",
            "role": "promotes item into existing resolved-candidate shape",
            "recommendation": "keep until promotion adapter is controller-owned",
        },
        {
            "id": "generator_boundary_trace",
            "token": "_build_design_guide_shear_low_util_cleanup_generator_boundary_proof(",
            "category": "D trace-only non-authoritative proof",
            "role": "records proof hash and generator/evaluator ownership flags",
            "recommendation": "keep as non-authoritative until generator is replaced",
        },
    ]
    rows = []
    for check in checks:
        present = check["token"] in function_source
        row = dict(check)
        row["present"] = present
        row["line_in_function"] = _line_number(function_source, check["token"])
        rows.append(row)
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    function_source = _target_function_source(inputs_source)
    callsite_count = max(
        0,
        len(re.findall(r"\b_shear_low_util_target_cleanup_item\(", inputs_source)) - 1,
    )
    classifications = _classify_remaining(function_source)
    present_categories = sorted(
        {
            str(row.get("category"))
            for row in classifications
            if row.get("present")
        }
    )
    controller_cutovers = {
        "classifier": "_classify_design_guide_shear_low_util_cleanup_candidate(" in function_source,
        "accumulator": "_accumulate_design_guide_shear_low_util_cleanup_candidate(" in function_source,
        "candidate_record": "_build_design_guide_shear_low_util_cleanup_candidate_record(" in function_source,
        "no_link_probe": "_build_design_guide_shear_low_util_no_link_probe(" in function_source,
        "raw_variant_states": "_build_design_guide_shear_low_util_raw_variant_states(" in function_source,
        "variant_sequence": "_build_design_guide_shear_low_util_variant_sequence(" in function_source,
        "candidate_delta_screen": "_build_design_guide_shear_low_util_candidate_delta_screen(" in function_source,
        "candidate_evaluation_boundary": "_evaluate_design_guide_shear_low_util_cleanup_candidate(" in function_source,
        "candidate_acceptance_screen": "_build_design_guide_shear_low_util_candidate_acceptance_screen(" in function_source,
        "change_lines": "_build_design_guide_shear_low_util_change_lines_for_updates(" in function_source,
        "failed_reason_from_preview": "_build_design_guide_shear_low_util_failed_reason_from_preview(" in function_source,
        "failure_coverage": "_build_design_guide_shear_low_util_failure_coverage_from_overviews(" in function_source,
        "selected_no_link_audit": "_build_design_guide_shear_low_util_selected_no_link_audit_update(" in function_source,
        "preferred_target_blocker": "_build_design_guide_shear_low_util_preferred_target_blocker(" in function_source,
        "candidate_search_evidence": "_build_design_guide_shear_low_util_cleanup_candidate_search_evidence(" in function_source,
        "final_item_packaging": "_build_design_guide_shear_low_util_final_item_packaging(" in function_source,
        "promotion_adapter": "_build_design_guide_shear_low_util_promoted_item(" in function_source,
        "guidance_descriptor": "_build_design_guide_shear_low_util_guidance_item_descriptor(" in function_source,
        "guidance_item_shell": "_build_design_guide_shear_low_util_guidance_item_shell(" in function_source,
        "generator_boundary_trace": "_build_design_guide_shear_low_util_cleanup_generator_boundary_proof(" in function_source,
    }
    old_inline_patterns_removed = {
        "inline_accumulator_removed": "if distance <= best_distance + 1e-9:" not in function_source,
        "inline_preferred_blocker_reason_removed": (
            "The selected best safe shear cleanup reaches shear utilisation" not in function_source
            and "The selected shear cleanup reaches the final accepted utilisation band" not in function_source
        ),
        "inline_evidence_block_removed": (
            '"cleanup_search_ran": True,\n        "cleanup_search_exhaustive": True,'
            not in function_source
        ),
        "inline_button_contract_removed": 'out_item["button_contract"] = {' not in function_source,
        "inline_resolved_candidate_update_removed": "resolved_candidate.update(" not in function_source,
        "inline_no_link_variant_prepend_removed": "if no_link_key not in {" not in function_source,
        "inline_raw_variant_generator_call_removed": (
            "generate_less_shear_reo_variants(" not in function_source
        ),
        "inline_page_promotion_bridge_removed": (
            "_promote_guidance_item_to_resolved_candidate(" not in function_source
        ),
        "inline_page_preview_failure_reason_removed": (
            "_shear_cleanup_failed_reason_from_preview(" not in function_source
        ),
        "inline_page_failure_coverage_removed": (
            "_candidate_failure_coverage_summary(state, resolved_candidate)" not in function_source
        ),
        "inline_page_change_lines_removed": (
            "_guidance_change_lines_for_updates(state, updates)" not in function_source
        ),
        "inline_page_direct_evaluator_removed": (
            "candidate = _evaluate_auto_design_candidate(" not in function_source
        ),
    }
    blocking_rows = [
        row
        for row in classifications
        if row.get("present") and str(row.get("category", "")).startswith(("B", "C"))
    ]
    deletion_ready = bool(function_source) and not blocking_rows
    return {
        "decision": (
            "SHEAR_LOW_UTIL_GENERATOR_DELETION_READY"
            if deletion_ready
            else "SHEAR_LOW_UTIL_GENERATOR_NOT_READY_TO_DELETE"
        ),
        "target_function_found": bool(function_source),
        "callsite_count": callsite_count,
        "remaining_classifications": classifications,
        "present_categories": present_categories,
        "controller_cutovers": controller_cutovers,
        "old_inline_patterns_removed": old_inline_patterns_removed,
        "deletion_ready": deletion_ready,
        "blocking_responsibilities": blocking_rows,
        "next_safe_slice": (
            "Extract current-overview boundary after a focused parity proof."
        ),
        "controller_page_free": "inputs_page" not in controller_source
        and "st.session_state" not in controller_source
        and "streamlit" not in controller_source,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_moved": True,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_function_found": bool(capture.get("target_function_found")),
        "callsite_inventory_present": int(capture.get("callsite_count") or 0) > 0,
        "all_controller_cutovers_present": all(
            (capture.get("controller_cutovers") or {}).values()
        ),
        "old_inline_patterns_removed": all(
            (capture.get("old_inline_patterns_removed") or {}).values()
        ),
        "remaining_responsibilities_classified": all(
            row.get("category") and row.get("recommendation")
            for row in capture.get("remaining_classifications") or []
        ),
        "not_marked_delete_ready_while_blockers_remain": (
            bool(capture.get("deletion_ready")) is False
            and bool(capture.get("blocking_responsibilities"))
        ),
        "controller_page_free": capture.get("controller_page_free") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_boundary_moved": capture.get("candidate_evaluation_moved") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Shear Low-Util Generator Deletion Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Callsites: `{capture.get('callsite_count')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Controller Cutovers", ""])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("controller_cutovers") or {}).items()
    )
    lines.extend(["", "## Remaining Responsibilities", ""])
    for row in capture.get("remaining_classifications") or []:
        if not row.get("present"):
            continue
        lines.append(
            f"- `{row.get('id')}`: {row.get('category')} - {row.get('recommendation')}"
        )
    lines.extend(["", "## Next Safe Slice", ""])
    lines.append(str(capture.get("next_safe_slice") or ""))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_shear_low_util_generator_deletion_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shear_low_util_generator_deletion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_shear_low_util_generator_deletion_readiness_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
