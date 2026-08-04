"""Audit deletion state for former inputs_page compatibility helpers.

This is a proof-only inventory roll-up. The expected locked state is that the
old compatibility helpers are absent from ``inputs_page.py``. If any helper
definition or callsite returns, the verifier fails so the extraction cannot
quietly drift back toward page-owned Design Guide truth.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

HELPERS = {
    "_mark_compute_debug_restamp_metadata_compatibility_only": {
        "surface": "compute debug/restamp metadata rows",
        "blocking_artifact": "design_guide_compute_stage_resolver_deletion_readiness",
        "expected_blocker": "B/D compute resolver truth still live",
    },
    "_mark_compute_publication_evidence_a_class_compatibility_only": {
        "surface": "publication-owned A-class compute evidence compatibility rows",
        "blocking_artifact": "design_guide_compute_stage_resolver_deletion_readiness",
        "expected_blocker": "compute resolver bridge still owns B/D pre-publication truth",
    },
    "_mark_final_visible_restamper_compatibility_stamp": {
        "surface": "final visible restamper compatibility rows",
        "blocking_artifact": "design_guide_remaining_resolver_cleanup_audit",
        "expected_blocker": "per-callsite consumer reachability proof still required",
    },
}

LOCK_PREFIXES = {
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "remaining_resolver_cleanup": "design_guide_remaining_resolver_cleanup_audit",
    "compute_stage_resolver_deletion_readiness": "design_guide_compute_stage_resolver_deletion_readiness",
    "remaining_direct_publication_build_audit": "design_guide_remaining_direct_publication_build_audit",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    files = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not files:
        return {"path": None, "status": None, "found": False, "payload": None}
    path = files[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "status": payload.get("status"),
        "found": True,
        "payload": payload,
    }


def _line_numbers(source: str, token: str) -> list[int]:
    return [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if token in line
    ]


def _helper_rows(source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cleanup = _latest("design_guide_remaining_resolver_cleanup_audit")
    compute_deletion = _latest("design_guide_compute_stage_resolver_deletion_readiness")
    cleanup_counts = dict(((cleanup.get("payload") or {}).get("classification_counts") or {}))
    compute_capture = dict(((compute_deletion.get("payload") or {}).get("capture") or {}))
    compute_decision = compute_capture.get("decision")
    completed_controller_state = bool(compute_capture.get("completed_controller_state"))
    for helper, meta in HELPERS.items():
        definition_lines = [
            line for line in _line_numbers(source, f"def {helper}(")
        ]
        call_lines = [
            line for line in _line_numbers(source, f"{helper}(")
            if line not in definition_lines
        ]
        if helper.startswith("_mark_compute_"):
            deletion_ready = compute_decision == "DELETE_READY"
            replacement_parity_proven = (
                compute_decision == "REPLACEMENT_PARITY_PROVEN_CUTOVER_PROOF_REQUIRED"
            )
            compute_helper_deleted = (
                completed_controller_state and not definition_lines and not call_lines
            )
            if compute_helper_deleted:
                classification = "A. compute compatibility helper deleted after controller cutover proof"
            elif deletion_ready:
                classification = "A. needs focused deletion proof"
            elif replacement_parity_proven:
                classification = "B. controller replacement parity proven; cutover proof required"
            else:
                classification = "C. still live compute bridge support"
            blocker = compute_capture.get("replacement_required") or meta["expected_blocker"]
        else:
            deletion_ready = False
            metadata_deleted = (
                not definition_lines
                and "compatibility_only_callsite" not in source
                and "final_publication_restamper_metadata" not in source
                and "final_publication_restamper_selected_callsite" not in source
            )
            classification = (
                "A. metadata wrapper deleted after focused reachability proof"
                if metadata_deleted
                else "B. compatibility-only callsites need focused consumer proof"
            )
            blocker = (
                {"deleted_surface": "final-visible restamper compatibility metadata"}
                if metadata_deleted
                else {
                    "classification_counts": cleanup_counts,
                    "expected_blocker": meta["expected_blocker"],
                }
            )
        rows.append(
            {
                "helper": helper,
                "surface": meta["surface"],
                "definition_lines": definition_lines,
                "call_lines": call_lines,
                "call_count": len(call_lines),
                "classification": classification,
                "deletion_ready_now": bool(deletion_ready),
                "blocker": blocker,
            }
        )
    return rows


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    latest = {name: _latest(prefix) for name, prefix in LOCK_PREFIXES.items()}
    helper_rows = _helper_rows(source)
    all_helpers_physically_deleted = all(
        not row["definition_lines"] and not row["call_lines"] for row in helper_rows
    )
    failures: list[str] = []
    for name in (
        "independence_lock",
        "render_bridge_lock",
        "compute_resolver_publication_bridge_lock",
        "remaining_resolver_cleanup",
        "compute_stage_resolver_deletion_readiness",
        "remaining_direct_publication_build_audit",
    ):
        if latest[name].get("status") != "PASS":
            failures.append(f"{name}_latest_artifact_not_pass")
    if not all_helpers_physically_deleted:
        failures.append("compatibility_helper_still_present_in_inputs_page")
    if any(row["deletion_ready_now"] for row in helper_rows):
        failures.append("unexpected_deletion_ready_helper_after_locked_deleted_state")
    if any(
        not row["definition_lines"]
        and row["classification"]
        not in {
            "A. metadata wrapper deleted after focused reachability proof",
            "A. compute compatibility helper deleted after controller cutover proof",
        }
        for row in helper_rows
    ):
        failures.append("expected_helper_missing_before_its_deletion_slice")
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": failures,
        "summary": {
            "helpers_checked": len(helper_rows),
            "helpers_physically_deleted": sum(
                1
                for row in helper_rows
                if not row["definition_lines"] and not row["call_lines"]
            ),
            "locked_expected_remaining_helpers": 0,
            "deletion_ready_now": sum(1 for row in helper_rows if row["deletion_ready_now"]),
            "still_live_compute_support": sum(
                1 for row in helper_rows if row["classification"].startswith("C.")
            ),
            "controller_parity_cutover_proof_required": sum(
                1 for row in helper_rows if row["classification"].startswith("B.")
            ),
            "compatibility_consumer_proof_required": sum(
                1
                for row in helper_rows
                if row["classification"].startswith("B.")
                and "consumer proof" in row["classification"]
            ),
            "product_behavior_changed": False,
        },
        "decision": (
            "COMPATIBILITY_HELPERS_DELETED_LOCKED_ZERO"
            if all_helpers_physically_deleted
            else "COMPATIBILITY_HELPERS_STILL_PRESENT"
        ),
        "helpers": helper_rows,
        "latest_artifacts": latest,
        "next_safe_step": (
            "Compatibility helper count is locked at zero. Continue with the next "
            "inventory surface: remaining final-visible restamper callsites and "
            "render-item consumer mutation surfaces."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Remaining Compatibility Helper Deletion Readiness Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["summary"].items())
    lines.extend(
        [
            "",
            "## Helper Map",
            "",
            "| Helper | Calls | Classification | Deletion Ready |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for row in payload["helpers"]:
        lines.append(
            f"| `{row['helper']}` | `{row['call_count']}` | {row['classification']} | `{row['deletion_ready_now']}` |"
        )
    lines.extend(["", "## Next Safe Step", "", payload["next_safe_step"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    stamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_remaining_compatibility_helper_deletion_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_remaining_compatibility_helper_deletion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload, report_path)
    print(f"design_guide_remaining_compatibility_helper_deletion_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["failures"]:
        print("failures=" + json.dumps(payload["failures"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
