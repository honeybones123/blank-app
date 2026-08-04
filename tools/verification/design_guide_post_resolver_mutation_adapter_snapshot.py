"""Proof-only post-resolver selected-item mutation adapter snapshot.

The snapshot proves that render-stage evidence, blocker, terminal, identity,
and utilisation mutations can be represented by a Design Brain proof object
without moving live resolver, render, CTA, apply, session, or UI behaviour.
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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_D = "D. unique resolver truth still not in FinalDesignGuidePublication"

ADAPTER_OWNED_REASONS = {
    "exact_blocker_evidence": "exact/blocker evidence can be represented by the post-resolver proof object",
    "candidate_search_evidence": "candidate search evidence can be represented by the post-resolver proof object",
    "blocker_attempts": "blocker attempt evidence can be represented by the post-resolver proof object",
    "utilisation_projection": "utilisation fields can be represented by the selected-item projection",
    "resolved_candidate_projection": "resolved candidate data can be represented by the selected-item projection",
    "identity_projection": "action/candidate/source identity can be represented by selected-item identity",
}

LIVE_RESOLVER_REASONS = {
    "selected_item_replacement": "whole selected-item replacement still belongs to the live resolver bridge",
    "resolver_item_replacement": "final-visible resolution item replacement still belongs to the live resolver bridge",
    "resolver_metadata": "render reason/presentation mutation is still resolver metadata",
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


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {"path": str(path), "snapshot": json.loads(path.read_text(encoding="utf-8"))}


def _module_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(str(node.module or ""))
    return sorted(set(imports))


def _build_adapter_case() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_publication,
        build_render_stage_post_resolver_item_mutation_proof,
    )

    item = {
        "published_item_id": "render-stage-item-001",
        "family": "combined",
        "selected_family_id": "COMBINED_BENDING_SHEAR_FAIL_GOVERNS",
        "status": "ACTION",
        "bucket": "action",
        "title": "Strengthening required",
        "post_click_design_guide_state": "ACTION",
        "design_guide_terminal_state": "ACTION",
        "candidate_id": "candidate_275",
        "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        "action_type": "apply_candidate",
        "util": 1.08,
        "expected_util": 0.91,
        "candidate_post_util": 0.91,
        "resolved_candidate": {"candidate_id": "candidate_275", "status": "PASS"},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_candidate",
            "family": "combined",
            "candidate_id": "candidate_275",
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "updates": {"D": 950.0, "lig_d": 20},
        },
        "action_payload": {
            "candidate_id": "candidate_275",
            "source_candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
            "updates": {"D": 950.0, "lig_d": 20},
        },
        "candidate_search_evidence": {
            "safe_executor_backed_candidate_found": True,
            "target_band_candidate_count": 1,
        },
        "exact_blockers_by_family": {
            "bending": {
                "no_second_cta_required": True,
                "reason": "exact below-floor cleanup stop",
            }
        },
        "post_click_exact_blockers_by_family": {
            "bending": {
                "no_second_cta_required": True,
                "reason": "post-click exact cleanup stop",
            }
        },
        "blocker_attempts_by_family": {"bending": [{"lane": "DEPTH_INCREASE"}]},
    }
    debug = {
        "candidate_search_evidence": {
            "safe_executor_backed_candidate_found": True,
            "target_band_candidate_count": 1,
        },
        "blocker_attempts_by_family": {"bending": [{"lane": "DEPTH_INCREASE"}]},
        "exact_blockers_by_family": dict(item["exact_blockers_by_family"]),
        "post_click_exact_blockers_by_family": dict(item["post_click_exact_blockers_by_family"]),
    }
    resolution = {
        "item": dict(item),
        "render_reason": "render_stage_final_visible_resolver",
        "presentation": {"primary_card": "action"},
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug=debug,
        publication_reason="render_stage_post_resolver_mutation_adapter_snapshot",
    )
    proof_a = build_render_stage_post_resolver_item_mutation_proof(
        publication,
        selected_item=item,
        final_visible_resolution=resolution,
        guidance_debug=debug,
    )
    proof_b = build_render_stage_post_resolver_item_mutation_proof(
        publication,
        selected_item=item,
        final_visible_resolution=resolution,
        guidance_debug=debug,
    )
    required_coverage = {
        "selected_item_identity": True,
        "candidate_search_evidence": True,
        "blocker_attempts_by_family": True,
        "exact_blockers_by_family": True,
        "terminal_state": True,
        "resolver_output": True,
        "utilisation_fields": True,
        "resolved_candidate": True,
        "cta_apply_identity": True,
    }
    coverage = dict(proof_a.mutation_target_coverage)
    return {
        "publication_hash": publication.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "stable_repeated_hash": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "required_coverage": required_coverage,
        "coverage": coverage,
        "missing_coverage": [
            key for key, required in required_coverage.items() if required and not coverage.get(key)
        ],
        "proof": proof_a.to_dict(),
    }


def _classify_target(target: str) -> tuple[str, str, str]:
    if "candidate_search_evidence" in target:
        return "adapter_owned_publication_truth", "candidate_search_evidence", ADAPTER_OWNED_REASONS["candidate_search_evidence"]
    if "blocker_attempts_by_family" in target:
        return "adapter_owned_publication_truth", "blocker_attempts", ADAPTER_OWNED_REASONS["blocker_attempts"]
    if "exact_blockers_by_family" in target or "_zero_shear_exact_key" in target:
        return "adapter_owned_publication_truth", "exact_blocker_evidence", ADAPTER_OWNED_REASONS["exact_blocker_evidence"]
    if any(field in target for field in ('["util"]', '["expected_util"]', '["candidate_post_util"]')):
        return "adapter_owned_publication_truth", "utilisation_projection", ADAPTER_OWNED_REASONS["utilisation_projection"]
    if '["resolved_candidate"]' in target:
        return "adapter_owned_publication_truth", "resolved_candidate_projection", ADAPTER_OWNED_REASONS["resolved_candidate_projection"]
    if any(field in target for field in ('["action_type"]', '["candidate_id"]', '["source_candidate_id"]')):
        return "adapter_owned_publication_truth", "identity_projection", ADAPTER_OWNED_REASONS["identity_projection"]
    if target == "_final_visible_item":
        return "remaining_live_resolver_truth", "selected_item_replacement", LIVE_RESOLVER_REASONS["selected_item_replacement"]
    if '_final_visible_resolution["item"]' in target:
        return "remaining_live_resolver_truth", "resolver_item_replacement", LIVE_RESOLVER_REASONS["resolver_item_replacement"]
    if '_final_visible_resolution["render_reason"]' in target or '_final_visible_resolution["presentation"]' in target:
        return "remaining_live_resolver_truth", "resolver_metadata", LIVE_RESOLVER_REASONS["resolver_metadata"]
    return "remaining_live_resolver_truth", "unclassified_resolver_truth", "target still needs bridge-specific resolver proof"


def _build_snapshot() -> dict[str, Any]:
    mutation_run = _run("tools/verification/design_guide_render_stage_selected_item_mutation_snapshot.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    cutover_run = _run("tools/verification/design_guide_collapsed_replacement_authority_cutover.py")
    mutation_artifact = _latest_artifact("design_guide_render_stage_selected_item_mutation_snapshot")
    mutation_snapshot = mutation_artifact.get("snapshot") or {}
    mutations = [
        row
        for row in list(mutation_snapshot.get("mutations") or [])
        if str(row.get("classification") or "") == CLASS_D
    ]
    classified = []
    for row in mutations:
        bucket, reason_key, reason = _classify_target(str(row.get("target") or ""))
        classified.append({**row, "adapter_split": bucket, "adapter_reason_key": reason_key, "adapter_reason": reason})

    adapter_case = _build_adapter_case()
    imports = _module_imports(FINAL_PUBLICATION)
    forbidden_imports = [
        module
        for module in imports
        if any(fragment in module.lower() for fragment in ("inputs_page", "streamlit", "session_state"))
    ]
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    adapter_source_present = "build_render_stage_post_resolver_item_mutation_proof" in source
    dataclass_present = "class FinalDesignGuidePostResolverMutationProof" in source
    forbidden_terms = [
        token
        for token in (
            "import inputs_page",
            "import streamlit",
            "st.session_state",
            "_record_rendered_design_guide_primary_apply_payload(",
            "_design_guide_dashboard_card_html_from_render_model(",
        )
        if token in source
    ]

    adapter_owned = [row for row in classified if row["adapter_split"] == "adapter_owned_publication_truth"]
    remaining_live = [row for row in classified if row["adapter_split"] == "remaining_live_resolver_truth"]
    failures: list[str] = []
    if not mutation_run["passed"]:
        failures.append("render_stage_selected_item_mutation_snapshot_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if not cutover_run["passed"]:
        failures.append("collapsed_replacement_authority_cutover_failed")
    if mutation_snapshot.get("status") != "PASS":
        failures.append("mutation_snapshot_not_pass")
    if not adapter_source_present or not dataclass_present:
        failures.append("adapter_surface_missing")
    if adapter_case["missing_coverage"]:
        failures.append("adapter_case_missing_required_coverage")
    if not adapter_case["stable_repeated_hash"]:
        failures.append("adapter_hash_not_stable")
    if forbidden_imports or forbidden_terms:
        failures.append("adapter_ownership_forbidden_terms")
    if not adapter_owned:
        failures.append("no_adapter_owned_mutations_identified")
    if not remaining_live:
        failures.append("no_remaining_live_resolver_truth_identified")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "adapter_case": {
            "proof_hash": adapter_case["proof_hash"],
            "coverage": adapter_case["coverage"],
        },
        "classified_mutations": [
            {
                "line": row.get("line"),
                "target": row.get("target"),
                "adapter_split": row.get("adapter_split"),
                "adapter_reason_key": row.get("adapter_reason_key"),
            }
            for row in classified
        ],
        "forbidden_imports": forbidden_imports,
        "forbidden_terms": forbidden_terms,
    }
    return {
        "snapshot_name": "design_guide_post_resolver_mutation_adapter_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "adapter_case": adapter_case,
        "mutation_source_artifact": mutation_artifact.get("path"),
        "unique_truth_mutation_count": len(mutations),
        "adapter_owned_publication_truth_count": len(adapter_owned),
        "remaining_live_resolver_truth_count": len(remaining_live),
        "classified_mutations": classified,
        "can_narrow_render_bridge_now": False,
        "object_ready_for_live_render_bridge_authority": False,
        "next_recommended_slice": "Build a live trace-only bridge that constructs this proof beside the render-stage resolver and compares hashes.",
        "ownership": {
            "product_behavior_changed": False,
            "proof_only": True,
            "rendering_moved": False,
            "cta_apply_moved": False,
            "session_ui_moved": False,
            "forbidden_imports": forbidden_imports,
            "forbidden_terms": forbidden_terms,
        },
        "verification": {
            "render_stage_selected_item_mutation_snapshot": mutation_run,
            "design_guide_independence_lock": lock_run,
            "collapsed_replacement_authority_cutover": cutover_run,
        },
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = [
        "| `{line}` | `{target}` | `{split}` | `{reason}` |".format(
            line=row.get("line"),
            target=str(row.get("target") or "").replace("|", "\\|"),
            split=row.get("adapter_split"),
            reason=row.get("adapter_reason_key"),
        )
        for row in snapshot["classified_mutations"]
    ]
    body = "\n".join(
        [
            "# Design Guide Post-Resolver Mutation Adapter Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Unique truth mutations reviewed: `{snapshot['unique_truth_mutation_count']}`",
            f"- Adapter-owned publication truth: `{snapshot['adapter_owned_publication_truth_count']}`",
            f"- Remaining live resolver truth: `{snapshot['remaining_live_resolver_truth_count']}`",
            f"- Can narrow render bridge now: `{snapshot['can_narrow_render_bridge_now']}`",
            f"- Object ready for live render bridge authority: `{snapshot['object_ready_for_live_render_bridge_authority']}`",
            f"- Next recommended slice: {snapshot['next_recommended_slice']}",
            "",
            "## Adapter Proof",
            "",
            f"- Proof hash: `{snapshot['adapter_case']['proof_hash']}`",
            f"- Stable repeated hash: `{snapshot['adapter_case']['stable_repeated_hash']}`",
            f"- Missing coverage: `{snapshot['adapter_case']['missing_coverage']}`",
            "",
            "## Mutation Split",
            "",
            "| Line | Target | Split | Reason |",
            "|---:|---|---|---|",
            *rows,
            "",
            "## Ownership",
            "",
            f"- Product behavior changed: `{snapshot['ownership']['product_behavior_changed']}`",
            f"- Rendering moved: `{snapshot['ownership']['rendering_moved']}`",
            f"- CTA/apply moved: `{snapshot['ownership']['cta_apply_moved']}`",
            f"- Session/UI moved: `{snapshot['ownership']['session_ui_moved']}`",
            f"- Forbidden imports: `{snapshot['ownership']['forbidden_imports']}`",
            f"- Forbidden terms: `{snapshot['ownership']['forbidden_terms']}`",
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
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_post_resolver_mutation_adapter_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_resolver_mutation_adapter_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_post_resolver_mutation_adapter_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
