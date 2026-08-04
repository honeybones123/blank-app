"""Proof-only deletion readiness for the render-stage final-visible resolver.

The render bridge lock proves the render-stage resolver no longer owns final
Design Guide truth. This verifier narrows the deletion boundary for the single
render-stage ``resolve_final_visible_design_guide_item(...)`` callsite without
deleting it or changing product behaviour.

Result semantics:
- Before cutover, PASS means the callsite is a deletion candidate for the next
  slice.
- After cutover, PASS means the render-stage resolver call has been replaced
  with a compatibility ``_final_visible_resolution`` shape derived from
  FinalDesignGuidePublication / post-resolver proof surfaces.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = (
    ROOT
    / "inputs_page_modules"
    / "design_guide"
    / "current_coordinators.py"
)
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
APPLY_ROUTING = ROOT / "inputs_page_modules" / "apply_routing.py"
PAGE_RUNTIME_COMMON = ROOT / "inputs_application" / "page_runtime" / "common.py"
APP_CONTRACTS = ROOT / "inputs_page_app_contracts.py"

READINESS_PREFIX = "design_guide_post_render_bridge_restamper_readiness"
RENDER_LOCK_PREFIX = "design_guide_render_bridge_lock"
INDEPENDENCE_LOCK_PREFIX = "design_guide_independence_lock"
COLLAPSED_CUTOVER_PREFIX = "design_guide_collapsed_replacement_authority_cutover"

REQUIRED_RESOLUTION_KEYS = (
    "item",
    "render_reason",
    "overview",
    "design_brain_result",
    "presentation",
    "state_fingerprint",
    "debug",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    if os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        try:
            from tools.verification.verification_run_manifest import current_run_artifact
        except ModuleNotFoundError:
            from verification_run_manifest import current_run_artifact
        path, snapshot = current_run_artifact(prefix)
        if path is None:
            return {"found": False, "path": None, "snapshot": {}, "passed": False, "current_run": True}
        return {"found": True, "path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS", "current_run": True}
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not matches:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = matches[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _function_bounds(source: str, function_name: str) -> tuple[int, int] | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _function_source(source: str, function_name: str) -> str:
    bounds = _function_bounds(source, function_name)
    if bounds is None:
        return ""
    start, end = bounds
    return "\n".join(source.splitlines()[start - 1 : end])


def _line_containing(source: str, needle: str, *, function_name: str | None = None) -> int | None:
    bounds = _function_bounds(source, function_name) if function_name else None
    for index, line in enumerate(source.splitlines(), start=1):
        if needle not in line:
            continue
        if bounds and not (bounds[0] <= index <= bounds[1]):
            continue
        return index
    return None


def _context_for_line(source: str, line: int | None, radius: int = 45) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def _resolution_key_usage(render_function_source: str) -> dict[str, dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    for key in REQUIRED_RESOLUTION_KEYS:
        get_pattern = f'_final_visible_resolution.get("{key}")'
        item_pattern = f'_final_visible_resolution["{key}"]'
        usage[key] = {
            "read_count": render_function_source.count(get_pattern),
            "write_count": render_function_source.count(item_pattern),
            "get_pattern": get_pattern,
            "item_pattern": item_pattern,
        }
    return usage


def _replacement_coverage(*, input_source: str, final_source: str) -> dict[str, dict[str, Any]]:
    return {
        "item": {
            "covered": all(
                marker in input_source
                for marker in (
                    "build_collapsed_guidance_item_from_final_publication",
                )
            )
            and "published_item_id" in final_source,
            "source": "FinalDesignGuidePublication identity + collapsed guidance adapter",
        },
        "render_reason": {
            "covered": "publication_reason" in final_source,
            "source": "FinalDesignGuidePublication.publication_reason",
        },
        "overview": {
            "covered": (
                "final_compute_resolution = {" in input_source
                or "final_publication" in input_source
                or "FinalDesignGuidePublication" in final_source
            ),
            "source": "current controller/publication resolution shape; overview is compatibility-only",
        },
        "design_brain_result": {
            "covered": (
                "DesignGuideController" in input_source
                and "publication" in input_source
            ),
            "source": "current DesignGuideController publication handoff; not render resolver authority",
        },
        "presentation": {
            "covered": "class FinalDesignGuideDisplay" in final_source,
            "source": "FinalDesignGuidePublication.display",
        },
        "state_fingerprint": {
            "covered": "final_publication_authority_hash" in input_source or "final_publication_authority_hash" in final_source,
            "source": "debug/verifier metadata remains hash-stamped and non-authoritative",
        },
        "debug": {
            "covered": (
                "final_publication_verifier_payload" in input_source
                and "legacy_non_authoritative" in (input_source + final_source)
            ),
            "source": "debug/session payloads are same-object stamped or legacy non-authoritative",
        },
    }


def _extract_render_candidate(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = dict(readiness.get("snapshot") or {})
    return [
        dict(row)
        for row in list(snapshot.get("render_stage_lock_covered_candidates") or [])
        if isinstance(row, dict)
    ]


def _build_projected_resolution_shape_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_collapsed_guidance_item_from_final_publication,
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    item = {
        "published_item_id": "render-resolver-deletion-proof-item",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "shear",
        "check_key": "shear",
        "status": "ACTION",
        "bucket": "fail",
        "title_main": "Shear strengthening required",
        "title": "Shear strengthening required",
        "summary_line": "Apply the selected shear repair.",
        "post_click_design_guide_state": "ACTION",
        "candidate_id": "render-resolver-deletion-proof-candidate",
        "source_candidate_id": "render-resolver-deletion-proof-candidate",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "render-resolver-deletion-proof-candidate",
            "source_candidate_id": "render-resolver-deletion-proof-candidate",
            "updates": {"lig_spacing": 150},
            "expected_util": 0.92,
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "family": "shear",
            "candidate_id": "render-resolver-deletion-proof-candidate",
            "source_candidate_id": "render-resolver-deletion-proof-candidate",
            "updates": {"lig_spacing": 150},
        },
        "candidate_search_evidence": {
            "safe_executor_backed_candidate_found": True,
            "target_band_candidate_count": 1,
        },
    }
    debug = {
        "candidate_search_evidence": dict(item["candidate_search_evidence"]),
        "primary_button_contract": dict(item["button_contract"]),
        "final_publication_authority_hash": "synthetic-pre-hash",
    }
    publication = build_final_design_guide_publication(
        item=dict(item),
        debug=dict(debug),
        publication_reason="final_visible_design_guide_resolver",
    )
    collapsed_item = build_collapsed_guidance_item_from_final_publication(
        publication,
    )
    projected_resolution = {
        "item": dict(collapsed_item),
        "render_reason": publication.publication_reason or "final_visible_design_guide_resolver",
        "overview": {},
        "presentation": dict(publication.display.to_dict().get("final_card_model_fields") or {}),
        "debug": dict(publication.verifier_payload.to_dict().get("payload") or {}),
        "state_fingerprint": publication.source_hash,
        "final_publication_authority_hash": publication.publication_hash,
        "compatibility_only": True,
        "derived_from": "FinalDesignGuidePublication",
    }
    proof = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=dict(projected_resolution["item"]),
        final_visible_resolution=dict(projected_resolution),
        guidance_debug=dict(debug),
    )
    required_shape_keys = {
        key: key in projected_resolution for key in ("item", "render_reason", "overview", "presentation", "debug")
    }
    return {
        "publication_hash": publication.publication_hash,
        "collapsed_item_hash": stable_final_publication_hash(collapsed_item),
        "projected_resolution_hash": stable_final_publication_hash(projected_resolution),
        "post_resolver_proof_hash": proof.mutation_proof_hash,
        "required_shape_keys": required_shape_keys,
        "all_required_shape_keys_present": all(required_shape_keys.values()),
        "compatibility_only": projected_resolution["compatibility_only"],
        "derived_from_final_publication": projected_resolution["derived_from"] == "FinalDesignGuidePublication",
        "product_driving": False,
        "render_driving": False,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, CONTROLLER)
        if path.exists()
    )
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    app_contract_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (APPLY_ROUTING, PAGE_RUNTIME_COMMON, APP_CONTRACTS)
        if path.exists()
    )
    authority_source = input_source + "\n" + final_source
    render_function_source = _function_source(input_source, "_render_fast_design_guidance_panel")
    readiness = _latest(READINESS_PREFIX)
    render_lock = _latest(RENDER_LOCK_PREFIX)
    independence_lock = _latest(INDEPENDENCE_LOCK_PREFIX)
    collapsed_cutover = _latest(COLLAPSED_CUTOVER_PREFIX)
    render_candidates = _extract_render_candidate(readiness)
    resolver_line = _line_containing(
        input_source,
        "_final_visible_resolution = resolve_final_visible_design_guide_item(",
        function_name="_render_fast_design_guidance_panel",
    )
    adapter_line = _line_containing(
        input_source,
        "build_collapsed_guidance_item_from_final_publication(",
    )
    compute_resolver_lines = [
        line
        for line in (
            _line_containing(
                input_source,
                "final_compute_resolution = resolve_final_visible_design_guide_item(",
                function_name="_resolve_compute_design_guidance_publication_handoff",
            ),
            _line_containing(
                input_source,
                "_final_visible_resolution = resolve_final_visible_design_guide_item(",
                function_name="_render_fast_design_guidance_panel",
            ),
        )
        if line is not None
    ]
    resolver_context = _context_for_line(input_source, resolver_line or adapter_line, radius=55)
    usage = _resolution_key_usage(render_function_source)
    coverage = _replacement_coverage(input_source=input_source, final_source=final_source)
    projected_shape = _build_projected_resolution_shape_proof()
    render_lock_summary = dict((render_lock.get("snapshot") or {}).get("summary") or {})
    source_guards = {
        "single_or_completed_render_resolver_candidate_from_readiness": len(render_candidates) in {0, 1},
        "render_candidate_matches_callsite": bool(
            not render_candidates
            or (
                render_candidates[0].get("function") == "_render_fast_design_guidance_panel"
                and render_candidates[0].get("target") == "resolve_final_visible_design_guide_item"
            )
        ),
        "render_resolver_callsite_removed": resolver_line is None,
        "publication_authority_adapter_callsite_present": adapter_line is not None,
        "compute_resolver_callsite_still_present": (
            "run_design_guide_controller_compute_resolver_replacement_trace_only(" in input_source
            or "final_compute_resolution = {" in input_source
        ),
        "render_bridge_lock_pass": bool(render_lock["passed"]),
        "independence_lock_pass": bool(independence_lock["passed"]),
        "collapsed_replacement_cutover_pass": bool(collapsed_cutover["passed"]),
        "render_bridge_fully_narrowed": render_lock_summary.get("render_bridge_fully_narrowed") is True,
        "remaining_live_resolver_rows_zero": render_lock_summary.get("remaining_live_resolver_rows") == 0,
        "product_behavior_changed_false": render_lock_summary.get("product_behavior_changed") is False,
        "all_required_resolution_surfaces_covered": all(row["covered"] for row in coverage.values()),
        "projected_replacement_shape_available": bool(
            projected_shape["all_required_shape_keys_present"]
            and projected_shape["compatibility_only"]
            and projected_shape["derived_from_final_publication"]
        ),
        "cta_rendering_not_moved": (
            "render_final_design_guide_card_html" in (ROOT / "ui" / "final_design_guide_card.py").read_text(encoding="utf-8")
            and "render_final_design_guide_card_html" not in final_source
        ),
        "apply_routing_not_moved": (
            "handle_inputs_apply_buttons" in app_contract_source
            and "apply_recommendation_result_fn" in app_contract_source
            and "handle_inputs_apply_buttons" not in final_source
        ),
        "session_debug_fallback_non_authoritative": (
            "legacy_non_authoritative" in authority_source
            and "final_publication_authority_hash" in authority_source
            and "session_state" not in final_source
        ),
        "ui_wording_family_runtime_not_moved": (
            "ui.design_guide_cards" not in final_source
            and "_design_guide_clean_main_card_text" not in input_source
            and "run_bending_fail_governs_ladder_runtime" not in final_source
            and "run_shear_fail_governs_ladder_runtime" not in final_source
        ),
    }
    direct_deletion_assessment = {
        "plain_remove_without_replacement_safe": False,
        "reason_plain_remove_is_not_safe": (
            "_final_visible_resolution still supplies a compatibility dictionary shape used by later render code."
        ),
        "adapter_backed_replacement_completed": adapter_line is not None and resolver_line is None,
        "safe_next_deletion_slice_with_publication_derived_resolution_adapter": bool(
            source_guards["single_or_completed_render_resolver_candidate_from_readiness"]
            and source_guards["render_bridge_fully_narrowed"]
            and source_guards["remaining_live_resolver_rows_zero"]
            and source_guards["all_required_resolution_surfaces_covered"]
            and source_guards["projected_replacement_shape_available"]
            and source_guards["publication_authority_adapter_callsite_present"]
            and source_guards["render_resolver_callsite_removed"]
        ),
        "required_next_adapter": (
            "replace the render-stage resolver call with a compatibility _final_visible_resolution "
            "dict derived from FinalDesignGuidePublication / collapsed item adapter / post-resolver proof"
        ),
    }
    failures: list[str] = []
    for key, passed in source_guards.items():
        if not passed:
            failures.append(f"{key}_failed")
    if not direct_deletion_assessment["safe_next_deletion_slice_with_publication_derived_resolution_adapter"]:
        failures.append("render_resolver_deletion_not_proven_safe_for_next_slice")

    proof_surface = {
        "render_candidates": render_candidates,
        "resolver_line": resolver_line,
        "usage": usage,
        "coverage": coverage,
        "projected_shape": projected_shape,
        "source_guards": source_guards,
        "direct_deletion_assessment": direct_deletion_assessment,
    }
    return {
        "schema": "design_guide_render_stage_resolver_deletion_proof.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "source_artifacts": {
            "readiness": readiness.get("path"),
            "render_bridge_lock": render_lock.get("path"),
            "independence_lock": independence_lock.get("path"),
            "collapsed_replacement_authority_cutover": collapsed_cutover.get("path"),
        },
        "render_stage_resolver_candidate": render_candidates[0] if render_candidates else None,
        "resolver_callsite": {
            "file": "inputs_page.py",
            "function": "_render_fast_design_guidance_panel",
            "line": resolver_line,
            "removed": resolver_line is None,
            "adapter_line": adapter_line,
            "context_hash": _stable_hash(resolver_context),
        },
        "resolution_key_usage": usage,
        "replacement_coverage": coverage,
        "projected_replacement_shape_proof": projected_shape,
        "source_guards": source_guards,
        "direct_deletion_assessment": direct_deletion_assessment,
        "product_behavior_changed": False,
        "next_safe_step": (
            "live deletion slice: replace only the render-stage resolver call with a "
            "FinalDesignGuidePublication-derived compatibility _final_visible_resolution shape"
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    coverage_rows = "\n".join(
        f"| `{key}` | `{value['covered']}` | {value['source']} |"
        for key, value in snapshot["replacement_coverage"].items()
    )
    usage_rows = "\n".join(
        f"| `{key}` | `{value['read_count']}` | `{value['write_count']}` |"
        for key, value in snapshot["resolution_key_usage"].items()
    )
    guard_lines = "\n".join(
        f"- {key}: `{value}`" for key, value in snapshot["source_guards"].items()
    )
    body = "\n".join(
        [
            "# Design Guide Render-Stage Resolver Deletion Proof",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            "",
            "## Candidate",
            "",
            f"- File: `inputs_page.py`",
            f"- Function: `_render_fast_design_guidance_panel`",
            f"- Removed resolver line: `{snapshot['resolver_callsite']['line']}`",
            f"- Adapter line: `{snapshot['resolver_callsite']['adapter_line']}`",
            f"- Product behaviour changed: `{snapshot['product_behavior_changed']}`",
            "",
            "## Deletion Assessment",
            "",
            (
                "- Plain remove without replacement safe: "
                f"`{snapshot['direct_deletion_assessment']['plain_remove_without_replacement_safe']}`"
            ),
            (
                "- Safe next deletion slice with publication-derived resolution adapter: "
                f"`{snapshot['direct_deletion_assessment']['safe_next_deletion_slice_with_publication_derived_resolution_adapter']}`"
            ),
            (
                "- Adapter-backed replacement completed: "
                f"`{snapshot['direct_deletion_assessment']['adapter_backed_replacement_completed']}`"
            ),
            f"- Required adapter: {snapshot['direct_deletion_assessment']['required_next_adapter']}",
            "",
            "## Resolution Shape Usage",
            "",
            "| Key | Reads | Writes |",
            "| --- | ---: | ---: |",
            usage_rows,
            "",
            "## Replacement Coverage",
            "",
            "| Key | Covered | Source |",
            "| --- | --- | --- |",
            coverage_rows,
            "",
            "## Guards",
            "",
            guard_lines,
            "",
            "## Failures",
            "",
            "\n".join(f"- `{failure}`" for failure in snapshot["failures"]) if snapshot["failures"] else "- None",
            "",
            "## Next Step",
            "",
            snapshot["next_safe_step"],
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    timestamp = snapshot["generated_at"].replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_render_stage_resolver_deletion_proof_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_stage_resolver_deletion_proof_{timestamp}.md"
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_render_stage_resolver_deletion_proof {snapshot['status']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if snapshot["failures"]:
        print("failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

