"""Classify remaining live Design Guide restamper mutations.

This proof-only verifier consumes the duplicate restamper reachability snapshot
and classifies the remaining live mutation callsites as:

A. can narrow to compatibility stamp
B. fallback-required / keep
C. still real live authority / keep for now
D. deletion candidate

It does not change product behaviour or delete code.
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


CLASS_CAN_NARROW = "A. can narrow to compatibility stamp"
CLASS_FALLBACK_KEEP = "B. fallback-required / keep"
CLASS_LIVE_AUTHORITY_KEEP = "C. still real live authority / keep for now"
CLASS_DELETION_CANDIDATE = "D. deletion candidate"
EXPECTED_REMAINING_LIVE_MUTATIONS = 4


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


def _classify_remaining_callsite(row: dict[str, Any]) -> dict[str, Any]:
    line = int(row.get("line") or 0)
    target = str(row.get("target") or "")
    function = str(row.get("function") or "")
    context = str(row.get("context_excerpt") or "")

    if row.get("classification") == "fallback shell support":
        classification = CLASS_FALLBACK_KEEP
        rationale = "Reachability already identifies this as fallback shell support; excluded from narrowing/deletion."
        next_action = "Keep fallback shell path until a dedicated fallback deletion proof exists."
        deletion_safe = False
        can_narrow = False
    elif target == "resolve_final_visible_design_guide_item":
        classification = CLASS_LIVE_AUTHORITY_KEEP
        rationale = (
            "Resolver call chooses the visible publication item before downstream binding; "
            "this is still selection/publication authority rather than duplicate stamping."
        )
        next_action = "Keep for now; audit resolver ownership before any narrowing or deletion."
        deletion_safe = False
        can_narrow = False
    elif function in {
        "_apply_compute_late_evidence_contract_rebound",
        "_orchestrate_compute_post_core_publication_handoff",
    }:
        classification = CLASS_LIVE_AUTHORITY_KEEP
        rationale = (
            "Compute-stage rebound can replace collapsed guidance items before final render publication; "
            "FinalDesignGuidePublication is not yet the only downstream truth at this point."
        )
        next_action = "Keep for now; add a compute-stage publication handoff proof before narrowing."
        deletion_safe = False
        can_narrow = False
    elif (
        function == "_render_fast_design_guidance_panel"
        and "_post_click_low_bending_resolution_item" in context
        and "_primary_render_items[0]" in context
        and "_primary_bending_resolution" in context
    ):
        classification = CLASS_CAN_NARROW
        rationale = (
            "Direct post-click exact-blocker binding mirrors the already-narrowed final exact-blocker path; "
            "CTA/display truth is owned by FinalDesignGuidePublication and this can be converted to a compatibility stamp in a future single-callsite slice."
        )
        next_action = (
            "Narrow with compatibility_only_callsite='post_click_low_bending_exact_blocker_primary_render_binding'."
        )
        deletion_safe = False
        can_narrow = True
    else:
        classification = CLASS_LIVE_AUTHORITY_KEEP
        rationale = (
            "Live mutation remains connected to visible item/debug state and is not proven duplicate-only."
        )
        next_action = "Keep until a focused proof isolates duplicate-only behavior."
        deletion_safe = False
        can_narrow = False

    return {
        "file": row.get("file"),
        "line": line,
        "function": function,
        "target": target,
        "source_line": row.get("source_line"),
        "reachability_classification": row.get("classification"),
        "remaining_mutation_classification": classification,
        "can_narrow_to_compatibility_stamp": bool(can_narrow),
        "fallback_required_keep": classification == CLASS_FALLBACK_KEEP,
        "still_real_live_authority_keep": classification == CLASS_LIVE_AUTHORITY_KEEP,
        "deletion_candidate": bool(deletion_safe),
        "rationale": rationale,
        "recommended_next_action": next_action,
        "context_hash": row.get("context_hash"),
    }


def _build_snapshot() -> dict[str, Any]:
    reachability = _run("tools/verification/design_guide_duplicate_restamper_reachability_snapshot.py")
    narrowing = _run("tools/verification/design_guide_restamper_mutation_narrowing_snapshot.py")
    independence = _run("tools/verification/design_guide_independence_lock_verifier.py")
    reachability_artifact = _latest_artifact("design_guide_duplicate_restamper_reachability")
    reachability_snapshot = reachability_artifact.get("snapshot") or {}
    live_mutations = [
        dict(row)
        for row in reachability_snapshot.get("callsites") or []
        if row.get("classification") == "still live mutation"
    ]
    classified = [_classify_remaining_callsite(row) for row in live_mutations]
    counts: dict[str, int] = {}
    for row in classified:
        key = str(row["remaining_mutation_classification"])
        counts[key] = counts.get(key, 0) + 1
    deletion_candidates = [row for row in classified if row["deletion_candidate"]]
    can_narrow = [row for row in classified if row["can_narrow_to_compatibility_stamp"]]

    failures: list[str] = []
    if not reachability["passed"]:
        failures.append("duplicate_restamper_reachability_failed")
    if not narrowing["passed"]:
        failures.append("restamper_mutation_narrowing_failed")
    if not independence["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if len(live_mutations) != EXPECTED_REMAINING_LIVE_MUTATIONS:
        failures.append(
            f"expected_{EXPECTED_REMAINING_LIVE_MUTATIONS}_live_mutations_found_{len(live_mutations)}"
        )

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "reachability_artifact": reachability_artifact.get("path"),
        "live_mutation_count": len(live_mutations),
        "classification_counts": counts,
        "classified_callsites": classified,
        "reachability_passed": reachability["passed"],
        "narrowing_passed": narrowing["passed"],
        "independence_passed": independence["passed"],
    }
    return {
        "snapshot_name": "design_guide_remaining_restamper_mutation_classification",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "source_reachability_artifact": reachability_artifact.get("path"),
        "remaining_live_mutation_count": len(live_mutations),
        "expected_remaining_live_mutation_count": EXPECTED_REMAINING_LIVE_MUTATIONS,
        "remaining_mutation_classification_counts": counts,
        "classified_callsites": classified,
        "deletion_candidates": deletion_candidates,
        "can_narrow_candidates": can_narrow,
        "next_recommended_slice": (
            "delete one D candidate"
            if deletion_candidates
            else (
                "continue narrowing the first A candidate"
                if can_narrow
                else "keep remaining live authority callsites and audit resolver/compute handoff"
            )
        ),
        "product_behavior_changed": False,
        "cta_display_apply_render_wording_changed": False,
        "verification": {
            "duplicate_restamper_reachability": reachability,
            "restamper_mutation_narrowing": narrowing,
            "design_guide_independence_lock": independence,
        },
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    count_rows = [
        f"| {name} | `{count}` |"
        for name, count in sorted(snapshot["remaining_mutation_classification_counts"].items())
    ]
    call_rows = [
        "| `{file}:{line}` | `{function}` | `{target}` | `{classification}` | `{narrow}` | `{delete}` | {rationale} | {next_action} |".format(
            file=row["file"],
            line=row["line"],
            function=row["function"],
            target=row["target"],
            classification=row["remaining_mutation_classification"],
            narrow=row["can_narrow_to_compatibility_stamp"],
            delete=row["deletion_candidate"],
            rationale=row["rationale"],
            next_action=row["recommended_next_action"],
        )
        for row in snapshot["classified_callsites"]
    ]
    body = "\n".join(
        [
            "# Design Guide Remaining Restamper Mutation Classification",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            f"Source reachability artifact: `{snapshot['source_reachability_artifact']}`",
            f"Remaining live mutation count: `{snapshot['remaining_live_mutation_count']}`",
            "",
            "## Classification Counts",
            "",
            "| Classification | Count |",
            "|---|---:|",
            *count_rows,
            "",
            "## Remaining Live Mutations",
            "",
            "| Location | Function | Restamper | Classification | Can Narrow | Deletion Candidate | Rationale | Recommended Next Action |",
            "|---|---|---|---|---:|---:|---|---|",
            *call_rows,
            "",
            "## Deletion Candidates",
            "",
            (
                "None. No code deletion was performed."
                if not snapshot["deletion_candidates"]
                else "\n".join(
                    f"- `{row['file']}:{row['line']}` {row['recommended_next_action']}"
                    for row in snapshot["deletion_candidates"]
                )
            ),
            "",
            "## Next Recommended Slice",
            "",
            snapshot["next_recommended_slice"],
            "",
            "## Verification",
            "",
            f"- Duplicate restamper reachability passed: `{snapshot['verification']['duplicate_restamper_reachability']['passed']}`",
            f"- Restamper mutation narrowing passed: `{snapshot['verification']['restamper_mutation_narrowing']['passed']}`",
            f"- Design Guide independence lock passed: `{snapshot['verification']['design_guide_independence_lock']['passed']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- CTA/display/apply/render/wording changed: `False`",
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
    json_path = ARTIFACT_DIR / f"design_guide_remaining_restamper_mutation_classification_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_restamper_mutation_classification_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_remaining_restamper_mutation_classification {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
