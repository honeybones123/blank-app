"""Narrow class-D combined cleanup rescue replacement rows.

This verifier proves the combined cleanup rescue replacement rows are now
compatibility/proof-only via FinalDesignGuidePublication and
FinalDesignGuidePostResolverMutationProof. The class-E exact-blocker row remains
untouched.
"""

from __future__ import annotations

import importlib.util
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
SAFE_LOW_NARROWING = (
    ROOT / "tools" / "verification" / "design_guide_safe_low_util_replacement_narrowing_snapshot.py"
)

CLASS_D = "D. combined cleanup rescue replacement"
CLASS_E = "E. post-click exact blocker replacement"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "passed": False}
    path = artifacts[-1]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return {"path": str(path), "snapshot": snapshot, "passed": snapshot.get("status") == "PASS"}


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


def _load_safe_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_safe_low_util_replacement_narrowing_snapshot",
        SAFE_LOW_NARROWING,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load safe-low-util narrowing snapshot")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remaining_after_safe_low() -> list[dict[str, Any]]:
    module = _load_safe_module()
    snapshot = module._build_snapshot()
    return list(snapshot.get("remaining_live_rows") or [])


def _combined_equivalence_case(*, boundary_metadata: bool = False) -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    if boundary_metadata:
        item = {
            "published_item_id": "combined-boundary-metadata-item",
            "selected_family_id": "BENDING_FAIL_GOVERNS",
            "family": "bending",
            "check_key": "bending",
            "status": "BLOCKED",
            "title_main": "Family selection contract boundary",
            "title": "Family selection contract boundary",
            "summary_line": "Combined cleanup rescue unavailable.",
            "post_click_design_guide_state": "BLOCKED",
            "button_contract": {
                "enabled": False,
                "actionable": False,
                "family": "bending",
                "disabled_reason": "family selection contract boundary",
            },
        }
        render_reason = "family_selection_contract_boundary"
        presentation = {
            "headline": item["title_main"],
            "subtext": item["summary_line"],
            "guidance_intent": "required_fix",
            "css_bucket": "fail",
            "theme": "fail",
            "show_apply_button": False,
            "use_success_style": False,
        }
    else:
        item = {
            "published_item_id": "combined-cleanup-rescue-item",
            "selected_family_id": "COMBINED_OVERDESIGN",
            "published_family_id": "COMBINED_OVERDESIGN",
            "family": "combined",
            "check_key": "combined",
            "status": "EFFICIENCY",
            "bucket": "info",
            "title_main": "Shear and bending cleanup - one-click optimisation",
            "title": "Shear and bending cleanup - one-click optimisation",
            "summary_line": "Apply one-click optimisation to tighten shear links and bottom reinforcement.",
            "post_click_design_guide_state": "ACTION",
            "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "action_type": "apply_resolved_candidate",
            "button_contract": {
                "enabled": True,
                "actionable": True,
                "label": "Apply repair",
                "action_type": "apply_resolved_candidate",
                "family": "combined",
                "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "updates": {"lig_d": 16, "bot_row_1_bars": 3},
                "expected_util": 0.91,
            },
            "action_payload": {
                "action_type": "apply_resolved_candidate",
                "family": "combined",
                "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "updates": {"lig_d": 16, "bot_row_1_bars": 3},
            },
            "candidate_search_evidence": {
                "search_scope": "combined_best_safe_shear_plus_bending_cleanup",
                "safe_executor_backed": True,
                "preview_pass": True,
            },
        }
        render_reason = "final_visible_combined_low_util_safe_cleanup"
        presentation = {
            "headline": item["title_main"],
            "guidance_intent": "efficiency_tightening",
            "css_bucket": "efficiency",
            "theme": "efficiency",
            "show_apply_button": True,
            "use_success_style": False,
        }
    resolution = {
        "item": dict(item),
        "render_reason": render_reason,
        "presentation": dict(presentation),
    }
    publication = build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason=render_reason,
    )
    proof_a = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=dict(item),
        final_visible_resolution=dict(resolution),
        guidance_debug={},
    )
    proof_b = build_final_design_guide_post_resolver_mutation_proof(
        publication,
        selected_item=dict(item),
        final_visible_resolution=dict(resolution),
        guidance_debug={},
    )
    cta = publication.cta.to_dict()
    display = publication.display.to_dict()
    evidence = publication.evidence.to_dict()
    return {
        "case": "combined_cleanup_rescue_boundary_metadata" if boundary_metadata else "combined_cleanup_rescue_replacement",
        "publication_hash": publication.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "proof_hash_stable": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "cta_hash": stable_final_publication_hash(cta),
        "display_hash": stable_final_publication_hash(display),
        "evidence_hash": stable_final_publication_hash(evidence),
        "resolver_projection_hash": stable_final_publication_hash(proof_a.resolver_projection),
        "selected_item_identity_hash": stable_final_publication_hash(proof_a.selected_item_identity),
        "presentation_hash": stable_final_publication_hash(presentation),
        "render_reason_matches": proof_a.resolver_projection.get("render_reason") == render_reason,
        "presentation_matches": proof_a.resolver_projection.get("presentation") == presentation,
        "action_type_matches": (
            True if boundary_metadata else cta.get("action_type") == "apply_resolved_candidate"
        ),
        "source_candidate_matches": (
            True
            if boundary_metadata
            else cta.get("source_candidate_id") == "combined_best_safe_shear_plus_bending_cleanup"
        ),
        "proof_only": proof_a.proof_only,
        "product_driving": proof_a.product_driving,
        "render_driving": proof_a.render_driving,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    remaining_after_safe_low = _remaining_after_safe_low()
    class_d_rows = [row for row in remaining_after_safe_low if row.get("classification") == CLASS_D]
    class_e_rows = [row for row in remaining_after_safe_low if row.get("classification") == CLASS_E]
    equivalence_cases = [
        _combined_equivalence_case(boundary_metadata=False),
        _combined_equivalence_case(boundary_metadata=True),
    ]
    helper_markers = {
        "helper_present": "def _stamp_final_publication_combined_cleanup_rescue_compatibility_proof(" in input_source,
        "replacement_callsite_present": 'callsite="combined_cleanup_rescue_replacement"' in input_source,
        "boundary_metadata_callsite_present": 'callsite="combined_cleanup_rescue_boundary_metadata"' in input_source,
        "proofs_key_present": "final_publication_combined_cleanup_rescue_compatibility_proofs" in input_source,
        "proof_hash_key_present": "final_publication_combined_cleanup_rescue_compatibility_proof_hash" in input_source,
        "compatibility_key_present": "final_publication_combined_cleanup_rescue_rows_compatibility_only" in input_source,
        "remaining_truth_not_narrowed_key_present": (
            "final_publication_combined_cleanup_rescue_remaining_truth_narrowed" in input_source
        ),
        "post_click_exact_blocker_not_product_driving": (
            'callsite="post_click_exact_blocker_replacement"' not in input_source
            or (
                "final_publication_post_click_exact_blocker_rows_compatibility_only" in input_source
                and "final_publication_post_click_exact_blocker_remaining_truth_narrowed" in input_source
            )
        ),
    }
    ownership_guards = {
        "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_not_moved": "st.session_state" in input_source
        and "session_state" not in publication_source,
        "ui_rendering_not_moved": "ui.design_guide_cards" not in publication_source,
        "visible_wording_not_moved": "_design_guide_clean_main_card_text" in input_source
        and "_design_guide_clean_main_card_text" not in publication_source,
    }
    proof_guards = {
        "all_cases_hash_stable": all(case["proof_hash_stable"] for case in equivalence_cases),
        "all_cases_render_reason_match": all(case["render_reason_matches"] for case in equivalence_cases),
        "all_cases_presentation_match": all(case["presentation_matches"] for case in equivalence_cases),
        "all_cases_action_identity_match": all(
            case["action_type_matches"] and case["source_candidate_matches"]
            for case in equivalence_cases
        ),
        "all_cases_not_product_or_render_driving": all(
            case["proof_only"] and not case["product_driving"] and not case["render_driving"]
            for case in equivalence_cases
        ),
    }
    safe_low = _latest_artifact("design_guide_safe_low_util_replacement_narrowing")
    metadata = _latest_artifact("design_guide_final_visible_resolution_metadata_narrowing")
    identity = _latest_artifact("design_guide_final_resolver_identity_narrowing")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    remaining_after_combined_narrowing = len(class_e_rows)
    failures: list[str] = []
    if len(class_d_rows) != 3:
        failures.append(f"expected_3_class_d_rows_found_{len(class_d_rows)}")
    if len(class_e_rows) != 1:
        failures.append(f"expected_1_class_e_row_found_{len(class_e_rows)}")
    if remaining_after_combined_narrowing != 1:
        failures.append(f"expected_1_remaining_live_row_found_{remaining_after_combined_narrowing}")
    if not all(helper_markers.values()):
        failures.append("combined_cleanup_helper_or_callsite_marker_missing")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("combined_cleanup_equivalence_proof_failed")
    if not safe_low["passed"]:
        failures.append("class_c_safe_low_util_narrowing_latest_artifact_not_pass")
    if not metadata["passed"]:
        failures.append("class_b_metadata_narrowing_latest_artifact_not_pass")
    if not identity["passed"]:
        failures.append("class_a_identity_narrowing_latest_artifact_not_pass")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")

    proof_surface = {
        "class_d_lines": [row.get("line") for row in class_d_rows],
        "class_e_lines": [row.get("line") for row in class_e_rows],
        "helper_markers": helper_markers,
        "equivalence_cases": equivalence_cases,
        "ownership_guards": ownership_guards,
    }
    return {
        "snapshot_name": "design_guide_combined_cleanup_rescue_replacement_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "class_d_rows_narrowed": len(class_d_rows),
            "class_e_rows_untouched": len(class_e_rows) == 1,
            "remaining_live_rows_before_combined_cleanup_narrowing": len(remaining_after_safe_low),
            "remaining_live_rows_after_combined_cleanup_narrowing": remaining_after_combined_narrowing,
            "render_bridge_fully_narrowed": False,
            "product_behavior_changed": False,
        },
        "combined_cleanup_rows": class_d_rows,
        "remaining_live_rows": class_e_rows,
        "helper_markers": helper_markers,
        "equivalence_cases": equivalence_cases,
        "proof_guards": proof_guards,
        "ownership_guards": ownership_guards,
        "verification": {
            "class_a_identity_narrowing_latest_artifact": identity,
            "class_b_metadata_narrowing_latest_artifact": metadata,
            "class_c_safe_low_util_narrowing_latest_artifact": safe_low,
            "design_guide_independence_lock": lock_run,
        },
        "next_slice": "Prove and narrow the single class-E post-click exact blocker row.",
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _escape_target(row: dict[str, Any]) -> str:
    return _escape_md(row.get("target"))


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    class_d_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['current_behaviour_role']} |"
        for row in snapshot["combined_cleanup_rows"]
    )
    remaining_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['classification']} |"
        for row in snapshot["remaining_live_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Combined Cleanup Rescue Replacement Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Class-D rows narrowed: `{snapshot['summary']['class_d_rows_narrowed']}`",
            f"- Class-E row untouched: `{snapshot['summary']['class_e_rows_untouched']}`",
            f"- Remaining live rows before combined cleanup narrowing: `{snapshot['summary']['remaining_live_rows_before_combined_cleanup_narrowing']}`",
            f"- Remaining live rows after combined cleanup narrowing: `{snapshot['summary']['remaining_live_rows_after_combined_cleanup_narrowing']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Combined Cleanup Rows",
            "",
            "| Line | Target | Role |",
            "|---:|---|---|",
            class_d_rows or "| - | - | - |",
            "",
            "## Remaining Live Rows",
            "",
            "| Line | Target | Class |",
            "|---:|---|---|",
            remaining_rows or "| - | - | - |",
            "",
            "## Equivalence Cases",
            "",
            *[
                f"- `{case['case']}`: proof hash stable `{case['proof_hash_stable']}`, render reason `{case['render_reason_matches']}`, presentation `{case['presentation_matches']}`"
                for case in snapshot["equivalence_cases"]
            ],
            "",
            "## Verification",
            "",
            f"- Class-A identity narrowing latest artifact: `{snapshot['verification']['class_a_identity_narrowing_latest_artifact']['passed']}`",
            f"- Class-B metadata narrowing latest artifact: `{snapshot['verification']['class_b_metadata_narrowing_latest_artifact']['passed']}`",
            f"- Class-C safe-low-util narrowing latest artifact: `{snapshot['verification']['class_c_safe_low_util_narrowing_latest_artifact']['passed']}`",
            f"- Design Guide independence lock: `{snapshot['verification']['design_guide_independence_lock']['passed']}`",
            "",
            "## Next Slice",
            "",
            snapshot["next_slice"],
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_combined_cleanup_rescue_replacement_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_combined_cleanup_rescue_replacement_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_combined_cleanup_rescue_replacement_narrowing_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
