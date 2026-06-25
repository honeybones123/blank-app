"""Proof-only same-object snapshot for the render-stage final visible resolver.

This verifier focuses only on the render-stage resolver bridge. It compares
the static render-stage selected item surface against FinalDesignGuidePublication
and the collapsed-guidance adapter output, then classifies the bridge as:

A. can narrow to compatibility stamp
C. still owns unique resolver truth
D. deletion candidate
"""

from __future__ import annotations

import ast
import json
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

CLASS_A = "A. can narrow to compatibility stamp"
CLASS_C = "C. still owns unique resolver truth"
CLASS_D = "D. deletion candidate"

TRACKED_FIELDS = (
    "published_item_id",
    "source_candidate_id",
    "selected_family",
    "outcome_state",
    "guidance_intent",
    "post_click_design_guide_state",
    "cta_hash",
    "display_hash",
    "evidence_hash",
    "button_contract_hash",
    "visible_title_status",
    "apply_payload_fingerprint",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _function_bounds(source: str, function_name: str) -> tuple[int, int] | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _line_containing(source: str, needle: str, *, function_name: str | None = None) -> int | None:
    lines = source.splitlines()
    bounds = _function_bounds(source, function_name) if function_name else None
    for index, line in enumerate(lines, start=1):
        if needle not in line:
            continue
        if bounds and not (bounds[0] <= index <= bounds[1]):
            continue
        return index
    return None


def _context(source: str, line: int | None, radius: int = 90) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def _hash_lines(context: str, tokens: tuple[str, ...]) -> str | None:
    lines = [
        line.strip()
        for line in context.splitlines()
        if any(token in line for token in tokens)
    ]
    if not lines:
        return None
    return _stable_hash(lines)


def _surface_from_context(name: str, location: str | None, context: str) -> dict[str, Any]:
    return {
        "surface": name,
        "location": location,
        "field_hashes": {
            "published_item_id": _hash_lines(context, ("published_item_id", "final_visible_item_id")),
            "source_candidate_id": _hash_lines(context, ("source_candidate_id", "candidate_id")),
            "selected_family": _hash_lines(context, ("selected_family", "selected_action_family", "family", "check_key")),
            "outcome_state": _hash_lines(context, ("outcome_state", "render_reason", "guidance_branch", "final_state_class")),
            "guidance_intent": _hash_lines(context, ("guidance_intent",)),
            "post_click_design_guide_state": _hash_lines(context, ("post_click_design_guide_state", "design_guide_terminal_state")),
            "cta_hash": _hash_lines(context, ("final_publication_cta_hash", "button_contract", "_final_visible_contract")),
            "display_hash": _hash_lines(context, ("final_publication_display_hash", "title_main", "selected_title", "primary_card_title")),
            "evidence_hash": _hash_lines(context, ("candidate_search_evidence", "exact_blockers_by_family", "blocker")),
            "button_contract_hash": _hash_lines(context, ("button_contract", "_final_visible_contract")),
            "visible_title_status": _hash_lines(context, ("title_main", "title", "status", "bucket", "primary_card_title")),
            "apply_payload_fingerprint": _hash_lines(context, ("apply_payload", "updates", "selected_action_updates")),
        },
        "surface_hash": _stable_hash(context),
    }


def _build_publication_surface() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    class_line = _line_containing(source, "class FinalDesignGuidePublication")
    context = _context(source, class_line, radius=180)
    return _surface_from_context(
        "FinalDesignGuidePublication",
        None if class_line is None else f"design_brain/final_publication.py:{class_line}",
        context,
    )


def _build_adapter_surface() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    line = _line_containing(source, "def build_collapsed_guidance_item_from_final_publication")
    context = _context(source, line, radius=130)
    surface = _surface_from_context(
        "collapsed_guidance_adapter_output",
        None if line is None else f"design_brain/final_publication.py:{line}",
        context,
    )
    surface["adapter_markers"] = {
        "accepts_publication": "FinalDesignGuidePublication" in context,
        "published_item_id": '"published_item_id": publication.published_item_id' in context,
        "post_click_design_guide_state": '"post_click_design_guide_state": publication.post_click_design_guide_state' in context,
        "cta_hash": '"final_publication_cta_hash"' in context,
        "display_hash": '"final_publication_display_hash"' in context,
        "evidence_hash": '"final_publication_evidence_hash"' in context,
        "proof_only": '"collapsed_guidance_adapter_proof_only": True' in context,
        "non_product_driving": '"product_driving": False' in context,
    }
    return surface


def _build_render_surface() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    resolver_line = _line_containing(
        source,
        "_final_visible_resolution = resolve_final_visible_design_guide_item(",
        function_name="_render_fast_design_guidance_panel",
    )
    resolver_context = _context(source, resolver_line, radius=180)
    final_item_line = _line_containing(
        source,
        "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
        function_name="_render_fast_design_guidance_panel",
    )
    final_item_context = _context(source, final_item_line, radius=220)
    combined_context = "\n".join([resolver_context, final_item_context])
    surface = _surface_from_context(
        "render_stage_final_visible_selected_item",
        None if resolver_line is None else f"inputs_page.py:{resolver_line}",
        combined_context,
    )
    surface["resolver_line"] = resolver_line
    surface["final_item_binding_line"] = final_item_line
    surface["render_stage_mutation_markers"] = {
        "calls_resolver": "resolve_final_visible_design_guide_item(" in resolver_context,
        "publishes_contract_binding": "_publish_final_visible_design_guide_contract_binding(" in final_item_context,
        "mutates_final_visible_item": "_final_visible_item[" in combined_context or "_final_visible_item.update(" in combined_context,
        "updates_final_visible_resolution": '_final_visible_resolution["item"]' in combined_context,
        "updates_guidance_items": "guidance_items = [_final_visible_item]" in combined_context
        or "guidance_items = [dict(_final_visible_item)]" in combined_context,
        "updates_render_plan": 'render_plan["visible_guidance_items"]' in combined_context,
        "updates_guidance_debug": "guidance_debug[" in combined_context,
        "has_final_publication_adapter": "_collapsed_guidance_item_from_final_publication_authority(" in combined_context,
    }
    return surface


def _compare_surfaces(
    *,
    publication: dict[str, Any],
    adapter: dict[str, Any],
    render: dict[str, Any],
) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    pub_hashes = dict(publication.get("field_hashes") or {})
    adapter_hashes = dict(adapter.get("field_hashes") or {})
    render_hashes = dict(render.get("field_hashes") or {})
    for field in TRACKED_FIELDS:
        comparisons.append(
            {
                "field": field,
                "publication_present": bool(pub_hashes.get(field)),
                "adapter_present": bool(adapter_hashes.get(field)),
                "render_present": bool(render_hashes.get(field)),
                "publication_hash": pub_hashes.get(field),
                "adapter_hash": adapter_hashes.get(field),
                "render_hash": render_hashes.get(field),
                "adapter_matches_publication": bool(
                    pub_hashes.get(field)
                    and adapter_hashes.get(field)
                    and pub_hashes.get(field) == adapter_hashes.get(field)
                ),
                "render_matches_publication": bool(
                    pub_hashes.get(field)
                    and render_hashes.get(field)
                    and pub_hashes.get(field) == render_hashes.get(field)
                ),
            }
        )
    return comparisons


def _classify_render_bridge(render_surface: dict[str, Any], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    markers = dict(render_surface.get("render_stage_mutation_markers") or {})
    render_matches_all_publication = all(
        row["render_matches_publication"]
        for row in comparisons
        if row["publication_present"] and row["render_present"]
    )
    owns_unique_truth = bool(
        markers.get("calls_resolver")
        or markers.get("publishes_contract_binding")
        or markers.get("mutates_final_visible_item")
        or markers.get("updates_final_visible_resolution")
        or markers.get("updates_guidance_items")
        or markers.get("updates_render_plan")
        or markers.get("updates_guidance_debug")
    )
    if render_matches_all_publication and not owns_unique_truth:
        classification = CLASS_A
        smallest_truth = None
        next_slice = "Narrow render-stage resolver to a compatibility stamp."
    elif not owns_unique_truth:
        classification = CLASS_D
        smallest_truth = None
        next_slice = "Delete one proven dead render resolver path."
    else:
        classification = CLASS_C
        smallest_truth = "render-stage selected item mutation after final visible resolver"
        next_slice = (
            "Add a render-stage selected-item mutation proof that moves/normalizes "
            "post-resolver item mutations into FinalDesignGuidePublication before narrowing."
        )
    return {
        "classification": classification,
        "can_narrow_to_compatibility_stamp": classification == CLASS_A,
        "deletion_candidate": classification == CLASS_D,
        "still_owns_unique_resolver_truth": classification == CLASS_C,
        "render_matches_all_comparable_publication_fields": render_matches_all_publication,
        "render_stage_mutation_markers": markers,
        "smallest_remaining_render_truth": smallest_truth,
        "next_recommended_slice": next_slice,
    }


def _build_snapshot() -> dict[str, Any]:
    classification_artifact = _latest_artifact("design_guide_remaining_resolver_bridge_classification")
    cutover_artifact = _latest_artifact("design_guide_collapsed_replacement_authority_cutover")
    same_object_artifact = _latest_artifact("design_guide_compute_render_same_object_proof")
    lock_artifact = _latest_artifact("design_guide_independence_lock")
    publication_surface = _build_publication_surface()
    adapter_surface = _build_adapter_surface()
    render_surface = _build_render_surface()
    comparisons = _compare_surfaces(
        publication=publication_surface,
        adapter=adapter_surface,
        render=render_surface,
    )
    classification = _classify_render_bridge(render_surface, comparisons)
    failures: list[str] = []
    for name, artifact in {
        "remaining_resolver_bridge_classification": classification_artifact,
        "collapsed_replacement_authority_cutover": cutover_artifact,
        "compute_render_same_object_proof": same_object_artifact,
        "design_guide_independence_lock": lock_artifact,
    }.items():
        snapshot = artifact.get("snapshot") or {}
        if snapshot.get("status") not in {"PASS", "PARTIAL"}:
            failures.append(f"{name}_not_available_or_failed")
    if not all((adapter_surface.get("adapter_markers") or {}).values()):
        failures.append("collapsed_adapter_missing_required_marker")
    if render_surface.get("resolver_line") is None:
        failures.append("render_resolver_line_not_found")
    if render_surface.get("final_item_binding_line") is None:
        failures.append("render_final_item_binding_line_not_found")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "publication_surface": publication_surface,
        "adapter_surface": adapter_surface,
        "render_surface": render_surface,
        "comparisons": comparisons,
        "classification": classification,
        "source_artifacts": {
            "remaining_resolver_bridge_classification": classification_artifact.get("path"),
            "collapsed_replacement_authority_cutover": cutover_artifact.get("path"),
            "compute_render_same_object_proof": same_object_artifact.get("path"),
            "design_guide_independence_lock": lock_artifact.get("path"),
        },
    }
    return {
        "snapshot_name": "design_guide_render_stage_resolver_same_object",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "bridge_id": "render_stage_final_visible_resolver",
        "publication_surface": publication_surface,
        "collapsed_guidance_adapter_surface": adapter_surface,
        "render_stage_selected_item_surface": render_surface,
        "field_comparisons": comparisons,
        "classification": classification,
        "summary": {
            "classification": classification["classification"],
            "can_narrow_to_compatibility_stamp": classification["can_narrow_to_compatibility_stamp"],
            "deletion_candidate": classification["deletion_candidate"],
            "still_owns_unique_resolver_truth": classification["still_owns_unique_resolver_truth"],
            "smallest_remaining_render_truth": classification["smallest_remaining_render_truth"],
            "next_recommended_slice": classification["next_recommended_slice"],
        },
        "source_artifacts": proof_surface["source_artifacts"],
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    comparison_rows = [
        "| `{field}` | `{pub}` | `{adapter}` | `{render}` | `{adapter_match}` | `{render_match}` |".format(
            field=row["field"],
            pub=row["publication_present"],
            adapter=row["adapter_present"],
            render=row["render_present"],
            adapter_match=row["adapter_matches_publication"],
            render_match=row["render_matches_publication"],
        )
        for row in snapshot["field_comparisons"]
    ]
    markers = snapshot["classification"]["render_stage_mutation_markers"]
    body = "\n".join(
        [
            "# Design Guide Render-Stage Resolver Same-Object Proof",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Classification: `{snapshot['summary']['classification']}`",
            f"- Can narrow to compatibility stamp: `{snapshot['summary']['can_narrow_to_compatibility_stamp']}`",
            f"- Deletion candidate: `{snapshot['summary']['deletion_candidate']}`",
            f"- Still owns unique resolver truth: `{snapshot['summary']['still_owns_unique_resolver_truth']}`",
            f"- Smallest remaining render truth: `{snapshot['summary']['smallest_remaining_render_truth']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Render Mutation Markers",
            "",
            *[f"- `{key}`: `{value}`" for key, value in markers.items()],
            "",
            "## Field Comparison",
            "",
            "| Field | Publication Present | Adapter Present | Render Present | Adapter Matches Publication | Render Matches Publication |",
            "|---|---:|---:|---:|---:|---:|",
            *comparison_rows,
            "",
            "## Source Artifacts",
            "",
            f"- Remaining resolver bridge classification: `{snapshot['source_artifacts']['remaining_resolver_bridge_classification']}`",
            f"- Collapsed replacement cutover: `{snapshot['source_artifacts']['collapsed_replacement_authority_cutover']}`",
            f"- Compute/render same-object proof: `{snapshot['source_artifacts']['compute_render_same_object_proof']}`",
            f"- Independence lock: `{snapshot['source_artifacts']['design_guide_independence_lock']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- This is audit/proof only.",
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
    json_path = ARTIFACT_DIR / f"design_guide_render_stage_resolver_same_object_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_stage_resolver_same_object_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_render_stage_resolver_same_object {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
