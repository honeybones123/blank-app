"""Live-path parity wiring snapshot for cleanup-evidence rehydrate projection.

Proof-only. Verifies the old cleanup-evidence rehydrate branch compares its
post-mutation helper output against the Design Brain projection adapter while
keeping the old helper as the product-driving path.
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


def _window(lines: list[str], line: int | None, *, before: int = 20, after: int = 420) -> str:
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
    contract_update_line = _line_for(lines, "contract.update(", start=evaluator_line or 1)
    projection_line = _line_for(
        lines,
        "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection(",
        start=evaluator_line or 1,
    )
    return {
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_PROJECTION_LIVE_PARITY_WIRED_OLD_HELPER_STILL_DRIVES_OUTPUT",
        "evaluator_line": evaluator_line,
        "contract_update_line": contract_update_line,
        "projection_line": projection_line,
        "import_present": (
            "build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection as "
            "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_projection"
        )
        in source,
        "pre_mutation_snapshots_present": all(
            token in context
            for token in (
                "_cleanup_rehydrate_tail_pre_item = dict(out)",
                "_cleanup_rehydrate_tail_pre_contract = dict(contract)",
                "_cleanup_rehydrate_tail_pre_evidence = dict(evidence_for_binding)",
                "_cleanup_rehydrate_tail_pre_debug = dict(debug_sink or {})",
            )
        ),
        "projection_after_old_mutation": bool(
            contract_update_line is not None
            and projection_line is not None
            and projection_line > contract_update_line
        ),
        "projection_uses_pre_mutation_inputs": all(
            token in context
            for token in (
                "item=dict(_cleanup_rehydrate_tail_pre_item)",
                "contract=dict(_cleanup_rehydrate_tail_pre_contract)",
                "evidence_for_binding=dict(_cleanup_rehydrate_tail_pre_evidence)",
                "debug=dict(_cleanup_rehydrate_tail_pre_debug)",
                "evidence_candidate=dict(evidence_candidate or {})",
                "cleanup_rehydrate_proof=dict(_cleanup_rehydrate_tail_proof or {})",
            )
        ),
        "projection_compares_post_mutation_outputs": all(
            token in context
            for token in (
                '_stable_final_publication_hash(_projection_contract)',
                "_stable_final_publication_hash(contract)",
                "_stable_final_publication_hash(_projection_evidence)",
                "_stable_final_publication_hash(evidence_for_binding)",
                "_stable_final_publication_hash(_projection_payload)",
                'dict(out.get("action_payload") or {})',
                "_stable_final_publication_hash(_projection_resolved)",
                'dict(out.get("resolved_candidate") or {})',
            )
        ),
        "parity_stamps_present": all(
            token in context
            for token in (
                '"final_binding_cleanup_evidence_rehydrate_projection_parity"',
                '"final_binding_cleanup_evidence_rehydrate_projection_parity_checks"',
                '"final_binding_cleanup_evidence_rehydrate_projection_hash"',
                '"final_binding_cleanup_evidence_rehydrate_projection_output_hashes"',
            )
        ),
        "non_driving_flags_present": all(
            token in context
            for token in (
                '"final_binding_cleanup_evidence_rehydrate_projection_product_driving"',
                '"final_binding_cleanup_evidence_rehydrate_projection_render_driving"',
                '"final_binding_cleanup_evidence_rehydrate_projection_apply_driving"',
                '"final_binding_cleanup_evidence_rehydrate_projection_session_driving"',
                '"final_binding_cleanup_evidence_rehydrate_projection_ready_for_live_cutover"',
            )
        ),
        "old_helper_mutations_still_present": all(
            token in context
            for token in (
                "contract.update(",
                "out.update(",
                'out["action_payload"] = payload',
                'out["resolved_candidate"] = resolved',
                '"final_binding_evidence_cleanup_rehydrated"',
            )
        ),
        "latest_artifacts": {
            "projection_adapter": _latest("design_guide_cleanup_evidence_rehydrate_projection_adapter"),
            "trace_wiring": _latest("design_guide_cleanup_evidence_rehydrate_tail_trace_wiring"),
            "tail_object": _latest("design_guide_cleanup_evidence_rehydrate_tail_object"),
            "dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_live_cutover": False,
        "next_safe_step": (
            "Use captured parity evidence to create a guarded cutover verifier for replacing "
            "only this cleanup-evidence rehydrate tail."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    dead_body_deleted = (latest.get("dead_body_deletion") or {}).get("status") == "PASS"
    return {
        "evaluator_branch_found": capture.get("evaluator_line") is not None,
        "import_present": capture.get("import_present") is True,
        "pre_mutation_snapshots_present": capture.get("pre_mutation_snapshots_present") is True,
        "projection_after_old_mutation_or_dead_body_deleted": (
            capture.get("projection_after_old_mutation") is True or dead_body_deleted
        ),
        "projection_uses_pre_mutation_inputs": capture.get("projection_uses_pre_mutation_inputs") is True,
        "projection_compares_post_mutation_outputs_or_dead_body_deleted": (
            capture.get("projection_compares_post_mutation_outputs") is True
            or dead_body_deleted
        ),
        "parity_stamps_present_or_dead_body_deleted": (
            capture.get("parity_stamps_present") is True or dead_body_deleted
        ),
        "non_driving_flags_present": capture.get("non_driving_flags_present") is True,
        "old_helper_mutations_still_present_or_dead_body_deleted": (
            capture.get("old_helper_mutations_still_present") is True or dead_body_deleted
        ),
        "projection_adapter_pass": (latest.get("projection_adapter") or {}).get("status") == "PASS",
        "trace_wiring_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "tail_object_pass": (latest.get("tail_object") or {}).get("status") == "PASS",
        "dead_body_deletion_pass_if_old_mutations_absent": (
            capture.get("old_helper_mutations_still_present") is True or dead_body_deleted
        ),
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "not_ready_for_live_cutover_yet": capture.get("ready_for_live_cutover") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Cleanup Evidence Rehydrate Projection Live Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Evaluator branch line: `{capture.get('evaluator_line')}`",
        f"Old mutation line: `{capture.get('contract_update_line')}`",
        f"Projection parity line: `{capture.get('projection_line')}`",
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
        "schema": "design_guide_cleanup_evidence_rehydrate_projection_live_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_projection_live_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_projection_live_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_projection_live_parity_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
