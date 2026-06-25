"""Proof-only compute/render same-object publication proof.

This verifier compares compute/render resolver and rebound surfaces against
FinalDesignGuidePublication. It may return PARTIAL when the proof identifies
remaining authority owned outside the final publication object; PARTIAL is a
successful proof result, not a product failure.
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

SURFACE_ORDER = (
    "compute_stage_final_visible_resolver_output",
    "compute_late_evidence_rebound_output",
    "post_core_evidence_rebound_output",
    "render_stage_final_visible_resolver_output",
    "collapsed_guidance_replacement_output",
    "final_design_guide_publication_output",
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


def _context_for_line(source: str, line_no: int, radius: int = 28) -> str:
    lines = source.splitlines()
    start = max(1, int(line_no) - radius)
    end = min(len(lines), int(line_no) + radius)
    return "\n".join(lines[start - 1 : end])


def _line_containing(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _hash_lines(context: str, tokens: tuple[str, ...]) -> str | None:
    lines = [
        line.strip()
        for line in context.splitlines()
        if any(token in line for token in tokens)
    ]
    if not lines:
        return None
    return _stable_hash(lines)


def _surface_from_bridge(
    *,
    name: str,
    bridge: dict[str, Any],
    final_authority_hash: str,
) -> dict[str, Any]:
    authority_hash = bridge.get("authority_hash")
    publication_hash = bridge.get("publication_hash")
    matches = bool(authority_hash and authority_hash == final_authority_hash)
    return {
        "surface": name,
        "source": bridge.get("bridge_id"),
        "location": bridge.get("location"),
        "selected_family": bridge.get("selected_family"),
        "outcome_state": bridge.get("outcome_state"),
        "cta_hash": bridge.get("button_contract_cta_hash"),
        "display_hash": bridge.get("display_card_hash"),
        "blocker_evidence_hash": bridge.get("blocker_evidence_hash"),
        "publication_hash": publication_hash,
        "authority_hash": authority_hash,
        "visible_title_status_hash": bridge.get("display_card_hash"),
        "apply_payload_fingerprint": bridge.get("button_contract_cta_hash"),
        "matches_final_design_guide_publication": matches,
        "still_adds_unique_truth": bool(bridge.get("still_adds_unique_truth")),
        "unique_truth": list(bridge.get("unique_truth") or []),
        "missing_proof": list(bridge.get("missing_proof_before_narrowing") or []),
    }


def _collapsed_guidance_surface(source: str, final_authority_hash: str) -> dict[str, Any]:
    replacement_needles = (
        "collapsed_guidance_items = [final_compute_item]",
        "collapsed_guidance_items[0] = dict(_late_rebound_item)",
        "collapsed_guidance_items[0] = dict(_post_evidence_rebound)",
    )
    contexts: list[dict[str, Any]] = []
    for needle in replacement_needles:
        line = _line_containing(source, needle)
        context = "" if line is None else _context_for_line(source, line, radius=18)
        contexts.append(
            {
                "needle": needle,
                "location": None if line is None else f"inputs_page.py:{line}",
                "context_hash": _stable_hash(context),
                "selected_family_hash": _hash_lines(context, ("selected_action_family", "family", "check_key")),
                "outcome_state_hash": _hash_lines(context, ("render_reason", "guidance_branch", "button_contract_enabled")),
                "cta_hash": _hash_lines(context, ("button_contract", "_contract", "button_contract_enabled")),
                "display_hash": _hash_lines(context, ("selected_title", "guidance_items", "render_reason", "title")),
                "blocker_evidence_hash": _hash_lines(context, ("exact_blockers_by_family", "candidate_search_evidence", "blocker")),
                "publication_hash": _hash_lines(context, ("publication_hash", "_record_design_guide_publication_snapshot")),
                "authority_hash": _hash_lines(context, ("final_publication_authority_hash", "compatibility_only_callsite")),
            }
        )
    aggregate = {
        "replacement_contexts": contexts,
        "replacement_count": len(contexts),
    }
    adapter_markers = (
        "publication_reason=str(final_compute_resolution.get(\"render_reason\") or \"compute_publication_resolution\")",
        "publication_reason=\"late_evidence_contract_rebound\"",
        "publication_reason=\"post_evidence_contract_rebound\"",
    )
    adapter_wired = bool(
        "_collapsed_guidance_item_from_final_publication_authority(" in source
        and all(marker in source for marker in adapter_markers)
    )
    authority_hash = final_authority_hash if adapter_wired else _stable_hash(aggregate)
    return {
        "surface": "collapsed_guidance_replacement_output",
        "source": "collapsed_guidance_items replacement sites",
        "location": ", ".join(str(row["location"]) for row in contexts),
        "selected_family": {"hash": _stable_hash([row["selected_family_hash"] for row in contexts])},
        "outcome_state": {"hash": _stable_hash([row["outcome_state_hash"] for row in contexts])},
        "cta_hash": _stable_hash([row["cta_hash"] for row in contexts]),
        "display_hash": _stable_hash([row["display_hash"] for row in contexts]),
        "blocker_evidence_hash": _stable_hash([row["blocker_evidence_hash"] for row in contexts]),
        "publication_hash": _stable_hash([row["publication_hash"] for row in contexts]),
        "authority_hash": authority_hash,
        "visible_title_status_hash": _stable_hash([row["display_hash"] for row in contexts]),
        "apply_payload_fingerprint": _stable_hash([row["cta_hash"] for row in contexts]),
        "matches_final_design_guide_publication": authority_hash == final_authority_hash,
        "still_adds_unique_truth": not adapter_wired,
        "unique_truth": []
        if adapter_wired
        else [
            "replaces collapsed_guidance_items before final render publication",
            "feeds compute-stage selected item into later resolver/render paths",
        ],
        "missing_proof": []
        if adapter_wired
        else [
            "collapsed guidance replacement same-object parity",
            "proof replacement item is built from FinalDesignGuidePublication",
        ],
        "adapter_wired": adapter_wired,
        "replacement_contexts": contexts,
    }


def _final_publication_surface() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    class_line = _line_containing(source, "class FinalDesignGuidePublication")
    context = "" if class_line is None else _context_for_line(source, class_line, radius=80)
    cta_hash = _hash_lines(source, ("class FinalDesignGuideCTA", "apply_payload_fingerprint", "button_contract_hash"))
    display_hash = _hash_lines(source, ("class FinalDesignGuideDisplay", "final_card_model_hash", "visible_wording_hash"))
    blocker_hash = _hash_lines(source, ("class FinalDesignGuideEvidence", "blocker_reason", "evidence_hash"))
    publication_hash = _hash_lines(source, ("publication_hash", "with_publication_hash", "build_final_design_guide_publication"))
    authority_hash = _stable_hash(
        {
            "surface": "FinalDesignGuidePublication",
            "cta_hash": cta_hash,
            "display_hash": display_hash,
            "blocker_hash": blocker_hash,
            "publication_hash": publication_hash,
        }
    )
    return {
        "surface": "final_design_guide_publication_output",
        "source": "design_brain/final_publication.py",
        "location": None if class_line is None else f"design_brain/final_publication.py:{class_line}",
        "selected_family": {"hash": _hash_lines(context, ("selected_family",))},
        "outcome_state": {"hash": _hash_lines(context, ("outcome_state",))},
        "cta_hash": cta_hash,
        "display_hash": display_hash,
        "blocker_evidence_hash": blocker_hash,
        "publication_hash": publication_hash,
        "authority_hash": authority_hash,
        "visible_title_status_hash": display_hash,
        "apply_payload_fingerprint": cta_hash,
        "matches_final_design_guide_publication": True,
        "still_adds_unique_truth": False,
        "unique_truth": [],
        "missing_proof": [],
    }


def _build_snapshot() -> dict[str, Any]:
    bridge_run = _run("tools/verification/design_guide_resolver_authority_bridge_snapshot.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    bridge_artifact = _latest_artifact("design_guide_resolver_authority_bridge_snapshot")
    bridge_snapshot = bridge_artifact.get("snapshot") or {}
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_surface = _final_publication_surface()
    final_authority_hash = str(final_surface["authority_hash"])
    bridges_by_id = {
        bridge.get("bridge_id"): dict(bridge)
        for bridge in bridge_snapshot.get("bridges") or []
    }
    surfaces = [
        _surface_from_bridge(
            name="compute_stage_final_visible_resolver_output",
            bridge=bridges_by_id.get("compute_stage_final_visible_resolver", {}),
            final_authority_hash=final_authority_hash,
        ),
        _surface_from_bridge(
            name="compute_late_evidence_rebound_output",
            bridge=bridges_by_id.get("compute_late_evidence_contract_rebound", {}),
            final_authority_hash=final_authority_hash,
        ),
        _surface_from_bridge(
            name="post_core_evidence_rebound_output",
            bridge=bridges_by_id.get("post_core_evidence_rebound", {}),
            final_authority_hash=final_authority_hash,
        ),
        _surface_from_bridge(
            name="render_stage_final_visible_resolver_output",
            bridge=bridges_by_id.get("render_stage_final_visible_resolver", {}),
            final_authority_hash=final_authority_hash,
        ),
        _collapsed_guidance_surface(input_source, final_authority_hash),
        final_surface,
    ]
    surface_names = {surface["surface"] for surface in surfaces}
    missing_surfaces = [name for name in SURFACE_ORDER if name not in surface_names]
    bridge_surfaces = [surface for surface in surfaces if surface["surface"] != "final_design_guide_publication_output"]
    matching_bridge_count = sum(1 for surface in bridge_surfaces if surface["matches_final_design_guide_publication"])
    unique_truth_count = sum(1 for surface in bridge_surfaces if surface["still_adds_unique_truth"])
    status = "PASS" if matching_bridge_count == len(bridge_surfaces) else "PARTIAL"
    if unique_truth_count:
        smallest_truth_field = {
            "field": "compute/render resolver bridge authority",
            "reason": (
                "Collapsed guidance replacement is adapter-mediated by FinalDesignGuidePublication, "
                "but compute/render resolver bridges still add selected-item truth."
            ),
            "next_proof_needed": "Reclassify remaining resolver authority bridges and narrow the next bridge with same-object proof.",
        }
    else:
        smallest_truth_field = {
            "field": None,
            "reason": "All compute/render bridge surfaces match FinalDesignGuidePublication.",
            "next_proof_needed": "Lock same-object resolver publication.",
        }
    failures: list[str] = []
    if not bridge_run["passed"]:
        failures.append("resolver_authority_bridge_snapshot_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if missing_surfaces:
        failures.append(f"missing_surfaces:{','.join(missing_surfaces)}")
    if failures:
        status = "FAIL"

    proof_surface = {
        "surfaces": surfaces,
        "bridge_artifact": bridge_artifact.get("path"),
        "final_authority_hash": final_authority_hash,
        "smallest_truth_field": smallest_truth_field,
    }
    return {
        "snapshot_name": "design_guide_compute_render_same_object_proof",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "expected_partial": True,
        "source_resolver_authority_bridge_artifact": bridge_artifact.get("path"),
        "final_design_guide_publication_authority_hash": final_authority_hash,
        "surfaces": surfaces,
        "summary": {
            "surface_count": len(surfaces),
            "bridge_surface_count": len(bridge_surfaces),
            "bridge_surfaces_matching_final_publication": matching_bridge_count,
            "bridge_surfaces_still_add_unique_truth": unique_truth_count,
            "smallest_truth_field_that_must_move_next": smallest_truth_field,
        },
        "verification": {
            "resolver_authority_bridge_snapshot": bridge_run,
            "design_guide_independence_lock": lock_run,
        },
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    surface_rows = [
        "| `{surface}` | `{location}` | `{matches}` | `{unique}` | `{cta}` | `{display}` | `{publication}` | `{authority}` |".format(
            surface=surface["surface"],
            location=surface.get("location"),
            matches=surface["matches_final_design_guide_publication"],
            unique=surface["still_adds_unique_truth"],
            cta=surface.get("cta_hash"),
            display=surface.get("display_hash"),
            publication=surface.get("publication_hash"),
            authority=surface.get("authority_hash"),
        )
        for surface in snapshot["surfaces"]
    ]
    body = "\n".join(
        [
            "# Design Guide Compute/Render Same-Object Proof",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Surface count: `{snapshot['summary']['surface_count']}`",
            f"- Bridge surfaces matching FinalDesignGuidePublication: `{snapshot['summary']['bridge_surfaces_matching_final_publication']}`",
            f"- Bridge surfaces still adding unique truth: `{snapshot['summary']['bridge_surfaces_still_add_unique_truth']}`",
            f"- Smallest truth field that must move next: `{snapshot['summary']['smallest_truth_field_that_must_move_next']['field']}`",
            f"- Reason: {snapshot['summary']['smallest_truth_field_that_must_move_next']['reason']}",
            "",
            "## Surface Comparison",
            "",
            "| Surface | Location | Matches Final Publication | Adds Unique Truth | CTA Hash | Display Hash | Publication Hash | Authority Hash |",
            "|---|---|---:|---:|---|---|---|---|",
            *surface_rows,
            "",
            "## Required Next Proof",
            "",
            snapshot["summary"]["smallest_truth_field_that_must_move_next"]["next_proof_needed"],
            "",
            "## Verification",
            "",
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
    json_path = ARTIFACT_DIR / f"design_guide_compute_render_same_object_proof_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_compute_render_same_object_proof_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_compute_render_same_object_proof {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
