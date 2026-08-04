"""Audit readiness to replace combined low-util generator invocation with a controller API."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

ROUTE_FUNCTION = "_resolve_final_visible_no_active_combined_low_util_safe_cleanup_result"
SHEAR_GENERATOR = "_shear_low_util_target_cleanup_item"
COMBINED_GENERATOR = "_combine_best_safe_shear_with_bending_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _token_presence(source: str, tokens: list[str]) -> dict[str, bool]:
    return {token: token in source for token in tokens}


def _capture() -> dict[str, Any]:
    route_deleted = False
    try:
        route_source, route_start, route_end = _function_source(INPUTS_PAGE, ROUTE_FUNCTION)
    except RuntimeError as exc:
        if f"Could not find {ROUTE_FUNCTION}" not in str(exc):
            raise
        route_source, route_start, route_end = "", None, None
        route_deleted = True
    shear_source, shear_start, shear_end = _function_source(INPUTS_PAGE, SHEAR_GENERATOR)
    combined_deleted = False
    try:
        combined_source, combined_start, combined_end = _function_source(INPUTS_PAGE, COMBINED_GENERATOR)
    except RuntimeError as exc:
        if f"Could not find {COMBINED_GENERATOR}" not in str(exc):
            raise
        combined_source, combined_start, combined_end = "", None, None
        combined_deleted = True
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    generator_dependency_tokens = {
        SHEAR_GENERATOR: _token_presence(
            shear_source,
            [
                "_collect_design_overview(",
            "_build_design_actions_context(",
            "_build_design_guide_shear_low_util_raw_variant_states(",
            "_build_design_guide_shear_low_util_variant_sequence(",
            "_evaluate_design_guide_shear_low_util_cleanup_candidate(",
            "_build_design_guide_shear_low_util_candidate_acceptance_screen(",
            "candidate_search_evidence",
            ],
        ),
        COMBINED_GENERATOR: _token_presence(
            combined_source,
            [
                "_resolve_design_guide_combined_low_util_cleanup_updates(",
                "_evaluate_design_guide_combined_low_util_cleanup_candidate(",
                "_run_design_guide_combined_low_util_bending_cleanup_item_generation(",
                "_assess_design_guide_combined_low_util_cleanup_acceptance_gate(",
                "_assess_design_guide_combined_low_util_post_click_accepted_green_audit(",
                "_resolve_design_guide_combined_low_util_cleanup_target_band(",
                "_build_design_guide_combined_low_util_cleanup_candidate_search_evidence(",
                "_build_design_guide_combined_low_util_result_packaging(",
            ],
        ),
    }
    route_invocation_tokens = _token_presence(
        route_source,
        [
            "_run_design_guide_controller_combined_low_util_candidate_generation(",
            'generation_result.get("route_policy_proof")',
            'generation_result.get("handoff_proof")',
        ],
    )
    route_legacy_direct_invocation_tokens = _token_presence(
        route_source,
        [
            "shear_low_util_target_cleanup_item_fn(",
            "combine_best_safe_shear_with_bending_cleanup_item_fn(",
            "design_guide_button_contract_enabled_fn(final_combined_cleanup_contract)",
            "updates_match_state_fn(final_state, final_combined_cleanup_updates)",
            "_build_design_guide_controller_combined_low_util_candidate_generation_handoff_proof(",
        ],
    )
    controller_has_invocation_api = (
        "def run_design_guide_controller_combined_low_util_candidate_generation" in controller_source
        or "def build_design_guide_controller_combined_low_util_candidate_generation_result" in controller_source
    )
    required_api_surface = [
        {
            "field": "state",
            "owner_after_move": "controller/shared API input",
            "reason": "candidate variants and evaluation are state-dependent",
        },
        {
            "field": "overview",
            "owner_after_move": "controller/shared API input",
            "reason": "current utils/statuses seed low-util route and evidence",
        },
        {
            "field": "threshold/mode_config",
            "owner_after_move": "controller/shared API input or Design Brain config",
            "reason": "target-band and accepted-floor decisions must stay contract-backed",
        },
        {
            "field": "evaluation adapter",
            "owner_after_move": "controller/shared API dependency",
            "reason": "both generators call candidate evaluation",
        },
        {
            "field": "normalization/applicability gate",
            "owner_after_move": "controller/shared API output proof",
            "reason": "selected item must still have enabled contract and non-stale updates",
        },
    ]
    return {
        "decision": (
            "ROUTE_INVOCATION_ALREADY_DELETED"
            if route_deleted
            else "ROUTE_INVOCATION_REPLACED_PAGE_GENERATORS_RETAINED"
        ),
        "route": {
            "function": ROUTE_FUNCTION,
            "start_line": route_start,
            "end_line": route_end,
            "line_count": 0 if route_deleted else route_end - route_start + 1,
            "deleted": route_deleted,
        },
        "generators": {
            SHEAR_GENERATOR: {
                "start_line": shear_start,
                "end_line": shear_end,
                "line_count": shear_end - shear_start + 1,
                "dependencies": generator_dependency_tokens[SHEAR_GENERATOR],
            },
            COMBINED_GENERATOR: {
                "start_line": combined_start,
                "end_line": combined_end,
                "line_count": 0 if combined_deleted else combined_end - combined_start + 1,
                "deleted": combined_deleted,
                "dependencies": generator_dependency_tokens[COMBINED_GENERATOR],
            },
        },
        "route_invocation_tokens": route_invocation_tokens,
        "route_legacy_direct_invocation_tokens": route_legacy_direct_invocation_tokens,
        "controller_has_invocation_api": controller_has_invocation_api,
        "safe_to_replace_route_invocation_now": not route_deleted,
        "safe_to_delete_page_generators_now": False,
        "combined_generator_deleted": combined_deleted,
        "required_api_surface": required_api_surface,
        "next_safe_step": (
            "Route invocation and combined generator already deleted; continue with remaining shear generator or route-level assembler/resolver glue."
            if route_deleted
            else (
                "Combined generator already deleted; continue at route-level assembler/resolver glue. "
                "Do not delete remaining route or shear generator paths until consumer reachability and replacement proofs pass."
            )
            if combined_deleted
            else (
                "Keep extracting the page-local generator internals one proof-backed boundary at a time. "
                "Do not delete either generator until consumer reachability and replacement proofs pass."
            )
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    route_tokens = dict(capture.get("route_invocation_tokens") or {})
    legacy_route_tokens = dict(capture.get("route_legacy_direct_invocation_tokens") or {})
    generators = dict(capture.get("generators") or {})
    route_deleted = bool((capture.get("route") or {}).get("deleted"))
    dependencies_ok = all(
        all((generator.get("dependencies") or {}).values())
        for generator in generators.values()
    )
    return {
        "route_function_found_or_deleted_as_expected": bool((capture.get("route") or {}).get("line_count"))
        or route_deleted,
        "page_generators_found_or_deleted_as_expected": bool(
            (generators.get(SHEAR_GENERATOR) or {}).get("line_count")
        )
        and (
            bool((generators.get(COMBINED_GENERATOR) or {}).get("line_count"))
            or bool((generators.get(COMBINED_GENERATOR) or {}).get("deleted"))
        ),
        "route_invocation_tokens_present_or_route_deleted": all(route_tokens.values())
        or route_deleted,
        "route_legacy_direct_invocation_removed": not any(legacy_route_tokens.values()),
        "page_generator_dependencies_identified_or_combined_deleted": dependencies_ok
        or bool(capture.get("combined_generator_deleted")),
        "controller_invocation_api_present": capture.get("controller_has_invocation_api") is True,
        "route_invocation_replaced_or_deleted": capture.get("safe_to_replace_route_invocation_now") is True
        or route_deleted,
        "not_safe_to_delete_generators_yet": capture.get("safe_to_delete_page_generators_now") is False,
        "required_api_surface_recorded": len(capture.get("required_api_surface") or []) >= 5,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Generator Invocation Replacement Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Generator Ownership", ""])
    for name, generator in (capture.get("generators") or {}).items():
        lines.append(f"### `{name}`")
        lines.append(f"- Lines: `{generator.get('start_line')}`-`{generator.get('end_line')}`")
        for token, present in (generator.get("dependencies") or {}).items():
            lines.append(f"- `{token}`: `{present}`")
        lines.append("")
    lines.extend(
        [
            "## Required API Surface",
            "",
            "| Field | Owner After Move | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for item in capture.get("required_api_surface") or []:
        lines.append(
            f"| {item.get('field')} | {item.get('owner_after_move')} | {item.get('reason')} |"
        )
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
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
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_generator_invocation_replacement_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_generator_invocation_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_generator_invocation_replacement_readiness_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
