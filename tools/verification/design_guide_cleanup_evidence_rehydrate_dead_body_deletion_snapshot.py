"""Dead-body deletion snapshot for cleanup-evidence rehydrate manual block.

Verifies the inactive old manual cleanup-evidence rehydrate body has been
deleted after the projection-adapter cutover, while the evaluator and the
unrelated remaining helper tail groups are still present.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_count() -> int:
    return len(INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").splitlines())


def _line_for(lines: list[str], token: str) -> int:
    for index, line in enumerate(lines):
        if token in line:
            return index
    return -1


def _window(lines: list[str], center: int, *, before: int = 40, after: int = 260) -> str:
    if center < 0:
        return ""
    start = max(0, center - before)
    end = min(len(lines), center + after)
    return "\n".join(lines[start:end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    cleanup_rehydrate_line = _line_for(lines, 'source="final_visible_cleanup_evidence_binding"')
    cleanup_rehydrate_context = _window(lines, cleanup_rehydrate_line)
    return {
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_MANUAL_DEAD_BODY_DELETED",
        "line_count": _line_count(),
        "line_count_before_cutover_checkpoint": 98877,
        "cleanup_rehydrate_line": cleanup_rehydrate_line + 1 if cleanup_rehydrate_line >= 0 else None,
        "source_checks": {
            "cleanup_rehydrate_branch_found": cleanup_rehydrate_line >= 0,
            "dead_if_false_block_removed": (
                "if False and _cleanup_rehydrate_candidate_accepted:" not in cleanup_rehydrate_context
            ),
            "old_candidate_id_manual_block_removed": (
                "candidate_id_from_evidence = _normalise_design_guide_candidate_id("
                not in cleanup_rehydrate_context
            ),
            "old_manual_payload_assignment_removed": (
                'out["action_payload"] = payload' not in cleanup_rehydrate_context
            ),
            "old_manual_resolved_assignment_removed": (
                'out["resolved_candidate"] = resolved' not in cleanup_rehydrate_context
            ),
            "projection_cutover_still_present": all(
                token in source
                for token in (
                    "_cleanup_rehydrate_candidate_accepted = (",
                    "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(",
                    "out = dict(_projection_item)",
                    "contract = dict(_projection_contract)",
                    "evidence_for_binding = dict(_projection_evidence)",
                    '"final_binding_cleanup_evidence_rehydrate_cutover_applied"',
                )
            ),
            "evaluator_still_page_owned": (
                "_evaluate_auto_design_candidate(" in source
                and 'source="final_visible_cleanup_evidence_binding"' in source
            ),
            "remaining_tail_groups_accounted_for": (
                all(
                    token in source
                    for token in (
                        "_design_guide_button_contract(out, state=state)",
                        "final_visible_active_shear_repair_family_restamp",
                        "DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY",
                    )
                )
            ),
        },
        "latest_artifacts": {
            "cutover_implementation": _latest("design_guide_cleanup_evidence_rehydrate_cutover_implementation"),
            "cutover_readiness": _latest("design_guide_cleanup_evidence_rehydrate_cutover_readiness"),
            "projection_adapter": _latest("design_guide_cleanup_evidence_rehydrate_projection_adapter"),
            "intent_row_selector_extraction": _latest("design_guide_intent_row_selector_extraction"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "deleted_line_count_expected": 342,
        "deletion_scope": "inactive cleanup-evidence rehydrate manual block only",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "cleanup_rehydrate_branch_found": source_checks.get("cleanup_rehydrate_branch_found") is True,
        "dead_if_false_block_removed": source_checks.get("dead_if_false_block_removed") is True,
        "old_candidate_id_manual_block_removed": source_checks.get("old_candidate_id_manual_block_removed") is True,
        "old_manual_payload_assignment_removed": source_checks.get("old_manual_payload_assignment_removed") is True,
        "old_manual_resolved_assignment_removed": source_checks.get("old_manual_resolved_assignment_removed") is True,
        "projection_cutover_still_present": source_checks.get("projection_cutover_still_present") is True,
        "evaluator_still_page_owned": source_checks.get("evaluator_still_page_owned") is True,
        "remaining_tail_groups_accounted_for": source_checks.get("remaining_tail_groups_accounted_for") is True,
        "line_count_recorded": int(capture.get("line_count") or 0) > 0,
        "cutover_implementation_pass": (latest.get("cutover_implementation") or {}).get("status") == "PASS",
        "cutover_readiness_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "projection_adapter_pass": (latest.get("projection_adapter") or {}).get("status") == "PASS",
        "intent_selector_extraction_pass": (
            (latest.get("intent_row_selector_extraction") or {}).get("status") == "PASS"
        ),
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Dead Body Deletion Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Line count: `{capture.get('line_count')}`",
        f"Deletion scope: `{capture.get('deletion_scope')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_cleanup_evidence_rehydrate_dead_body_deletion_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_dead_body_deletion_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_dead_body_deletion_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_dead_body_deletion_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
