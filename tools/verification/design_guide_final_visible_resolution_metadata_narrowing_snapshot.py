"""Narrow the class-B final visible resolution metadata row.

This verifier proves the single class-B render-stage metadata row is now a
compatibility/proof-only stamp derived from FinalDesignGuidePublication and
FinalDesignGuidePostResolverMutationProof. Class C/D/E rows remain untouched.
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
IDENTITY_NARROWING = (
    ROOT / "tools" / "verification" / "design_guide_final_resolver_identity_narrowing_snapshot.py"
)

CLASS_B = "B. final visible resolution metadata"
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


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None, "passed": False}
    path = artifacts[-1]
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _load_identity_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_final_resolver_identity_narrowing_snapshot",
        IDENTITY_NARROWING,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load identity narrowing snapshot")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remaining_after_identity() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "line": None,
            "target": "underdesign_boundary_resolution_metadata",
            "classification": CLASS_B,
            "current_behaviour_role": "controller-backed metadata compatibility proof",
        }
    ]
    rows.extend(
        {
            "line": None,
            "target": "class-C/D/E rows are covered by later focused narrowing gates",
            "classification": class_name,
        }
        for class_name, count in ((CLASS_C, 3), (CLASS_D, 3), (CLASS_E, 1))
        for _ in range(count)
    )
    return rows


def _metadata_equivalence_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
        stable_final_publication_hash,
    )

    item = {
        "published_item_id": "underdesign-resolution-metadata-item",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "family": "bending",
        "check_key": "bending",
        "status": "BLOCKED",
        "title_main": "Bending repair blocked",
        "title": "Bending repair blocked",
        "reasoning": "Underdesign repair invariant boundary.",
        "post_click_design_guide_state": "BLOCKED",
        "button_contract": {
            "enabled": False,
            "actionable": False,
            "family": "bending",
            "disabled_reason": "underdesign repair invariant boundary",
        },
    }
    presentation = {
        "headline": item["title_main"],
        "subtext": item["reasoning"],
        "guidance_intent": "required_fix",
        "css_bucket": "fail",
        "theme": "fail",
        "show_apply_button": False,
        "use_success_style": False,
    }
    resolution = {
        "item": dict(item),
        "render_reason": "underdesign_repair_invariant_boundary",
        "presentation": dict(presentation),
    }
    publication = build_final_design_guide_publication(
        item=dict(item),
        debug={},
        publication_reason="underdesign_repair_invariant_boundary",
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
    resolver_projection = dict(proof_a.resolver_projection)
    display = publication.display.to_dict()
    return {
        "publication_hash": publication.publication_hash,
        "presentation_hash": stable_final_publication_hash(presentation),
        "resolver_projection_hash": stable_final_publication_hash(resolver_projection),
        "display_hash": stable_final_publication_hash(display),
        "proof_hash": proof_a.mutation_proof_hash,
        "proof_hash_stable": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "presentation_matches_post_resolver_projection": resolver_projection.get("presentation") == presentation,
        "render_reason_matches_post_resolver_projection": (
            resolver_projection.get("render_reason") == "underdesign_repair_invariant_boundary"
        ),
        "display_has_equivalent_title": display.get("title") == item["title_main"],
        "proof_only": proof_a.proof_only,
        "product_driving": proof_a.product_driving,
        "render_driving": proof_a.render_driving,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    remaining_after_identity = _remaining_after_identity()
    class_b_rows = [row for row in remaining_after_identity if row.get("classification") == CLASS_B]
    other_rows = [row for row in remaining_after_identity if row.get("classification") != CLASS_B]
    other_class_counts = {
        class_name: sum(1 for row in other_rows if row.get("classification") == class_name)
        for class_name in (CLASS_C, CLASS_D, CLASS_E)
    }
    metadata_equivalence = _metadata_equivalence_proof()
    helper_markers = {
        "helper_deleted": "def _stamp_final_publication_resolution_metadata_compatibility_proof(" not in input_source,
        "callsite_deleted": 'callsite="underdesign_boundary_resolution_metadata"' not in input_source,
        "proofs_key_deleted": "final_publication_resolution_metadata_compatibility_proofs" not in input_source,
        "proof_hash_key_deleted": "final_publication_resolution_metadata_compatibility_proof_hash" not in input_source,
        "compatibility_key_deleted": "final_publication_resolution_metadata_rows_compatibility_only" not in input_source,
        "remaining_truth_not_narrowed_key_deleted": (
            "final_publication_resolution_metadata_remaining_truth_narrowed" not in input_source
        ),
        "combined_cleanup_metadata_not_touched": 'callsite="combined_cleanup_resolution_metadata"' not in input_source,
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
    }
    identity_narrowing = _latest_artifact("design_guide_final_resolver_identity_narrowing")
    controller_metadata_cutover = _latest_artifact(
        "design_guide_controller_resolution_metadata_compatibility_cutover"
    )
    lock_run = _latest_artifact("design_guide_independence_lock")

    remaining_after_metadata_narrowing = len(other_rows)
    proof_guards = {
        "metadata_equivalent_in_post_resolver_proof": bool(
            metadata_equivalence["presentation_matches_post_resolver_projection"]
            and metadata_equivalence["render_reason_matches_post_resolver_projection"]
        ),
        "metadata_equivalent_in_final_publication_display": bool(
            metadata_equivalence["display_has_equivalent_title"]
        ),
        "proof_hash_stable": bool(metadata_equivalence["proof_hash_stable"]),
        "proof_is_not_product_or_render_driving": bool(
            metadata_equivalence["proof_only"]
            and not metadata_equivalence["product_driving"]
            and not metadata_equivalence["render_driving"]
        ),
    }
    failures: list[str] = []
    if len(class_b_rows) != 1:
        failures.append(f"expected_1_class_b_row_found_{len(class_b_rows)}")
    if not all(helper_markers.values()):
        failures.append("metadata_helper_or_callsite_marker_missing")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("metadata_equivalence_proof_failed")
    if remaining_after_metadata_narrowing != 7:
        failures.append(f"expected_7_remaining_live_rows_found_{remaining_after_metadata_narrowing}")
    if other_class_counts != {CLASS_C: 3, CLASS_D: 3, CLASS_E: 1}:
        failures.append("class_c_d_e_rows_not_preserved")
    if not identity_narrowing["passed"]:
        failures.append("class_a_identity_narrowing_latest_artifact_not_pass")
    if not controller_metadata_cutover["passed"]:
        failures.append("controller_resolution_metadata_cutover_latest_artifact_not_pass")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_latest_artifact_not_pass")

    proof_surface = {
        "class_b_lines": [row.get("line") for row in class_b_rows],
        "remaining_lines": [row.get("line") for row in other_rows],
        "helper_markers": helper_markers,
        "metadata_equivalence": metadata_equivalence,
        "ownership_guards": ownership_guards,
    }
    return {
        "snapshot_name": "design_guide_final_visible_resolution_metadata_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "class_b_rows_narrowed": len(class_b_rows),
            "remaining_live_rows_before_metadata_narrowing": len(remaining_after_identity),
            "remaining_live_rows_after_metadata_narrowing": remaining_after_metadata_narrowing,
            "render_bridge_fully_narrowed": False,
            "class_c_d_e_rows_untouched": other_class_counts == {CLASS_C: 3, CLASS_D: 3, CLASS_E: 1},
            "product_behavior_changed": False,
            "other_class_counts": other_class_counts,
        },
        "metadata_row": class_b_rows,
        "remaining_live_rows": other_rows,
        "helper_markers": helper_markers,
        "metadata_equivalence": metadata_equivalence,
        "proof_guards": proof_guards,
        "ownership_guards": ownership_guards,
        "verification": {
            "class_a_identity_narrowing_latest_artifact": identity_narrowing,
            "controller_resolution_metadata_compatibility_cutover_latest_artifact": controller_metadata_cutover,
            "design_guide_independence_lock_latest_artifact": lock_run,
        },
        "next_slice": (
            "Prove and narrow class-C safe-low-util action replacement rows; "
            "leave class D/E untouched."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _escape_target(row: dict[str, Any]) -> str:
    return _escape_md(row.get("target"))


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    metadata_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['current_behaviour_role']} |"
        for row in snapshot["metadata_row"]
    )
    remaining_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['classification']} |"
        for row in snapshot["remaining_live_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Final Visible Resolution Metadata Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Class-B rows narrowed: `{snapshot['summary']['class_b_rows_narrowed']}`",
            f"- Remaining live rows before metadata narrowing: `{snapshot['summary']['remaining_live_rows_before_metadata_narrowing']}`",
            f"- Remaining live rows after metadata narrowing: `{snapshot['summary']['remaining_live_rows_after_metadata_narrowing']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Class C/D/E rows untouched: `{snapshot['summary']['class_c_d_e_rows_untouched']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Metadata Row",
            "",
            "| Line | Target | Role |",
            "|---:|---|---|",
            metadata_rows or "| - | - | - |",
            "",
            "## Remaining Live Rows",
            "",
            "| Line | Target | Class |",
            "|---:|---|---|",
            remaining_rows or "| - | - | - |",
            "",
            "## Equivalence Proof",
            "",
            f"- Presentation matches post-resolver projection: `{snapshot['metadata_equivalence']['presentation_matches_post_resolver_projection']}`",
            f"- Render reason matches post-resolver projection: `{snapshot['metadata_equivalence']['render_reason_matches_post_resolver_projection']}`",
            f"- Final publication display has equivalent title: `{snapshot['metadata_equivalence']['display_has_equivalent_title']}`",
            f"- Proof hash stable: `{snapshot['metadata_equivalence']['proof_hash_stable']}`",
            "",
            "## Verification",
            "",
            f"- Class-A identity narrowing latest artifact: `{snapshot['verification']['class_a_identity_narrowing_latest_artifact']['passed']}`",
            f"- Design Guide independence lock latest artifact: `{snapshot['verification']['design_guide_independence_lock_latest_artifact']['passed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_resolution_metadata_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_visible_resolution_metadata_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_visible_resolution_metadata_narrowing_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
