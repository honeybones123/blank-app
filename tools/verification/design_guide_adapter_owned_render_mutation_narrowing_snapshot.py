"""Adapter-owned render-stage mutation narrowing snapshot.

This verifier narrows only render-stage mutations that are already represented
by FinalDesignGuidePostResolverMutationProof. It does not delete code, move
rendering, move CTA/apply/session/UI ownership, or narrow remaining resolver
truth.
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
MUTATION_SNAPSHOT = ROOT / "tools" / "verification" / "design_guide_render_stage_selected_item_mutation_snapshot.py"

CLASS_D = "D. unique resolver truth still not in FinalDesignGuidePublication"
NARROWED_CLASS = "adapter_owned_publication_truth_compatibility_proof_only"
REMAINING_CLASS = "remaining_live_resolver_truth_not_narrowed"


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


def _load_mutation_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_render_stage_selected_item_mutation_snapshot",
        MUTATION_SNAPSHOT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load render-stage mutation snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _target_text(row: dict[str, Any]) -> str:
    return "\n".join(
        str(row.get(key) or "")
        for key in ("target", "value", "line_text", "reason")
    )


def _is_adapter_owned_publication_truth(row: dict[str, Any]) -> tuple[bool, str]:
    """Return whether a D-row is now proof-covered by the bridge."""

    text = _target_text(row)
    target = str(row.get("target") or "")
    lower = text.lower()
    if target == "_final_visible_item" or target.startswith('_final_visible_resolution["'):
        return False, "whole selected-item/resolver replacement remains live resolver truth"
    if "_session_" in target:
        return False, "session/debug storage remains page-owned and is not narrowed here"
    if "candidate_search_evidence" in target:
        return True, "candidate-search evidence is represented by post-resolver proof evidence_projection"
    if "blocker_attempts_by_family" in target:
        return True, "blocker attempts are represented by post-resolver proof blocker_projection"
    if "exact_blockers_by_family" in target or "_zero_shear_exact_key" in target:
        return True, "exact blocker evidence is represented by post-resolver proof blocker_projection"
    if any(field in target for field in ('["util"]', '["expected_util"]', '["candidate_post_util"]')):
        return True, "utilisation fields are represented by post-resolver proof selected_item_projection"
    if '["resolved_candidate"]' in target:
        return True, "resolved candidate is represented by post-resolver proof selected_item_projection"
    if any(field in target for field in ('["action_type"]', '["candidate_id"]', '["source_candidate_id"]')):
        return True, "CTA/apply identity is represented by post-resolver proof selected_item_identity"
    if "post_click_exact_blockers_by_family" in lower:
        return True, "post-click blocker evidence is represented by post-resolver proof blocker_projection"
    return False, "row is not covered by adapter-owned post-resolver proof"


def _narrow_mutations() -> dict[str, Any]:
    module = _load_mutation_module()
    collection = module._collect_mutations()
    mutations = list(collection.get("mutations") or [])
    d_rows = [row for row in mutations if row.get("classification") == CLASS_D]
    narrowed: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for row in d_rows:
        is_adapter_owned, reason = _is_adapter_owned_publication_truth(row)
        out = {
            **row,
            "pre_narrowing_classification": row.get("classification"),
            "post_narrowing_classification": NARROWED_CLASS if is_adapter_owned else REMAINING_CLASS,
            "narrowing_reason": reason,
            "derived_from": "FinalDesignGuidePostResolverMutationProof" if is_adapter_owned else "live resolver",
            "compatibility_only": bool(is_adapter_owned),
            "proof_only": bool(is_adapter_owned),
        }
        if is_adapter_owned:
            narrowed.append(out)
        else:
            remaining.append(out)
    return {
        "collection": collection,
        "pre_narrowing_live_mutation_count": len(d_rows),
        "adapter_owned_narrowed_count": len(narrowed),
        "remaining_live_mutation_count": len(remaining),
        "narrowed_rows": narrowed,
        "remaining_live_rows": remaining,
    }


def _build_synthetic_bridge_proof() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_resolver_mutation_proof,
        build_final_design_guide_publication,
    )

    item = {
        "published_item_id": "adapter-owned-narrowing-item",
        "family": "combined",
        "status": "ACTION",
        "title": "Strengthening required",
        "post_click_design_guide_state": "ACTION",
        "candidate_id": "candidate-narrowing",
        "source_candidate_id": "source-narrowing",
        "action_type": "apply_resolved_candidate",
        "util": 1.1,
        "expected_util": 0.92,
        "candidate_post_util": 0.92,
        "resolved_candidate": {"candidate_id": "candidate-narrowing"},
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Apply repair",
            "action_type": "apply_resolved_candidate",
            "candidate_id": "candidate-narrowing",
            "source_candidate_id": "source-narrowing",
            "updates": {"D": 900.0},
        },
        "candidate_search_evidence": {"target_band_candidate_count": 1},
        "exact_blockers_by_family": {"bending": {"reason": "proof-only exact stop"}},
        "post_click_exact_blockers_by_family": {"bending": {"reason": "proof-only exact stop"}},
        "blocker_attempts_by_family": {"bending": [{"lane": "DEPTH_INCREASE"}]},
    }
    debug = {
        "candidate_search_evidence": dict(item["candidate_search_evidence"]),
        "exact_blockers_by_family": dict(item["exact_blockers_by_family"]),
        "post_click_exact_blockers_by_family": dict(item["post_click_exact_blockers_by_family"]),
        "blocker_attempts_by_family": dict(item["blocker_attempts_by_family"]),
        "button_contract": dict(item["button_contract"]),
    }
    resolution = {
        "item": dict(item),
        "render_reason": "render_stage_final_visible_resolver",
        "presentation": {"theme": "fail"},
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug=debug,
        publication_reason="adapter_owned_render_mutation_narrowing_snapshot",
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
    return {
        "publication_hash": publication.publication_hash,
        "proof_hash": proof_a.mutation_proof_hash,
        "stable_repeated_hash": proof_a.mutation_proof_hash == proof_b.mutation_proof_hash,
        "adapter_owned_mutation_truth": dict(proof_a.adapter_owned_mutation_truth),
        "remaining_resolver_truth": dict(proof_a.remaining_resolver_truth),
        "proof_only": proof_a.proof_only,
        "product_driving": proof_a.product_driving,
        "render_driving": proof_a.render_driving,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    narrowing = _narrow_mutations()
    bridge_proof = _build_synthetic_bridge_proof()
    bridge_run = _run("tools/verification/design_guide_live_post_resolver_mutation_bridge_snapshot.py")
    collapsed_cutover = _run("tools/verification/design_guide_collapsed_replacement_authority_cutover.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")

    helper_markers = {
        "compatibility_only_debug_stamp": "final_publication_post_resolver_mutation_compatibility_only" in input_source,
        "adapter_owned_rows_compatibility_stamp": (
            "final_publication_post_resolver_adapter_owned_rows_compatibility_only" in input_source
        ),
        "remaining_truth_not_narrowed_stamp": "final_publication_post_resolver_remaining_truth_narrowed" in input_source,
        "proof_helper_present": "def _stamp_final_publication_post_resolver_mutation_proof(" in input_source,
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
        "family_runtimes_not_touched_by_this_verifier": True,
    }
    proof_guards = {
        "proof_hash_stable": bool(bridge_proof["stable_repeated_hash"]),
        "adapter_owned_truth_represented": all(
            bool(bridge_proof["adapter_owned_mutation_truth"].get(key))
            for key in (
                "candidate_search_evidence",
                "blocker_attempts_by_family",
                "exact_blockers_by_family",
                "utilisation_projection",
                "resolved_candidate_projection",
                "cta_apply_identity",
            )
        ),
        "remaining_truth_still_live": (
            bridge_proof["remaining_resolver_truth"].get("classification")
            == "remaining_live_resolver_truth_not_narrowed"
        ),
        "proof_is_not_product_driving": bridge_proof["proof_only"] is True
        and bridge_proof["product_driving"] is False
        and bridge_proof["render_driving"] is False,
    }
    count_guards = {
        "fewer_live_rows": narrowing["remaining_live_mutation_count"]
        < narrowing["pre_narrowing_live_mutation_count"],
        "adapter_owned_rows_narrowed": narrowing["adapter_owned_narrowed_count"] > 0,
        "render_bridge_still_not_fully_narrowed": narrowing["remaining_live_mutation_count"] > 0,
    }

    failures: list[str] = []
    if not all(helper_markers.values()):
        failures.append("missing_page_debug_narrowing_markers")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not all(proof_guards.values()):
        failures.append("proof_guard_failed")
    if not all(count_guards.values()):
        failures.append("narrowing_count_guard_failed")
    if not bridge_run["passed"]:
        failures.append("live_post_resolver_bridge_snapshot_failed")
    if not collapsed_cutover["passed"]:
        failures.append("collapsed_replacement_authority_cutover_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")

    proof_surface = {
        "helper_markers": helper_markers,
        "ownership_guards": ownership_guards,
        "proof_guards": proof_guards,
        "count_guards": count_guards,
        "narrowing_counts": {
            "pre_narrowing_live_mutation_count": narrowing["pre_narrowing_live_mutation_count"],
            "adapter_owned_narrowed_count": narrowing["adapter_owned_narrowed_count"],
            "remaining_live_mutation_count": narrowing["remaining_live_mutation_count"],
        },
        "narrowed_lines": [row["line"] for row in narrowing["narrowed_rows"]],
        "remaining_live_lines": [row["line"] for row in narrowing["remaining_live_rows"]],
        "bridge_proof_hash": bridge_proof["proof_hash"],
    }
    return {
        "snapshot_name": "design_guide_adapter_owned_render_mutation_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "pre_narrowing_live_mutation_count": narrowing["pre_narrowing_live_mutation_count"],
            "adapter_owned_narrowed_count": narrowing["adapter_owned_narrowed_count"],
            "remaining_live_mutation_count": narrowing["remaining_live_mutation_count"],
            "render_bridge_fully_narrowed": False,
            "product_behavior_changed": False,
        },
        "helper_markers": helper_markers,
        "ownership_guards": ownership_guards,
        "proof_guards": proof_guards,
        "count_guards": count_guards,
        "bridge_proof": bridge_proof,
        "narrowed_rows": narrowing["narrowed_rows"],
        "remaining_live_rows": narrowing["remaining_live_rows"],
        "verification": {
            "live_post_resolver_mutation_bridge": bridge_run,
            "collapsed_replacement_authority_cutover": collapsed_cutover,
            "design_guide_independence_lock": lock_run,
        },
        "next_slice": (
            "Reclassify remaining live resolver truth; do not delete or narrow whole-item/"
            "resolution replacement rows until their authority moves or freezes."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    narrowed_rows = "\n".join(
        f"| {row['line']} | `{_escape_md(row['target'])}` | {_escape_md(row['narrowing_reason'])} |"
        for row in snapshot["narrowed_rows"]
    )
    remaining_rows = "\n".join(
        f"| {row['line']} | `{_escape_md(row['target'])}` | {_escape_md(row['narrowing_reason'])} |"
        for row in snapshot["remaining_live_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Adapter-Owned Render Mutation Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Pre-narrowing live mutation rows: `{snapshot['summary']['pre_narrowing_live_mutation_count']}`",
            f"- Adapter-owned rows narrowed to proof/compatibility: `{snapshot['summary']['adapter_owned_narrowed_count']}`",
            f"- Remaining live mutation rows: `{snapshot['summary']['remaining_live_mutation_count']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            "",
            "## Narrowed Adapter-Owned Rows",
            "",
            "| Line | Target | Reason |",
            "|---:|---|---|",
            narrowed_rows or "| - | - | None |",
            "",
            "## Remaining Live Resolver Rows",
            "",
            "| Line | Target | Reason |",
            "|---:|---|---|",
            remaining_rows or "| - | - | None |",
            "",
            "## Ownership Guards",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Verification",
            "",
            f"- Live post-resolver bridge: `{snapshot['verification']['live_post_resolver_mutation_bridge']['passed']}`",
            f"- Collapsed replacement authority cutover: `{snapshot['verification']['collapsed_replacement_authority_cutover']['passed']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_adapter_owned_render_mutation_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_adapter_owned_render_mutation_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_adapter_owned_render_mutation_narrowing_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
