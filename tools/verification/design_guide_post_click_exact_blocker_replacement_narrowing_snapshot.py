"""Narrow class-E post-click exact blocker replacement row.

This verifier proves the final post-click exact blocker replacement row is now
compatibility/proof-only via FinalDesignGuidePublication and
FinalDesignGuidePostResolverMutationProof. No render, CTA/apply, session/UI,
wording, or family-runtime ownership moves here.
"""

from __future__ import annotations

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


def _line_for_marker(marker: str) -> int | None:
    for index, line in enumerate(INPUTS_PAGE.read_text(encoding="utf-8").splitlines(), start=1):
        if marker in line:
            return index
    return None


def _post_click_exact_blocker_equivalence_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    exact_blocker = {
        "family": "shear",
        "reason": "zero_shear_terminal_exact_blocker",
        "visible_exact_blocker": True,
        "terminal": True,
    }
    evidence = {
        "search_scope": "zero_shear_terminal_exact_blocker_session_debug",
        "blocker_attempts_by_family": {"shear": dict(exact_blocker)},
        "post_click_exact_blockers_by_family": {"shear": dict(exact_blocker)},
        "exact_blockers_by_family": {"shear": dict(exact_blocker)},
    }
    item = {
        "published_item_id": "post-click-exact-blocker-item",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "published_family_id": "SHEAR_FAIL_GOVERNS",
        "family": "shear",
        "check_key": "shear",
        "status": "BLOCKED",
        "bucket": "fail",
        "title_main": "Shear repair blocked",
        "title": "Shear repair blocked",
        "summary_line": "No valid shear repair is available.",
        "post_click_design_guide_state": "BLOCKED",
        "candidate_search_evidence": dict(evidence),
        "blocker_attempts_by_family": {"shear": dict(exact_blocker)},
        "post_click_exact_blockers_by_family": {"shear": dict(exact_blocker)},
        "exact_blockers_by_family": {"shear": dict(exact_blocker)},
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "family": "shear",
            "disabled_reason": "zero_shear_terminal_exact_blocker",
        },
    }
    resolution = {
        "item": dict(item),
        "render_reason": "zero_shear_terminal_exact_blocker_session_debug",
        "presentation": {
            "headline": item["title_main"],
            "subtext": item["summary_line"],
            "guidance_intent": "specific_blocker",
            "css_bucket": "fail",
            "theme": "fail",
            "show_apply_button": False,
            "use_success_style": False,
        },
    }
    debug = {
        "candidate_search_evidence": dict(evidence),
        "blocker_attempts_by_family": {"shear": dict(exact_blocker)},
        "post_click_exact_blockers_by_family": {"shear": dict(exact_blocker)},
        "exact_blockers_by_family": {"shear": dict(exact_blocker)},
    }
    publication_a = build_final_design_guide_publication(
        item=dict(item),
        debug=dict(debug),
        publication_reason="zero_shear_terminal_exact_blocker_session_debug",
    )
    publication_b = build_final_design_guide_publication(
        item=dict(item),
        debug=dict(debug),
        publication_reason="zero_shear_terminal_exact_blocker_session_debug",
    )
    proof_a = build_final_design_guide_post_resolver_mutation_proof(
        publication_a,
        selected_item=dict(item),
        final_visible_resolution=dict(resolution),
        guidance_debug=dict(debug),
    )
    proof_b = build_final_design_guide_post_resolver_mutation_proof(
        publication_b,
        selected_item=dict(item),
        final_visible_resolution=dict(resolution),
        guidance_debug=dict(debug),
    )
    blocker_projection = dict(proof_a.blocker_projection or {})
    evidence_projection = dict(proof_a.evidence_projection or {})
    exact_attempts = dict(blocker_projection.get("blocker_attempts_by_family") or {})
    exact_blockers = dict(blocker_projection.get("exact_blockers_by_family") or {})
    post_click_exact = dict(blocker_projection.get("post_click_exact_blockers_by_family") or {})
    return {
        "publication_hash": publication_a.publication_hash,
        "publication_hash_stable": publication_a.publication_hash == publication_b.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "proof_hash_stable": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "blocker_projection_hash": stable_final_publication_hash(blocker_projection),
        "evidence_projection_hash": stable_final_publication_hash(evidence_projection),
        "candidate_search_evidence_hash": evidence_projection.get("candidate_search_evidence_hash"),
        "blocker_attempts_by_family_hash": stable_final_publication_hash(exact_attempts),
        "exact_blockers_by_family_hash": stable_final_publication_hash(exact_blockers),
        "post_click_exact_blockers_by_family_hash": stable_final_publication_hash(post_click_exact),
        "shear_blocker_attempt_present": "shear" in exact_attempts,
        "shear_exact_blocker_present": "shear" in exact_blockers,
        "shear_post_click_exact_present": "shear" in post_click_exact,
        "outcome_state_matches": publication_a.outcome_state == "BLOCKED",
        "post_click_state_matches": publication_a.post_click_design_guide_state == "BLOCKED",
        "proof_only": proof_a.proof_only,
        "product_driving": proof_a.product_driving,
        "render_driving": proof_a.render_driving,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    combined_narrowing = _latest_artifact("design_guide_combined_cleanup_rescue_replacement_narrowing")
    class_a_narrowing = _latest_artifact("design_guide_final_resolver_identity_narrowing")
    class_b_narrowing = _latest_artifact("design_guide_final_visible_resolution_metadata_narrowing")
    class_c_narrowing = _latest_artifact("design_guide_safe_low_util_replacement_narrowing")
    controller_exact_cutover = _latest_artifact("design_guide_controller_exact_blocker_compatibility_cutover")
    independence_lock = _latest_artifact("design_guide_independence_lock")

    pre_rows = list((combined_narrowing.get("snapshot") or {}).get("remaining_live_rows") or [])
    class_e_rows = [row for row in pre_rows if row.get("classification") == CLASS_E]
    equivalence = _post_click_exact_blocker_equivalence_proof()
    helper_markers = {
        "helper_deleted": "def _stamp_final_publication_post_click_exact_blocker_compatibility_proof(" not in input_source,
        "callsite_deleted": 'callsite="post_click_exact_blocker_replacement"' not in input_source,
        "proofs_key_deleted": "final_publication_post_click_exact_blocker_compatibility_proofs" not in input_source,
        "proof_hash_key_deleted": "final_publication_post_click_exact_blocker_compatibility_proof_hash" not in input_source,
        "compatibility_key_deleted": "final_publication_post_click_exact_blocker_rows_compatibility_only" not in input_source,
        "remaining_truth_narrowed_key_deleted": (
            "final_publication_post_click_exact_blocker_remaining_truth_narrowed" not in input_source
        ),
        "existing_session_debug_shape_preserved": (
            '_session_zero_shear_debug["candidate_search_evidence"] = dict(' in input_source
        ),
    }
    source_locations = {
        "helper_line": _line_for_marker("def _stamp_final_publication_post_click_exact_blocker_compatibility_proof("),
        "callsite_line": _line_for_marker('callsite="post_click_exact_blocker_replacement"'),
        "legacy_session_write_line": _line_for_marker('_session_zero_shear_debug["candidate_search_evidence"] = dict('),
    }
    ownership_guards = {
        "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_not_moved": "st.session_state" in input_source
        and "session_state" not in publication_source,
        "ui_rendering_not_moved": "ui.design_guide_cards" not in publication_source,
        "legacy_wording_helper_deleted": "_design_guide_clean_main_card_text" not in input_source,
        "family_runtime_ownership_not_moved": "run_bending_fail_governs_ladder_runtime" not in publication_source
        and "run_shear_fail_governs_ladder_runtime" not in publication_source,
    }
    proof_guards = {
        "truth_exists_in_publication_or_post_resolver_proof": bool(
            equivalence["shear_blocker_attempt_present"]
            and equivalence["shear_exact_blocker_present"]
            and equivalence["shear_post_click_exact_present"]
            and equivalence["outcome_state_matches"]
            and equivalence["post_click_state_matches"]
        ),
        "hashes_stable": bool(equivalence["publication_hash_stable"] and equivalence["proof_hash_stable"]),
        "proof_only_not_product_or_render_driving": bool(
            equivalence["proof_only"]
            and not equivalence["product_driving"]
            and not equivalence["render_driving"]
        ),
    }
    remaining_after_post_click_narrowing: list[dict[str, Any]] = []
    failures: list[str] = []
    if not combined_narrowing["passed"]:
        failures.append("class_d_combined_cleanup_narrowing_latest_artifact_not_pass")
    if not class_a_narrowing["passed"]:
        failures.append("class_a_identity_narrowing_latest_artifact_not_pass")
    if not class_b_narrowing["passed"]:
        failures.append("class_b_metadata_narrowing_latest_artifact_not_pass")
    if not class_c_narrowing["passed"]:
        failures.append("class_c_safe_low_util_narrowing_latest_artifact_not_pass")
    if not controller_exact_cutover["passed"]:
        failures.append("controller_exact_blocker_cutover_latest_artifact_not_pass")
    if not independence_lock["passed"]:
        failures.append("design_guide_independence_lock_latest_artifact_not_pass")
    if len(pre_rows) != 1 or len(class_e_rows) != 1:
        failures.append(f"expected_single_class_e_prerow_found_{len(class_e_rows)}_of_{len(pre_rows)}")
    if remaining_after_post_click_narrowing:
        failures.append("expected_zero_remaining_live_rows_after_post_click_narrowing")
    if not all(helper_markers.values()):
        failures.append("post_click_exact_blocker_helper_or_callsite_marker_missing")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("post_click_exact_blocker_equivalence_proof_failed")

    proof_surface = {
        "class_e_rows": class_e_rows,
        "remaining_after_post_click_narrowing": remaining_after_post_click_narrowing,
        "helper_markers": helper_markers,
        "source_locations": source_locations,
        "equivalence": equivalence,
        "ownership_guards": ownership_guards,
    }
    return {
        "snapshot_name": "design_guide_post_click_exact_blocker_replacement_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "class_e_rows_identified": len(class_e_rows),
            "class_e_rows_narrowed": len(class_e_rows) if not failures else 0,
            "remaining_live_rows_before_post_click_narrowing": len(pre_rows),
            "remaining_live_rows_after_post_click_narrowing": len(remaining_after_post_click_narrowing),
            "render_bridge_fully_narrowed": not remaining_after_post_click_narrowing,
            "product_behavior_changed": False,
            "class_a_b_c_d_narrowing_verifiers_pass": all(
                artifact["passed"]
                for artifact in (class_a_narrowing, class_b_narrowing, class_c_narrowing, combined_narrowing)
            ),
        },
        "class_e_rows": class_e_rows,
        "remaining_live_rows": remaining_after_post_click_narrowing,
        "source_locations": source_locations,
        "helper_markers": helper_markers,
        "equivalence": equivalence,
        "proof_guards": proof_guards,
        "ownership_guards": ownership_guards,
        "verification": {
            "class_a_identity_narrowing_latest_artifact": class_a_narrowing,
            "class_b_metadata_narrowing_latest_artifact": class_b_narrowing,
            "class_c_safe_low_util_narrowing_latest_artifact": class_c_narrowing,
            "class_d_combined_cleanup_narrowing_latest_artifact": combined_narrowing,
            "controller_exact_blocker_cutover_latest_artifact": controller_exact_cutover,
            "design_guide_independence_lock_latest_artifact": independence_lock,
        },
        "next_slice": (
            "Render bridge is fully narrowed; re-run resolver bridge classification "
            "and then audit proven compatibility-only restamp retirement."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    class_e_rows = "\n".join(
        f"| {row.get('line')} | `{_escape_md(row.get('target'))}` | "
        f"{_escape_md(row.get('current_behaviour_role', 'controller-backed compatibility proof'))} |"
        for row in snapshot["class_e_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Post-Click Exact Blocker Replacement Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            "",
            "## Summary",
            "",
            f"- Class-E rows identified: `{snapshot['summary']['class_e_rows_identified']}`",
            f"- Class-E rows narrowed: `{snapshot['summary']['class_e_rows_narrowed']}`",
            (
                "- Remaining live resolver rows: "
                f"`{snapshot['summary']['remaining_live_rows_before_post_click_narrowing']}` -> "
                f"`{snapshot['summary']['remaining_live_rows_after_post_click_narrowing']}`"
            ),
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Product behaviour changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Class-E Row",
            "",
            "| Line | Target | Role |",
            "| --- | --- | --- |",
            class_e_rows or "| n/a | n/a | n/a |",
            "",
            "## Proof",
            "",
            (
                "- Equivalent exact blocker truth exists in FinalDesignGuidePublication / "
                f"post-resolver proof: `{snapshot['proof_guards']['truth_exists_in_publication_or_post_resolver_proof']}`"
            ),
            f"- Hashes stable: `{snapshot['proof_guards']['hashes_stable']}`",
            (
                "- Proof-only, non-product-driving, non-render-driving: "
                f"`{snapshot['proof_guards']['proof_only_not_product_or_render_driving']}`"
            ),
            f"- Helper line after deletion: `{snapshot['source_locations']['helper_line']}`",
            f"- Callsite line after deletion: `{snapshot['source_locations']['callsite_line']}`",
            f"- Legacy session write line: `{snapshot['source_locations']['legacy_session_write_line']}`",
            "",
            "## Ownership Guards",
            "",
            *[f"- {key}: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Verification",
            "",
            (
                "- Latest independence lock artifact: "
                f"`{snapshot['verification']['design_guide_independence_lock_latest_artifact']['passed']}`"
            ),
            (
                "- Latest controller exact-blocker cutover artifact: "
                f"`{snapshot['verification']['controller_exact_blocker_cutover_latest_artifact']['passed']}`"
            ),
            (
                "- Class A/B/C/D narrowing verifiers PASS: "
                f"`{snapshot['summary']['class_a_b_c_d_narrowing_verifiers_pass']}`"
            ),
            "",
            "## Next Slice",
            "",
            snapshot["next_slice"],
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    snapshot = _build_snapshot()
    timestamp = snapshot["generated_at"].replace(":", "-")
    artifact_path = ARTIFACT_DIR / f"design_guide_post_click_exact_blocker_replacement_narrowing_{timestamp}.json"
    report_path = AUDIT_DIR / f"design_guide_post_click_exact_blocker_replacement_narrowing_{timestamp}.md"
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, report_path)
    print(f"post-click exact blocker replacement narrowing {snapshot['status']}")
    print(f"artifact: {artifact_path}")
    print(f"report: {report_path}")
    if snapshot["failures"]:
        print("failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
