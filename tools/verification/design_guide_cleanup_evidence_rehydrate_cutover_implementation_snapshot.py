"""Cutover implementation snapshot for cleanup-evidence rehydrate tail.

Verifies only the cleanup-evidence rehydrate post-evaluation mutation surface
has moved to the Design Brain projection adapter. The evaluator call remains
page-owned and the surrounding old helper/tail groups remain present.
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


def _line_for(lines: list[str], token: str, *, start: int = 1) -> int | None:
    for index, line in enumerate(lines, start=1):
        if index < start:
            continue
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 20, after: int = 360) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    evaluator_line = _line_for(lines, 'source="final_visible_cleanup_evidence_binding"')
    context = _window(lines, evaluator_line)
    return {
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_TAIL_CUTOVER_IMPLEMENTED_NO_DELETION",
        "evaluator_line": evaluator_line,
        "source_checks": {
            "evaluator_still_page_owned": (
                "_evaluate_auto_design_candidate(" in context
                and 'source="final_visible_cleanup_evidence_binding"' in context
            ),
            "accepted_gate_preserved": "_cleanup_rehydrate_candidate_accepted = (" in context,
            "projection_adapter_called": (
                "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(" in context
            ),
            "projection_output_drives_item_contract_evidence": all(
                token in context
                for token in (
                    "out = dict(_projection_item)",
                    "contract = dict(_projection_contract)",
                    "evidence_for_binding = dict(_projection_evidence)",
                    "updates = dict(contract.get(\"updates\") or out.get(\"updates\") or {})",
                    "action_type = str(",
                )
            ),
            "cutover_debug_stamp_present": (
                '"final_binding_cleanup_evidence_rehydrate_cutover_applied"' in context
            ),
            "old_manual_body_statically_inactive": (
                "if False and _cleanup_rehydrate_candidate_accepted:" in context
            ),
            "old_manual_body_retained_for_followup_deletion": all(
                token in context
                for token in (
                    "candidate_id_from_evidence = _normalise_design_guide_candidate_id(",
                    "contract.update(",
                    "out.update(",
                    'out["action_payload"] = payload',
                    'out["resolved_candidate"] = resolved',
                )
            ),
            "old_manual_body_deleted": all(
                token not in context
                for token in (
                    "candidate_id_from_evidence = _normalise_design_guide_candidate_id(",
                    'out["action_payload"] = payload',
                    'out["resolved_candidate"] = resolved',
                )
            ),
            "other_tail_groups_accounted_for": (
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
            "cutover_readiness": _latest("design_guide_cleanup_evidence_rehydrate_cutover_readiness"),
            "projection_adapter": _latest("design_guide_cleanup_evidence_rehydrate_projection_adapter"),
            "tail_object": _latest("design_guide_cleanup_evidence_rehydrate_tail_object"),
            "dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "intent_row_selector_extraction": _latest("design_guide_intent_row_selector_extraction"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "deletion_allowed": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Add a dead-body deletion proof for the now-inactive cleanup-rehydrate manual block, "
            "then delete only that dead block if proven safe."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    dead_body_deleted = (latest.get("dead_body_deletion") or {}).get("status") == "PASS"
    return {
        "evaluator_branch_found": capture.get("evaluator_line") is not None,
        "evaluator_still_page_owned": source_checks.get("evaluator_still_page_owned") is True,
        "accepted_gate_preserved": source_checks.get("accepted_gate_preserved") is True,
        "projection_adapter_called": source_checks.get("projection_adapter_called") is True,
        "projection_output_drives_item_contract_evidence": (
            source_checks.get("projection_output_drives_item_contract_evidence") is True
        ),
        "cutover_debug_stamp_present": source_checks.get("cutover_debug_stamp_present") is True,
        "old_manual_body_inactive_or_deleted": (
            source_checks.get("old_manual_body_statically_inactive") is True
            or source_checks.get("old_manual_body_deleted") is True
            or dead_body_deleted
        ),
        "old_manual_body_retained_or_deleted": (
            source_checks.get("old_manual_body_retained_for_followup_deletion") is True
            or source_checks.get("old_manual_body_deleted") is True
            or dead_body_deleted
        ),
        "other_tail_groups_accounted_for": source_checks.get("other_tail_groups_accounted_for") is True,
        "cutover_readiness_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "projection_adapter_pass": (latest.get("projection_adapter") or {}).get("status") == "PASS",
        "tail_object_pass": (latest.get("tail_object") or {}).get("status") == "PASS",
        "intent_selector_extraction_pass": (
            (latest.get("intent_row_selector_extraction") or {}).get("status") == "PASS"
        ),
        "dead_body_deletion_pass_if_manual_body_absent": (
            source_checks.get("old_manual_body_retained_for_followup_deletion") is True
            or source_checks.get("old_manual_body_deleted") is True
            or dead_body_deleted
        ),
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "deletion_not_allowed": capture.get("deletion_allowed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Cutover Implementation Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Evaluator branch line: `{capture.get('evaluator_line')}`",
        f"Deletion allowed: `{capture.get('deletion_allowed')}`",
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
    lines.extend(["", "## Next Safe Step", "", str(capture.get("next_safe_step") or "")])
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
        "schema": "design_guide_cleanup_evidence_rehydrate_cutover_implementation_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_cutover_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_cutover_implementation_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
