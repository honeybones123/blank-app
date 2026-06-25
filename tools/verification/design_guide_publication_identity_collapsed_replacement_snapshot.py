"""Proof-only publication identity and collapsed-guidance replacement snapshot.

This snapshot maps how final published item identity is chosen and whether
collapsed_guidance_items replacement can be driven by FinalDesignGuidePublication
rather than independent resolver/rebound item replacement.

Expected result may be PARTIAL: that means the proof found the missing identity
field or envelope that must move into FinalDesignGuidePublication next.
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

TRACKED_FIELDS = (
    "published_item_id",
    "source_candidate_id",
    "selected_family",
    "outcome_state",
    "guidance_intent",
    "post_click_design_guide_state",
    "cta_hash",
    "display_hash",
    "blocker_evidence_hash",
    "publication_hash",
    "collapsed_guidance_items_replacement_hash",
)


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
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


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


def _function_range(source: str, function_name: str) -> tuple[int, int] | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _line_in_function(source: str, needle: str, function_name: str) -> int | None:
    lines = source.splitlines()
    bounds = _function_range(source, function_name)
    start, end = bounds or (1, len(lines))
    for line_no in range(start, min(end, len(lines)) + 1):
        if needle in lines[line_no - 1]:
            return line_no
    return None


def _context(source: str, line_no: int | None, radius: int = 28) -> str:
    if line_no is None:
        return ""
    lines = source.splitlines()
    start = max(1, int(line_no) - radius)
    end = min(len(lines), int(line_no) + radius)
    return "\n".join(lines[start - 1 : end])


def _hash_for_tokens(context: str, tokens: tuple[str, ...]) -> str | None:
    lines = [
        line.strip()
        for line in context.splitlines()
        if any(token in line for token in tokens)
    ]
    if not lines:
        return None
    return _stable_hash(lines)


def _has_any(context: str, tokens: tuple[str, ...]) -> bool:
    return any(token in context for token in tokens)


def _identity_surface(
    *,
    name: str,
    location: str | None,
    context: str,
    source_kind: str,
) -> dict[str, Any]:
    field_presence = {
        "published_item_id": _has_any(context, ("published_item_id", "final_visible_item_id")),
        "source_candidate_id": _has_any(context, ("source_candidate_id", "candidate_id")),
        "selected_family": _has_any(context, ("selected_action_family", "selected_family", "family", "check_key")),
        "outcome_state": _has_any(context, ("outcome_state", "render_reason", "guidance_branch", "button_contract_enabled")),
        "guidance_intent": "guidance_intent" in context,
        "post_click_design_guide_state": "post_click_design_guide_state" in context,
        "cta_hash": _has_any(context, ("button_contract", "cta_hash", "FinalDesignGuideCTA")),
        "display_hash": _has_any(context, ("display_hash", "FinalDesignGuideDisplay", "title", "selected_title")),
        "blocker_evidence_hash": _has_any(context, ("exact_blockers_by_family", "blocker_reason", "candidate_search_evidence")),
        "publication_hash": "publication_hash" in context or "_record_design_guide_publication_snapshot" in context,
        "collapsed_guidance_items_replacement_hash": "collapsed_guidance_items" in context,
    }
    return {
        "surface": name,
        "source_kind": source_kind,
        "location": location,
        "field_presence": field_presence,
        "published_item_id": {"hash": _hash_for_tokens(context, ("published_item_id", "final_visible_item_id"))},
        "source_candidate_id": {"hash": _hash_for_tokens(context, ("source_candidate_id", "candidate_id"))},
        "selected_family": {"hash": _hash_for_tokens(context, ("selected_action_family", "selected_family", "family", "check_key"))},
        "outcome_state": {"hash": _hash_for_tokens(context, ("outcome_state", "render_reason", "guidance_branch", "button_contract_enabled"))},
        "guidance_intent": {"hash": _hash_for_tokens(context, ("guidance_intent",))},
        "post_click_design_guide_state": {"hash": _hash_for_tokens(context, ("post_click_design_guide_state",))},
        "cta_hash": _hash_for_tokens(context, ("button_contract", "cta_hash", "FinalDesignGuideCTA", "apply_payload_fingerprint")),
        "display_hash": _hash_for_tokens(context, ("display_hash", "FinalDesignGuideDisplay", "title", "selected_title", "display")),
        "blocker_evidence_hash": _hash_for_tokens(context, ("exact_blockers_by_family", "blocker_reason", "candidate_search_evidence", "blocker")),
        "publication_hash": _hash_for_tokens(context, ("publication_hash", "_record_design_guide_publication_snapshot", "with_publication_hash")),
        "collapsed_guidance_items_replacement_hash": _hash_for_tokens(context, ("collapsed_guidance_items", "primary_item_for_evidence.update")),
        "surface_hash": _stable_hash(context),
    }


def _build_surfaces(input_source: str, publication_source: str) -> list[dict[str, Any]]:
    compute_line = _line_in_function(
        input_source,
        "final_compute_item = dict(final_compute_resolution.get(\"item\") or {})",
        "_resolve_compute_design_guidance_publication_handoff",
    )
    compute_context = _context(input_source, compute_line, radius=34)

    late_before_line = _line_in_function(
        input_source,
        "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "_apply_compute_late_evidence_contract_rebound",
    )
    late_context = _context(input_source, late_before_line, radius=34)

    post_core_line = _line_in_function(
        input_source,
        "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "_orchestrate_compute_post_core_publication_handoff",
    )
    post_core_context = _context(input_source, post_core_line, radius=34)

    render_line = _line_in_function(
        input_source,
        "_final_visible_item = _publish_final_visible_design_guide_contract_binding(",
        "_render_fast_design_guidance_panel",
    )
    render_context = _context(input_source, render_line, radius=34)

    collapsed_context = "\n".join(
        [
            compute_context,
            late_context,
            post_core_context,
        ]
    )

    publication_line = None
    for index, line in enumerate(publication_source.splitlines(), start=1):
        if "class FinalDesignGuidePublication" in line:
            publication_line = index
            break
    publication_context = _context(publication_source, publication_line, radius=150)

    return [
        _identity_surface(
            name="resolver_output_item",
            location=None if compute_line is None else f"inputs_page.py:{compute_line}",
            context=compute_context,
            source_kind="compute resolver output",
        ),
        _identity_surface(
            name="final_design_guide_publication_built_item",
            location=None if publication_line is None else f"design_brain/final_publication.py:{publication_line}",
            context=publication_context,
            source_kind="FinalDesignGuidePublication object",
        ),
        _identity_surface(
            name="collapsed_guidance_items_before_replacement",
            location=None if late_before_line is None else f"inputs_page.py:{late_before_line}",
            context=late_context,
            source_kind="late evidence primary item before replacement",
        ),
        _identity_surface(
            name="collapsed_guidance_items_after_replacement",
            location="inputs_page.py:collapsed_guidance_items replacement sites",
            context=collapsed_context,
            source_kind="collapsed guidance replacement aggregate",
        ),
        _identity_surface(
            name="render_stage_selected_item",
            location=None if render_line is None else f"inputs_page.py:{render_line}",
            context=render_context,
            source_kind="render resolver selected item",
        ),
    ]


def _missing_identity_fields(publication_surface: dict[str, Any]) -> list[str]:
    presence = dict(publication_surface.get("field_presence") or {})
    missing = []
    for field in ("published_item_id", "guidance_intent", "post_click_design_guide_state"):
        if not presence.get(field):
            missing.append(field)
    return missing


def _build_snapshot() -> dict[str, Any]:
    same_object = _run("tools/verification/design_guide_compute_render_same_object_proof.py")
    resolver_bridge = _run("tools/verification/design_guide_resolver_authority_bridge_snapshot.py")
    independence = _run("tools/verification/design_guide_independence_lock_verifier.py")
    same_object_artifact = _latest_artifact("design_guide_compute_render_same_object_proof")
    resolver_bridge_artifact = _latest_artifact("design_guide_resolver_authority_bridge_snapshot")

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    surfaces = _build_surfaces(input_source, publication_source)
    publication_surface = next(
        surface for surface in surfaces if surface["surface"] == "final_design_guide_publication_built_item"
    )
    missing_identity = _missing_identity_fields(publication_surface)
    smallest_missing_field = "published_item_id" if "published_item_id" in missing_identity else (missing_identity[0] if missing_identity else None)
    collapsed_after = next(surface for surface in surfaces if surface["surface"] == "collapsed_guidance_items_after_replacement")
    publication_can_drive_replacement = bool(
        not missing_identity
        and collapsed_after["collapsed_guidance_items_replacement_hash"] == publication_surface["surface_hash"]
    )
    status = "PASS" if publication_can_drive_replacement else "PARTIAL"

    failures: list[str] = []
    if not same_object["passed"]:
        failures.append("compute_render_same_object_proof_failed")
    if not resolver_bridge["passed"]:
        failures.append("resolver_authority_bridge_snapshot_failed")
    if not independence["passed"]:
        failures.append("design_guide_independence_lock_failed")
    for surface in surfaces:
        if surface["location"] is None:
            failures.append(f"missing_surface_location:{surface['surface']}")
    if failures:
        status = "FAIL"

    proof_surface = {
        "surfaces": surfaces,
        "missing_identity": missing_identity,
        "smallest_missing_field": smallest_missing_field,
        "publication_can_drive_replacement": publication_can_drive_replacement,
        "same_object_artifact": same_object_artifact.get("path"),
        "resolver_bridge_artifact": resolver_bridge_artifact.get("path"),
    }
    return {
        "snapshot_name": "design_guide_publication_identity_collapsed_replacement_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "expected_partial": True,
        "source_same_object_artifact": same_object_artifact.get("path"),
        "source_resolver_bridge_artifact": resolver_bridge_artifact.get("path"),
        "tracked_fields": list(TRACKED_FIELDS),
        "surfaces": surfaces,
        "summary": {
            "publication_can_drive_collapsed_replacement_now": publication_can_drive_replacement,
            "missing_identity_fields_on_final_publication": missing_identity,
            "one_missing_identity_field_to_add_first": smallest_missing_field,
            "next_recommended_slice": (
                "Add proof-only published_item_id to FinalDesignGuidePublication identity/evidence surface"
                if smallest_missing_field == "published_item_id"
                else "Add the missing identity field to FinalDesignGuidePublication before narrowing resolver bridges"
            ),
        },
        "verification": {
            "compute_render_same_object_proof": same_object,
            "resolver_authority_bridge_snapshot": resolver_bridge,
            "design_guide_independence_lock": independence,
        },
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = []
    for surface in snapshot["surfaces"]:
        presence = surface["field_presence"]
        rows.append(
            "| `{surface}` | `{location}` | `{published}` | `{source_id}` | `{family}` | `{outcome}` | `{intent}` | `{post_click}` | `{replacement}` |".format(
                surface=surface["surface"],
                location=surface["location"],
                published=presence["published_item_id"],
                source_id=presence["source_candidate_id"],
                family=presence["selected_family"],
                outcome=presence["outcome_state"],
                intent=presence["guidance_intent"],
                post_click=presence["post_click_design_guide_state"],
                replacement=presence["collapsed_guidance_items_replacement_hash"],
            )
        )
    hash_rows = [
        "| `{surface}` | `{cta}` | `{display}` | `{blocker}` | `{publication}` | `{replacement}` |".format(
            surface=surface["surface"],
            cta=surface["cta_hash"],
            display=surface["display_hash"],
            blocker=surface["blocker_evidence_hash"],
            publication=surface["publication_hash"],
            replacement=surface["collapsed_guidance_items_replacement_hash"],
        )
        for surface in snapshot["surfaces"]
    ]
    body = "\n".join(
        [
            "# Design Guide Publication Identity / Collapsed Replacement Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Publication can drive collapsed replacement now: `{snapshot['summary']['publication_can_drive_collapsed_replacement_now']}`",
            f"- Missing identity fields on FinalDesignGuidePublication: `{snapshot['summary']['missing_identity_fields_on_final_publication']}`",
            f"- One missing identity field to add first: `{snapshot['summary']['one_missing_identity_field_to_add_first']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Field Presence",
            "",
            "| Surface | Location | published_item_id | source_candidate_id | selected_family | outcome_state | guidance_intent | post_click_design_guide_state | collapsed replacement |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            "## Hash Surfaces",
            "",
            "| Surface | CTA Hash | Display Hash | Blocker Evidence Hash | Publication Hash | Collapsed Replacement Hash |",
            "|---|---|---|---|---|---|",
            *hash_rows,
            "",
            "## Verification",
            "",
            f"- Compute/render same-object proof passed: `{snapshot['verification']['compute_render_same_object_proof']['passed']}`",
            f"- Resolver authority bridge snapshot passed: `{snapshot['verification']['resolver_authority_bridge_snapshot']['passed']}`",
            f"- Design Guide independence lock passed: `{snapshot['verification']['design_guide_independence_lock']['passed']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
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
    json_path = ARTIFACT_DIR / f"design_guide_publication_identity_collapsed_replacement_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_identity_collapsed_replacement_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_publication_identity_collapsed_replacement_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
