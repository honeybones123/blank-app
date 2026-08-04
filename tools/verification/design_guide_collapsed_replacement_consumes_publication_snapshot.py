"""Proof-only collapsed-guidance replacement consumes-publication snapshot.

This verifier compares FinalDesignGuidePublication identity/CTA/display/evidence
surfaces against collapsed_guidance_items replacement and render selected item
surfaces. It does not wire replacement and does not change product behaviour.

Result semantics:
- PASS: replacement can consume FinalDesignGuidePublication as-is.
- PARTIAL: FinalDesignGuidePublication has the required truth, but a
  transformation adapter is still needed.
- FAIL: replacement requires truth missing from FinalDesignGuidePublication.
"""

from __future__ import annotations

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

REQUIRED_ADAPTER_WIRING_MARKERS = (
    "publication_reason=str(final_compute_resolution.get(\"render_reason\") or \"compute_publication_resolution\")",
    "publication_reason=\"late_evidence_contract_rebound\"",
    "publication_reason=\"post_evidence_contract_rebound\"",
)

REQUIRED_PUBLICATION_FIELDS = (
    "published_item_id",
    "post_click_design_guide_state",
    "selected_family",
    "outcome_state",
    "cta_hash",
    "display_hash",
    "blocker_evidence_hash",
    "publication_hash",
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


def _surface_by_name(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(surface.get("surface")): dict(surface)
        for surface in snapshot.get("surfaces") or []
        if isinstance(surface, dict)
    }


def _field_hash(surface: dict[str, Any], field: str) -> Any:
    if field == "published_item_id":
        value = surface.get("published_item_id")
        return value.get("hash") if isinstance(value, dict) else value
    if field == "post_click_design_guide_state":
        value = surface.get("post_click_design_guide_state")
        return value.get("hash") if isinstance(value, dict) else value
    if field == "selected_family":
        value = surface.get("selected_family")
        return value.get("hash") if isinstance(value, dict) else value
    if field == "outcome_state":
        value = surface.get("outcome_state")
        return value.get("hash") if isinstance(value, dict) else value
    if field == "cta_hash":
        return surface.get("cta_hash")
    if field == "display_hash":
        return surface.get("display_hash")
    if field == "blocker_evidence_hash":
        return surface.get("blocker_evidence_hash")
    if field == "publication_hash":
        return surface.get("publication_hash")
    return None


def _compare_surface(publication: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    field_rows = []
    matching = 0
    comparable = 0
    for field in REQUIRED_PUBLICATION_FIELDS:
        pub_hash = _field_hash(publication, field)
        other_hash = _field_hash(other, field)
        pub_present = bool((publication.get("field_presence") or {}).get(field)) or bool(pub_hash)
        other_present = bool((other.get("field_presence") or {}).get(field)) or bool(other_hash)
        same = bool(pub_hash and other_hash and pub_hash == other_hash)
        if pub_present and other_present:
            comparable += 1
            if same:
                matching += 1
        field_rows.append(
            {
                "field": field,
                "publication_present": pub_present,
                "target_present": other_present,
                "publication_hash": pub_hash,
                "target_hash": other_hash,
                "hash_match": same,
            }
        )
    return {
        "surface": other.get("surface"),
        "location": other.get("location"),
        "field_comparisons": field_rows,
        "comparable_fields": comparable,
        "matching_fields": matching,
        "all_required_fields_match": comparable == len(REQUIRED_PUBLICATION_FIELDS) and matching == comparable,
        "target_surface_hash": other.get("surface_hash"),
        "target_replacement_hash": other.get("collapsed_guidance_items_replacement_hash"),
    }


def _build_snapshot() -> dict[str, Any]:
    identity_artifact = _latest_artifact("design_guide_publication_identity_collapsed_replacement_snapshot")
    same_object_artifact = _latest_artifact("design_guide_compute_render_same_object_proof")
    resolver_artifact = _latest_artifact("design_guide_resolver_authority_bridge_snapshot")
    lock_artifact = _latest_artifact("design_guide_independence_lock")
    adapter_artifact = _latest_artifact("design_guide_collapsed_guidance_adapter_parity")

    identity = identity_artifact.get("snapshot") or {}
    adapter_snapshot = adapter_artifact.get("snapshot") or {}
    input_source = INPUTS_PAGE.read_text(encoding="utf-8") if INPUTS_PAGE.exists() else ""
    surfaces = _surface_by_name(identity)
    publication = surfaces.get("final_design_guide_publication_built_item", {})
    before = surfaces.get("collapsed_guidance_items_before_replacement", {})
    after = surfaces.get("collapsed_guidance_items_after_replacement", {})
    render = surfaces.get("render_stage_selected_item", {})
    resolver = surfaces.get("resolver_output_item", {})

    publication_presence = dict(publication.get("field_presence") or {})
    missing_truth = [
        field
        for field in REQUIRED_PUBLICATION_FIELDS
        if not publication_presence.get(field) and not _field_hash(publication, field)
    ]
    comparisons = [
        _compare_surface(publication, before),
        _compare_surface(publication, after),
        _compare_surface(publication, render),
        _compare_surface(publication, resolver),
    ]
    replacement_matches_as_is = bool(
        comparisons[1]["all_required_fields_match"]
        and after.get("collapsed_guidance_items_replacement_hash") == publication.get("surface_hash")
    )
    adapter_parity_pass = adapter_snapshot.get("status") == "PASS"
    adapter_wiring_markers = {
        marker: marker in input_source for marker in REQUIRED_ADAPTER_WIRING_MARKERS
    }
    adapter_helper_present = "_collapsed_guidance_item_from_final_publication_authority(" in input_source
    adapter_consumption_wired = bool(
        adapter_parity_pass
        and adapter_helper_present
        and all(adapter_wiring_markers.values())
    )
    adapter_needed = bool(not missing_truth and not replacement_matches_as_is and not adapter_consumption_wired)
    if missing_truth:
        status = "FAIL"
    elif replacement_matches_as_is or adapter_consumption_wired:
        status = "PASS"
    else:
        status = "PARTIAL"

    proof_surface = {
        "identity_artifact": identity_artifact.get("path"),
        "same_object_artifact": same_object_artifact.get("path"),
        "resolver_artifact": resolver_artifact.get("path"),
        "lock_artifact": lock_artifact.get("path"),
        "adapter_artifact": adapter_artifact.get("path"),
        "missing_truth": missing_truth,
        "comparisons": comparisons,
        "replacement_matches_as_is": replacement_matches_as_is,
        "adapter_consumption_wired": adapter_consumption_wired,
        "adapter_wiring_markers": adapter_wiring_markers,
        "adapter_needed": adapter_needed,
    }
    return {
        "snapshot_name": "design_guide_collapsed_replacement_consumes_publication_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "source_identity_artifact": identity_artifact.get("path"),
        "source_same_object_artifact": same_object_artifact.get("path"),
        "source_resolver_bridge_artifact": resolver_artifact.get("path"),
        "source_independence_lock_artifact": lock_artifact.get("path"),
        "source_adapter_parity_artifact": adapter_artifact.get("path"),
        "final_publication_surface": publication,
        "comparisons": comparisons,
        "adapter_wiring": {
            "adapter_parity_pass": adapter_parity_pass,
            "adapter_helper_present": adapter_helper_present,
            "required_markers": adapter_wiring_markers,
            "adapter_consumption_wired": adapter_consumption_wired,
        },
        "summary": {
            "final_publication_has_required_truth": not bool(missing_truth),
            "missing_truth_from_final_publication": missing_truth,
            "collapsed_replacement_can_consume_publication_as_is": replacement_matches_as_is,
            "collapsed_replacement_consumes_publication_via_adapter": adapter_consumption_wired,
            "transformation_adapter_needed": adapter_needed,
            "next_recommended_slice": (
                "Live collapsed replacement wiring can now be locked and remaining authority bridges can be reclassified"
                if adapter_consumption_wired
                else "Add proof-only adapter that builds collapsed guidance item shape from FinalDesignGuidePublication"
                if adapter_needed
                else (
                    "Wire collapsed replacement to consume FinalDesignGuidePublication"
                    if replacement_matches_as_is
                    else "Add missing truth to FinalDesignGuidePublication"
                )
            ),
        },
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": [] if status in {"PASS", "PARTIAL"} else ["missing_truth_from_final_publication"],
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    comparison_rows = []
    for comparison in snapshot["comparisons"]:
        comparison_rows.append(
            "| `{surface}` | `{location}` | `{matching}` | `{comparable}` | `{all_match}` | `{replacement}` |".format(
                surface=comparison["surface"],
                location=comparison["location"],
                matching=comparison["matching_fields"],
                comparable=comparison["comparable_fields"],
                all_match=comparison["all_required_fields_match"],
                replacement=comparison["target_replacement_hash"],
            )
        )
    body = "\n".join(
        [
            "# Design Guide Collapsed Replacement Consumes Publication Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Final publication has required truth: `{snapshot['summary']['final_publication_has_required_truth']}`",
            f"- Missing truth from final publication: `{snapshot['summary']['missing_truth_from_final_publication']}`",
            f"- Collapsed replacement can consume publication as-is: `{snapshot['summary']['collapsed_replacement_can_consume_publication_as_is']}`",
            f"- Collapsed replacement consumes publication via adapter: `{snapshot['summary']['collapsed_replacement_consumes_publication_via_adapter']}`",
            f"- Transformation adapter needed: `{snapshot['summary']['transformation_adapter_needed']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Surface Comparison",
            "",
            "| Compared Surface | Location | Matching Fields | Comparable Fields | All Required Match | Replacement Hash |",
            "|---|---|---:|---:|---:|---|",
            *comparison_rows,
            "",
            "## Source Artifacts",
            "",
            f"- Identity/collapsed replacement: `{snapshot['source_identity_artifact']}`",
            f"- Compute/render same-object: `{snapshot['source_same_object_artifact']}`",
            f"- Resolver authority bridge: `{snapshot['source_resolver_bridge_artifact']}`",
            f"- Independence lock: `{snapshot['source_independence_lock_artifact']}`",
            f"- Collapsed guidance adapter parity: `{snapshot['source_adapter_parity_artifact']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- Collapsed replacement wired: `False`",
            "- This snapshot is proof-only.",
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
    json_path = ARTIFACT_DIR / f"design_guide_collapsed_replacement_consumes_publication_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_collapsed_replacement_consumes_publication_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_collapsed_replacement_consumes_publication_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
