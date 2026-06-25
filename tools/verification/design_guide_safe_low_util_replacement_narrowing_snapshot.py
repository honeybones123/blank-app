"""Narrow class-C safe-low-util replacement rows.

This verifier proves the three safe-low-util replacement rows are represented
by FinalDesignGuidePublication / FinalDesignGuidePostResolverMutationProof and
are now compatibility/proof-only. Class D/E rows remain untouched.
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
METADATA_NARROWING = (
    ROOT / "tools" / "verification" / "design_guide_final_visible_resolution_metadata_narrowing_snapshot.py"
)

CLASS_C = "C. safe-low-util action replacement"
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


def _load_metadata_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_final_visible_resolution_metadata_narrowing_snapshot",
        METADATA_NARROWING,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load metadata narrowing snapshot")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remaining_after_metadata() -> list[dict[str, Any]]:
    module = _load_metadata_module()
    snapshot = module._build_snapshot()
    return list(snapshot.get("remaining_live_rows") or [])


def _safe_low_util_equivalence_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    item = {
        "published_item_id": "safe-low-util-action-item",
        "final_visible_item_id": "safe-low-util-action-item",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "family": "bending",
        "check_key": "bending",
        "status": "ACTION",
        "bucket": "info",
        "title_main": "Bending cleanup - best safe action",
        "title": "Bending cleanup - best safe action",
        "summary_line": "Apply the best safe low-util cleanup action.",
        "post_click_design_guide_state": "ACTION",
        "final_visible_resolver_reason": "visible_safe_low_util_cleanup_from_blocker_evidence",
        "candidate_id": "safe-low-util-candidate",
        "source_candidate_id": "safe-low-util-source",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "candidate_id": "safe-low-util-candidate",
            "source_candidate_id": "safe-low-util-source",
            "updates": {"D": 925.0},
            "expected_util": 0.84,
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "family": "bending",
            "candidate_id": "safe-low-util-candidate",
            "source_candidate_id": "safe-low-util-source",
            "updates": {"D": 925.0},
        },
        "candidate_search_evidence": {
            "best_safe_partial_cleanup": True,
            "safe_incremental_cleanup_below_final_threshold": True,
            "target_band_candidate_count": 0,
        },
    }
    resolution = {
        "item": dict(item),
        "render_reason": "visible_safe_low_util_cleanup_from_blocker_evidence",
        "presentation": {"headline": item["title_main"], "guidance_intent": "efficiency_tightening"},
    }
    publication = build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason="visible_safe_low_util_cleanup_from_blocker_evidence",
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
        "publication_hash": publication.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "proof_hash_stable": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "cta_hash": stable_final_publication_hash(cta),
        "display_hash": stable_final_publication_hash(display),
        "evidence_hash": stable_final_publication_hash(evidence),
        "resolver_projection_hash": stable_final_publication_hash(proof_a.resolver_projection),
        "selected_item_identity_hash": stable_final_publication_hash(proof_a.selected_item_identity),
        "action_type_matches": cta.get("action_type") == "apply_resolved_candidate",
        "source_candidate_matches": cta.get("source_candidate_id") == "safe-low-util-source",
        "render_reason_matches": proof_a.resolver_projection.get("render_reason")
        == "visible_safe_low_util_cleanup_from_blocker_evidence",
        "proof_only": proof_a.proof_only,
        "product_driving": proof_a.product_driving,
        "render_driving": proof_a.render_driving,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    remaining_after_metadata = _remaining_after_metadata()
    class_c_rows = [row for row in remaining_after_metadata if row.get("classification") == CLASS_C]
    other_rows = [row for row in remaining_after_metadata if row.get("classification") != CLASS_C]
    other_class_counts = {
        class_name: sum(1 for row in other_rows if row.get("classification") == class_name)
        for class_name in (CLASS_D, CLASS_E)
    }
    equivalence = _safe_low_util_equivalence_proof()
    helper_markers = {
        "helper_present": "def _stamp_final_publication_safe_low_util_replacement_compatibility_proof(" in input_source,
        "callsite_present": 'callsite="visible_safe_low_util_cleanup_from_blocker_evidence"' in input_source,
        "proofs_key_present": "final_publication_safe_low_util_replacement_compatibility_proofs" in input_source,
        "proof_hash_key_present": "final_publication_safe_low_util_replacement_compatibility_proof_hash" in input_source,
        "compatibility_key_present": "final_publication_safe_low_util_replacement_rows_compatibility_only" in input_source,
        "remaining_truth_not_narrowed_key_present": (
            "final_publication_safe_low_util_replacement_remaining_truth_narrowed" in input_source
        ),
        "combined_cleanup_not_product_driving": (
            'callsite="combined_cleanup_rescue_replacement"' not in input_source
            or (
                "final_publication_combined_cleanup_rescue_rows_compatibility_only" in input_source
                and "final_publication_combined_cleanup_rescue_remaining_truth_narrowed" in input_source
            )
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
        "truth_equivalent_in_publication_and_post_resolver_proof": bool(
            equivalence["action_type_matches"]
            and equivalence["source_candidate_matches"]
            and equivalence["render_reason_matches"]
        ),
        "proof_hash_stable": bool(equivalence["proof_hash_stable"]),
        "proof_is_not_product_or_render_driving": bool(
            equivalence["proof_only"]
            and not equivalence["product_driving"]
            and not equivalence["render_driving"]
        ),
    }
    metadata_narrowing = _latest_artifact("design_guide_final_visible_resolution_metadata_narrowing")
    identity_narrowing = _latest_artifact("design_guide_final_resolver_identity_narrowing")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    remaining_after_safe_low_narrowing = len(other_rows)
    failures: list[str] = []
    if len(class_c_rows) != 3:
        failures.append(f"expected_3_class_c_rows_found_{len(class_c_rows)}")
    if other_class_counts != {CLASS_D: 3, CLASS_E: 1}:
        failures.append("class_d_e_rows_not_preserved")
    if remaining_after_safe_low_narrowing != 4:
        failures.append(f"expected_4_remaining_live_rows_found_{remaining_after_safe_low_narrowing}")
    if not all(helper_markers.values()):
        failures.append("safe_low_util_helper_or_callsite_marker_missing")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("safe_low_util_equivalence_proof_failed")
    if not metadata_narrowing["passed"]:
        failures.append("class_b_metadata_narrowing_latest_artifact_not_pass")
    if not identity_narrowing["passed"]:
        failures.append("class_a_identity_narrowing_latest_artifact_not_pass")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")

    proof_surface = {
        "class_c_lines": [row.get("line") for row in class_c_rows],
        "remaining_lines": [row.get("line") for row in other_rows],
        "helper_markers": helper_markers,
        "equivalence": equivalence,
        "ownership_guards": ownership_guards,
    }
    return {
        "snapshot_name": "design_guide_safe_low_util_replacement_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "class_c_rows_narrowed": len(class_c_rows),
            "remaining_live_rows_before_safe_low_util_narrowing": len(remaining_after_metadata),
            "remaining_live_rows_after_safe_low_util_narrowing": remaining_after_safe_low_narrowing,
            "render_bridge_fully_narrowed": False,
            "class_d_e_rows_untouched": other_class_counts == {CLASS_D: 3, CLASS_E: 1},
            "product_behavior_changed": False,
            "other_class_counts": other_class_counts,
        },
        "safe_low_util_rows": class_c_rows,
        "remaining_live_rows": other_rows,
        "helper_markers": helper_markers,
        "equivalence": equivalence,
        "proof_guards": proof_guards,
        "ownership_guards": ownership_guards,
        "verification": {
            "class_a_identity_narrowing_latest_artifact": identity_narrowing,
            "class_b_metadata_narrowing_latest_artifact": metadata_narrowing,
            "design_guide_independence_lock": lock_run,
        },
        "next_slice": (
            "Prove and narrow class-D combined cleanup rescue replacement rows; "
            "leave class E untouched."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _escape_target(row: dict[str, Any]) -> str:
    return _escape_md(row.get("target"))


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    class_c_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['current_behaviour_role']} |"
        for row in snapshot["safe_low_util_rows"]
    )
    remaining_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['classification']} |"
        for row in snapshot["remaining_live_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Safe-Low-Util Replacement Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Class-C rows narrowed: `{snapshot['summary']['class_c_rows_narrowed']}`",
            f"- Remaining live rows before safe-low-util narrowing: `{snapshot['summary']['remaining_live_rows_before_safe_low_util_narrowing']}`",
            f"- Remaining live rows after safe-low-util narrowing: `{snapshot['summary']['remaining_live_rows_after_safe_low_util_narrowing']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Class D/E rows untouched: `{snapshot['summary']['class_d_e_rows_untouched']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Safe-Low-Util Rows",
            "",
            "| Line | Target | Role |",
            "|---:|---|---|",
            class_c_rows or "| - | - | - |",
            "",
            "## Remaining Live Rows",
            "",
            "| Line | Target | Class |",
            "|---:|---|---|",
            remaining_rows or "| - | - | - |",
            "",
            "## Equivalence Proof",
            "",
            f"- Action type matches: `{snapshot['equivalence']['action_type_matches']}`",
            f"- Source candidate matches: `{snapshot['equivalence']['source_candidate_matches']}`",
            f"- Render reason matches: `{snapshot['equivalence']['render_reason_matches']}`",
            f"- Proof hash stable: `{snapshot['equivalence']['proof_hash_stable']}`",
            "",
            "## Verification",
            "",
            f"- Class-A identity narrowing latest artifact: `{snapshot['verification']['class_a_identity_narrowing_latest_artifact']['passed']}`",
            f"- Class-B metadata narrowing latest artifact: `{snapshot['verification']['class_b_metadata_narrowing_latest_artifact']['passed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_safe_low_util_replacement_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_safe_low_util_replacement_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_safe_low_util_replacement_narrowing_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
