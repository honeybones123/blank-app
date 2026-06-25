"""Classify remaining resolver authority bridges after collapsed replacement cutover.

This verifier is proof-only. It consumes the current collapsed replacement
cutover, compute/render same-object proof, resolver bridge snapshot, and
independence lock, then classifies the four remaining resolver bridges as:

A. can narrow to compatibility stamp
B. fallback-required / keep
C. still real live authority / keep for now
D. deletion candidate
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

CLASS_A = "A. can narrow to compatibility stamp"
CLASS_B = "B. fallback-required / keep"
CLASS_C = "C. still real live authority / keep for now"
CLASS_D = "D. deletion candidate"

EXPECTED_RESOLVER_BRIDGES = (
    "compute_stage_final_visible_resolver",
    "compute_late_evidence_contract_rebound",
    "post_core_evidence_rebound",
    "render_stage_final_visible_resolver",
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
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _same_object_surface_by_bridge(same_object_snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapping = {
        "compute_stage_final_visible_resolver_output": "compute_stage_final_visible_resolver",
        "compute_late_evidence_rebound_output": "compute_late_evidence_contract_rebound",
        "post_core_evidence_rebound_output": "post_core_evidence_rebound",
        "render_stage_final_visible_resolver_output": "render_stage_final_visible_resolver",
    }
    out: dict[str, dict[str, Any]] = {}
    for surface in same_object_snapshot.get("surfaces") or []:
        bridge_id = mapping.get(str(surface.get("surface") or ""))
        if bridge_id:
            out[bridge_id] = dict(surface)
    return out


def _classify_bridge(
    bridge: dict[str, Any],
    same_surface: dict[str, Any],
    *,
    collapsed_cutover_pass: bool,
    collapsed_replacement_consumes_publication: bool,
) -> dict[str, Any]:
    bridge_id = str(bridge.get("bridge_id") or "")
    matches_publication = bool(
        bridge.get("matches_final_design_guide_publication")
        or same_surface.get("matches_final_design_guide_publication")
    )
    still_adds_unique_truth = bool(
        bridge.get("still_adds_unique_truth")
        or same_surface.get("still_adds_unique_truth")
    )
    missing_proof = list(
        same_surface.get("missing_proof")
        or bridge.get("missing_proof_before_narrowing")
        or []
    )
    unique_truth = list(same_surface.get("unique_truth") or bridge.get("unique_truth") or [])

    if matches_publication and not still_adds_unique_truth:
        classification = CLASS_A
        can_narrow = True
        deletion_candidate = False
        reason = "Bridge already matches FinalDesignGuidePublication and adds no unique truth."
        required_next_proof = "Narrow this bridge to a compatibility-only stamp."
    elif (
        bridge_id == "render_stage_final_visible_resolver"
        and collapsed_cutover_pass
        and collapsed_replacement_consumes_publication
        and "render resolver same-object proof against FinalDesignGuidePublication" in missing_proof
    ):
        classification = CLASS_C
        can_narrow = False
        deletion_candidate = False
        reason = (
            "Collapsed replacement is publication-driven, but render-stage final visible "
            "resolver still chooses the final render item and needs a dedicated same-object proof."
        )
        required_next_proof = "Render-stage resolver same-object proof."
    elif bridge_id in {
        "compute_stage_final_visible_resolver",
        "compute_late_evidence_contract_rebound",
        "post_core_evidence_rebound",
    }:
        classification = CLASS_C
        can_narrow = False
        deletion_candidate = False
        reason = (
            "Collapsed replacement no longer adds independent truth, but this bridge still "
            "owns resolver/rebound decision truth before publication compatibility can be stamped."
        )
        required_next_proof = "Bridge-specific same-object proof against FinalDesignGuidePublication."
    else:
        classification = CLASS_B
        can_narrow = False
        deletion_candidate = False
        reason = "Bridge role is not proven redundant; keep until a narrower proof exists."
        required_next_proof = "Fallback/compatibility proof before narrowing."

    return {
        "bridge_id": bridge_id,
        "location": bridge.get("location"),
        "function": bridge.get("function"),
        "symbol": bridge.get("symbol"),
        "classification": classification,
        "can_narrow_to_compatibility_stamp": can_narrow,
        "deletion_candidate": deletion_candidate,
        "matches_final_design_guide_publication": matches_publication,
        "still_adds_unique_truth": still_adds_unique_truth,
        "decision_truth_owned": bridge.get("decision_truth_owned"),
        "unique_truth": unique_truth,
        "missing_proof_before_narrowing": missing_proof,
        "reason": reason,
        "required_next_proof": required_next_proof,
        "recommended_future_owner": bridge.get("recommended_future_owner"),
    }


def _build_snapshot() -> dict[str, Any]:
    cutover_run = _run("tools/verification/design_guide_collapsed_replacement_authority_cutover.py")
    same_object_run = _run("tools/verification/design_guide_compute_render_same_object_proof.py")
    bridge_run = _run("tools/verification/design_guide_resolver_authority_bridge_snapshot.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")

    cutover_artifact = _latest_artifact("design_guide_collapsed_replacement_authority_cutover")
    same_object_artifact = _latest_artifact("design_guide_compute_render_same_object_proof")
    bridge_artifact = _latest_artifact("design_guide_resolver_authority_bridge_snapshot")
    lock_artifact = _latest_artifact("design_guide_independence_lock")

    cutover_snapshot = cutover_artifact.get("snapshot") or {}
    same_object_snapshot = same_object_artifact.get("snapshot") or {}
    bridge_snapshot = bridge_artifact.get("snapshot") or {}
    same_surfaces = _same_object_surface_by_bridge(same_object_snapshot)
    collapsed_surface = next(
        (
            dict(surface)
            for surface in same_object_snapshot.get("surfaces") or []
            if surface.get("surface") == "collapsed_guidance_replacement_output"
        ),
        {},
    )
    collapsed_cutover_pass = cutover_snapshot.get("status") == "PASS"
    collapsed_replacement_consumes_publication = bool(
        collapsed_surface.get("matches_final_design_guide_publication")
        and not collapsed_surface.get("still_adds_unique_truth")
    )
    bridge_rows = {
        str(bridge.get("bridge_id")): dict(bridge)
        for bridge in bridge_snapshot.get("bridges") or []
    }
    classifications = [
        _classify_bridge(
            bridge_rows.get(bridge_id, {"bridge_id": bridge_id}),
            same_surfaces.get(bridge_id, {}),
            collapsed_cutover_pass=collapsed_cutover_pass,
            collapsed_replacement_consumes_publication=collapsed_replacement_consumes_publication,
        )
        for bridge_id in EXPECTED_RESOLVER_BRIDGES
    ]
    class_counts = {
        CLASS_A: sum(1 for row in classifications if row["classification"] == CLASS_A),
        CLASS_B: sum(1 for row in classifications if row["classification"] == CLASS_B),
        CLASS_C: sum(1 for row in classifications if row["classification"] == CLASS_C),
        CLASS_D: sum(1 for row in classifications if row["classification"] == CLASS_D),
    }
    failures: list[str] = []
    if not cutover_run["passed"]:
        failures.append("collapsed_replacement_authority_cutover_failed")
    if not same_object_run["passed"]:
        failures.append("compute_render_same_object_proof_failed")
    if not bridge_run["passed"]:
        failures.append("resolver_authority_bridge_snapshot_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")
    missing = [bridge_id for bridge_id in EXPECTED_RESOLVER_BRIDGES if bridge_id not in bridge_rows]
    if missing:
        failures.append(f"missing_expected_bridges:{','.join(missing)}")
    if not collapsed_cutover_pass:
        failures.append("collapsed_cutover_not_pass")
    if not collapsed_replacement_consumes_publication:
        failures.append("collapsed_replacement_not_publication_driven")
    if class_counts[CLASS_D] > 0:
        failures.append("unexpected_deletion_candidate")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "classifications": classifications,
        "class_counts": class_counts,
        "collapsed_cutover_pass": collapsed_cutover_pass,
        "collapsed_replacement_consumes_publication": collapsed_replacement_consumes_publication,
        "source_artifacts": {
            "cutover": cutover_artifact.get("path"),
            "same_object": same_object_artifact.get("path"),
            "resolver_bridge": bridge_artifact.get("path"),
            "independence_lock": lock_artifact.get("path"),
        },
    }
    next_slice = (
        "Narrow exactly one class A bridge."
        if class_counts[CLASS_A]
        else (
            "Delete exactly one class D bridge."
            if class_counts[CLASS_D]
            else "No bridge is narrowable yet; add a bridge-specific same-object proof."
        )
    )
    return {
        "snapshot_name": "design_guide_remaining_resolver_bridge_classification",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "collapsed_cutover_pass": collapsed_cutover_pass,
        "collapsed_replacement_consumes_publication": collapsed_replacement_consumes_publication,
        "classifications": classifications,
        "class_counts": class_counts,
        "summary": {
            "can_narrow_to_compatibility_stamp": class_counts[CLASS_A],
            "fallback_required_keep": class_counts[CLASS_B],
            "still_real_live_authority_keep_for_now": class_counts[CLASS_C],
            "deletion_candidates": class_counts[CLASS_D],
            "next_recommended_slice": next_slice,
        },
        "source_artifacts": proof_surface["source_artifacts"],
        "verification": {
            "collapsed_replacement_authority_cutover": cutover_run,
            "compute_render_same_object_proof": same_object_run,
            "resolver_authority_bridge_snapshot": bridge_run,
            "design_guide_independence_lock": lock_run,
        },
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = [
        "| `{bridge}` | `{classification}` | `{narrow}` | `{delete}` | `{matches}` | `{unique}` | `{reason}` |".format(
            bridge=row["bridge_id"],
            classification=row["classification"],
            narrow=row["can_narrow_to_compatibility_stamp"],
            delete=row["deletion_candidate"],
            matches=row["matches_final_design_guide_publication"],
            unique=row["still_adds_unique_truth"],
            reason=row["reason"],
        )
        for row in snapshot["classifications"]
    ]
    body = "\n".join(
        [
            "# Design Guide Remaining Resolver Bridge Classification",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Collapsed replacement cutover PASS: `{snapshot['collapsed_cutover_pass']}`",
            f"- Collapsed replacement consumes publication: `{snapshot['collapsed_replacement_consumes_publication']}`",
            f"- A can narrow: `{snapshot['summary']['can_narrow_to_compatibility_stamp']}`",
            f"- B fallback-required / keep: `{snapshot['summary']['fallback_required_keep']}`",
            f"- C still real live authority / keep for now: `{snapshot['summary']['still_real_live_authority_keep_for_now']}`",
            f"- D deletion candidates: `{snapshot['summary']['deletion_candidates']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Bridge Classification",
            "",
            "| Bridge | Classification | Can Narrow | Delete | Matches Publication | Adds Unique Truth | Reason |",
            "|---|---|---:|---:|---:|---:|---|",
            *rows,
            "",
            "## Source Artifacts",
            "",
            f"- Collapsed replacement cutover: `{snapshot['source_artifacts']['cutover']}`",
            f"- Compute/render same-object proof: `{snapshot['source_artifacts']['same_object']}`",
            f"- Resolver authority bridge snapshot: `{snapshot['source_artifacts']['resolver_bridge']}`",
            f"- Independence lock: `{snapshot['source_artifacts']['independence_lock']}`",
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
    json_path = ARTIFACT_DIR / f"design_guide_remaining_resolver_bridge_classification_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_resolver_bridge_classification_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_remaining_resolver_bridge_classification {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
