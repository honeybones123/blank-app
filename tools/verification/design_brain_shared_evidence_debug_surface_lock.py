from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

FOCUSED_PREFIXES: tuple[str, ...] = (
    "design_brain_inputs_page_zero_authority_inventory_lock",
    "design_guide_verifier_debug_same_object",
    "design_guide_compute_invalid_state_debug_payload_extraction",
    "design_guide_compatibility_debug_projection_extraction",
    "design_brain_compute_rebound_debug_compatibility_payload_deletion",
    "design_guide_compute_optimisation_selector_debug_projection_extraction",
    "design_guide_independence_lock",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status", "zero_authority_lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper or "NOT_LOCKED" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": _status_from_payload(payload)}


def _source_checks() -> dict[str, bool]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    controller_source = _read(CONTROLLER)
    return {
        "same_object_verifier_payload_stamped": "final_publication_verifier_payload" in inputs_source
        and "final_publication_authority_hash" in inputs_source,
        "debug_surfaces_marked_non_authoritative": "legacy_non_authoritative" in inputs_source
        and "compatibility_only" in inputs_source
        and "proof_only" in inputs_source,
        "fallback_shells_marked_non_authoritative": "fallback-only" in inputs_source
        or "fallback_only" in inputs_source,
        "final_publication_has_no_session_or_streamlit": "session_state" not in final_source
        and "streamlit" not in final_source
        and "st." not in final_source,
        "controller_has_no_streamlit": "streamlit" not in controller_source,
        "debug_projection_helpers_exist": "debug_projection" in controller_source
        or "debug_key" in controller_source
        or "proof_hash" in controller_source,
        "page_debug_storage_remains_page_owned": "guidance_debug" in inputs_source
        and "st.session_state" in inputs_source,
    }


def _payload_invariant_checks(payload: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    if "product_behavior_changed" in payload:
        checks["product_behavior_unchanged"] = payload.get("product_behavior_changed") is False
    if "visible_wording_changed" in payload:
        checks["visible_wording_unchanged"] = payload.get("visible_wording_changed") is False
    if "cta_apply_semantics_changed" in payload:
        checks["cta_apply_semantics_unchanged"] = payload.get("cta_apply_semantics_changed") is False
    if "family_runtime_changed" in payload:
        checks["family_runtime_unchanged"] = payload.get("family_runtime_changed") is False
    if "family_runtime_behavior_changed" in payload:
        checks["family_runtime_behavior_unchanged"] = payload.get("family_runtime_behavior_changed") is False
    if "zero_authority_lock_status" in payload:
        checks["zero_authority_locked"] = payload.get("zero_authority_lock_status") == "LOCKED"
    if "payload_branch_result" in payload:
        checks["same_object_payload_branch"] = payload.get("payload_branch_result") == "same_object_hash_stamped"
    return checks


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Evidence / Debug Surface Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers proof/evidence/debug surfaces. These surfaces may store and expose evidence, but must not own engineering truth, publication truth, CTA truth, display truth, or Apply semantics.",
        "",
        "## Ownership",
        "",
        "- Design Brain proof helpers own proof payload shape and hashes.",
        "- FinalDesignGuidePublication owns publication/display/CTA truth.",
        "- inputs_page.py may store session/debug data only as non-authoritative shell/debug state.",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in snapshot.get("source_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Artifacts", ""])
    for prefix, row in (snapshot.get("focused_artifacts") or {}).items():
        lines.append(f"- `{prefix}`: `{row.get('status')}` at `{row.get('path')}`")
    if snapshot.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    lines.extend(["", f"JSON: `{snapshot['artifact']}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    focused = {prefix: _latest_payload(prefix) for prefix in FOCUSED_PREFIXES}
    source_checks = _source_checks()

    blockers: list[str] = []
    for key, passed in source_checks.items():
        if not passed:
            blockers.append(f"source check failed: {key}")
    invariant_checks: dict[str, dict[str, bool]] = {}
    for prefix, row in focused.items():
        if row.get("status") != "PASS":
            blockers.append(f"focused artifact is not PASS: {prefix}")
        invariants = _payload_invariant_checks(dict(row.get("payload") or {}))
        invariant_checks[prefix] = invariants
        for key, passed in invariants.items():
            if not passed:
                blockers.append(f"invariant failed for {prefix}: {key}")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_evidence_debug_surface_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_evidence_debug_surface_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_evidence_debug_surface_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "evidence/debug surfaces",
        "source_checks": source_checks,
        "focused_artifacts": {
            prefix: {"status": row.get("status"), "path": row.get("path")}
            for prefix, row in focused.items()
        },
        "invariant_checks": invariant_checks,
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_evidence_debug_surface_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
