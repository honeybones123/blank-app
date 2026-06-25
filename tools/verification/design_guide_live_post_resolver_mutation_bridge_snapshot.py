"""Trace-only live bridge snapshot for render-stage post-resolver mutations.

This verifier proves the render-stage final visible resolver now stamps a
FinalDesignGuidePostResolverMutationProof beside the live path. The proof is
debug-only: it does not narrow the resolver bridge, render cards, route apply
actions, or change CTA/session/UI ownership.
"""

from __future__ import annotations

import ast
import json
import subprocess
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

FORBIDDEN_FINAL_PUBLICATION_IMPORTS = {
    "inputs_page",
    "streamlit",
    "st",
    "session_state",
    "design_guide_page",
    "ui.design_guide_cards",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(str(node.module or ""))
    return sorted(set(imports))


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


def _line_containing(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _line_containing_in_function(source: str, function_name: str, needle: str) -> int | None:
    bounds = _function_bounds(source, function_name)
    if bounds is None:
        return None
    start, end = bounds
    lines = source.splitlines()
    for offset, line in enumerate(lines[start - 1 : end], start=start):
        if needle in line:
            return offset
    return None


def _build_synthetic_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
    )

    item = {
        "published_item_id": "render-stage-item-bridge-001",
        "family": "combined",
        "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL_GOVERN",
        "status": "ACTION",
        "bucket": "action",
        "title": "Strengthening required",
        "title_main": "Strengthening required",
        "summary_line": "Apply the selected repair.",
        "post_click_design_guide_state": "ACTION",
        "design_guide_terminal_state": "ACTION",
        "candidate_id": "candidate-bridge-001",
        "source_candidate_id": "source-candidate-bridge-001",
        "action_type": "apply_resolved_candidate",
        "util": 1.08,
        "expected_util": 0.94,
        "candidate_post_util": 0.94,
        "resolved_candidate": {"candidate_id": "candidate-bridge-001", "expected_util": 0.94},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "candidate_id": "candidate-bridge-001",
            "source_candidate_id": "source-candidate-bridge-001",
            "updates": {"D": 950.0, "lig_d": 20},
            "expected_util": 0.94,
        },
        "action_payload": {
            "candidate_id": "candidate-bridge-001",
            "source_candidate_id": "source-candidate-bridge-001",
            "updates": {"D": 950.0, "lig_d": 20},
            "candidate_search_evidence": {
                "safe_executor_backed_candidate_found": True,
                "target_band_candidate_count": 1,
            },
        },
        "candidate_search_evidence": {
            "safe_executor_backed_candidate_found": True,
            "target_band_candidate_count": 1,
            "exact_blockers_by_family": {"bending": {"reason": "exact post-click stop"}},
        },
        "exact_blockers_by_family": {"bending": {"reason": "exact post-click stop"}},
        "post_click_exact_blockers_by_family": {"bending": {"reason": "post-click exact stop"}},
        "blocker_attempts_by_family": {"bending": [{"lane": "DEPTH_INCREASE"}]},
    }
    debug = {
        "candidate_search_evidence": dict(item["candidate_search_evidence"]),
        "exact_blockers_by_family": dict(item["exact_blockers_by_family"]),
        "post_click_exact_blockers_by_family": dict(item["post_click_exact_blockers_by_family"]),
        "blocker_attempts_by_family": dict(item["blocker_attempts_by_family"]),
        "primary_button_contract": dict(item["button_contract"]),
        "button_contract": dict(item["button_contract"]),
    }
    resolution = {
        "item": dict(item),
        "render_reason": "render_stage_final_visible_resolver",
        "presentation": {"headline": "Strengthening required", "theme": "fail"},
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug=debug,
        publication_reason="render_stage_final_visible_resolver",
    )
    proof_a = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=item,
        final_visible_resolution=resolution,
        guidance_debug=debug,
    )
    proof_b = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=item,
        final_visible_resolution=resolution,
        guidance_debug=debug,
    )
    proof_payload = proof_a.to_dict()
    return {
        "publication_hash": publication.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "stable_repeated_hash": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "adapter_owned_mutation_truth": dict(proof_a.adapter_owned_mutation_truth),
        "remaining_resolver_truth": dict(proof_a.remaining_resolver_truth),
        "mutation_target_coverage": dict(proof_a.mutation_target_coverage),
        "payload_hash": _stable_hash(proof_payload),
        "proof": proof_payload,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    helper_source = _function_source(input_source, "_stamp_final_publication_post_resolver_mutation_proof")
    render_source = _function_source(input_source, "_render_fast_design_guidance_panel")
    builder_source = _function_source(publication_source, "build_final_design_guide_post_resolver_mutation_proof")
    canonical_builder_source = _function_source(publication_source, "build_render_stage_post_resolver_item_mutation_proof")
    final_publication_imports = _module_imports(FINAL_PUBLICATION)
    forbidden_imports = sorted(
        imp for imp in final_publication_imports if imp in FORBIDDEN_FINAL_PUBLICATION_IMPORTS
    )

    synthetic_proof = _build_synthetic_proof()
    collapsed_cutover = _run("tools/verification/design_guide_collapsed_replacement_authority_cutover.py")
    independence_lock = _run("tools/verification/design_guide_independence_lock_verifier.py")

    live_bridge = {
        "import_present": (
            "build_final_design_guide_post_resolver_mutation_proof as _build_final_design_guide_post_resolver_mutation_proof"
            in input_source
        ),
        "page_helper_present": bool(helper_source),
        "render_stage_call_present": "_stamp_final_publication_post_resolver_mutation_proof(" in render_source,
        "render_stage_call_line": _line_containing_in_function(
            input_source,
            "_render_fast_design_guidance_panel",
            "_stamp_final_publication_post_resolver_mutation_proof(",
        ),
        "debug_payload_stamp_present": "final_publication_post_resolver_mutation_proof" in helper_source,
        "proof_hash_stamp_present": "final_publication_post_resolver_mutation_proof_hash" in helper_source,
        "authority_hash_stamp_present": "final_publication_post_resolver_mutation_authority_hash" in helper_source,
        "adapter_owned_truth_stamp_present": "final_publication_post_resolver_mutation_adapter_owned_truth" in helper_source,
        "remaining_truth_stamp_present": "final_publication_post_resolver_mutation_remaining_resolver_truth" in helper_source,
        "proof_only_stamp_present": "final_publication_post_resolver_mutation_proof_only" in helper_source,
        "non_product_driving_stamp_present": "final_publication_post_resolver_mutation_product_driving" in helper_source,
        "non_render_driving_stamp_present": "final_publication_post_resolver_mutation_render_driving" in helper_source,
    }
    helper_guards = {
        "does_not_write_session": "st.session_state" not in helper_source,
        "does_not_record_apply_payload": "_record_rendered_design_guide_primary_apply_payload" not in helper_source,
        "does_not_render": "render_final_panel" not in helper_source
        and "_design_guide_dashboard_card_html_from_render_model" not in helper_source,
        "does_not_mutate_visible_item": 'item["' not in helper_source and "item.update(" not in helper_source,
        "uses_plain_dict_inputs": "dict(item or {})" in helper_source
        and "dict(final_visible_resolution or {})" in helper_source
        and "dict(debug_sink or {})" in helper_source,
    }
    design_brain_proof = {
        "dataclass_present": "class FinalDesignGuidePostResolverMutationProof" in publication_source,
        "alias_builder_present": bool(builder_source),
        "canonical_builder_present": bool(canonical_builder_source),
        "adapter_owned_truth_field_present": "adapter_owned_mutation_truth" in publication_source,
        "remaining_resolver_truth_field_present": "remaining_resolver_truth" in publication_source,
        "stable_hash_field_present": "mutation_proof_hash" in publication_source,
        "no_forbidden_imports": not forbidden_imports,
        "forbidden_imports": forbidden_imports,
    }
    ownership_guards = {
        "cta_rendering_stays_page_owned": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_stays_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_stays_page_owned": "st.session_state" in input_source
        and "session_state" not in final_publication_imports,
        "ui_rendering_stays_out_of_design_brain": "ui.design_guide_cards" not in final_publication_imports,
        "bridge_is_trace_only": synthetic_proof["proof"].get("proof_only") is True
        and synthetic_proof["proof"].get("product_driving") is False
        and synthetic_proof["proof"].get("render_driving") is False,
    }
    proof_guards = {
        "derived_from_final_publication": synthetic_proof["proof"].get("derived_from") == "FinalDesignGuidePublication",
        "proof_hash_stable": bool(synthetic_proof["stable_repeated_hash"]),
        "adapter_owned_mutation_truth_represented": bool(
            synthetic_proof["adapter_owned_mutation_truth"].get("candidate_search_evidence")
            and synthetic_proof["adapter_owned_mutation_truth"].get("exact_blockers_by_family")
            and synthetic_proof["adapter_owned_mutation_truth"].get("cta_apply_identity")
        ),
        "remaining_resolver_truth_classified": (
            synthetic_proof["remaining_resolver_truth"].get("classification")
            == "remaining_live_resolver_truth_not_narrowed"
            and synthetic_proof["remaining_resolver_truth"].get("post_resolver_bridge_narrowed") is False
        ),
    }

    failures: list[str] = []
    if not all(live_bridge.values()):
        failures.append("live_bridge_wiring_missing_or_incomplete")
    if not all(helper_guards.values()):
        failures.append("helper_guard_failed")
    if not all(
        value for key, value in design_brain_proof.items() if key != "forbidden_imports"
    ):
        failures.append("design_brain_proof_object_failed")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("proof_guard_failed")
    if not collapsed_cutover["passed"]:
        failures.append("collapsed_replacement_authority_cutover_failed")
    if not independence_lock["passed"]:
        failures.append("design_guide_independence_lock_failed")

    return {
        "snapshot_name": "design_guide_live_post_resolver_mutation_bridge_snapshot",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "expected_result": "PASS, render bridge still not narrowed",
        "failures": failures,
        "live_bridge": live_bridge,
        "helper_guards": helper_guards,
        "design_brain_proof": design_brain_proof,
        "ownership_guards": ownership_guards,
        "proof_guards": proof_guards,
        "synthetic_proof": synthetic_proof,
        "composed_gates": {
            "collapsed_replacement_authority_cutover": collapsed_cutover,
            "design_guide_independence_lock": independence_lock,
        },
        "render_bridge_narrowed": False,
        "next_slice": (
            "Narrow only adapter-owned mutation rows after this bridge remains green; "
            "leave remaining live resolver truth untouched."
        ),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Live Post-Resolver Mutation Bridge Snapshot",
        "",
        f"Result: **{snapshot['status']}**",
        "",
        "## Purpose",
        "",
        "Proof-only live bridge beside the render-stage final visible resolver. "
        "The bridge stamps `FinalDesignGuidePostResolverMutationProof` into debug payloads only.",
        "",
        "## Live Bridge",
        "",
    ]
    for key, value in snapshot["live_bridge"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Proof Object",
            "",
            f"- publication hash: `{snapshot['synthetic_proof']['publication_hash']}`",
            f"- proof hash: `{snapshot['synthetic_proof']['proof_hash']}`",
            f"- stable repeated hash: `{snapshot['synthetic_proof']['stable_repeated_hash']}`",
            "- adapter-owned mutation truth is represented.",
            "- remaining resolver truth remains classified as live and not narrowed.",
            "",
            "## Ownership",
            "",
        ]
    )
    for key, value in snapshot["ownership_guards"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Composed Gates",
            "",
            f"- collapsed replacement authority cutover: `{snapshot['composed_gates']['collapsed_replacement_authority_cutover']['passed']}`",
            f"- Design Guide independence lock: `{snapshot['composed_gates']['design_guide_independence_lock']['passed']}`",
            "",
            "## Next Slice",
            "",
            snapshot["next_slice"],
            "",
        ]
    )
    if snapshot["failures"]:
        lines.extend(["## Failures", ""])
        for failure in snapshot["failures"]:
            lines.append(f"- `{failure}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    snapshot = _build_snapshot()
    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_live_post_resolver_mutation_bridge_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_post_resolver_mutation_bridge_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_live_post_resolver_mutation_bridge_snapshot {snapshot['status']}")
    print(f"json: {json_path}")
    print(f"report: {md_path}")
    if snapshot["status"] != "PASS":
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
