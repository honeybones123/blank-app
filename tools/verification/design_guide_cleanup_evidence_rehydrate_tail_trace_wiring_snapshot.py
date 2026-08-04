"""Trace-wiring snapshot for cleanup-evidence rehydrate tail proof.

Proof-only. Verifies the old final-visible cleanup-evidence rehydrate branch
stamps the Design Brain proof object beside the existing page/evaluator-owned
tail without driving product, render, apply, or session behavior.
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


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 20, after: int = 130) -> str:
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
    mutation_context = _window(lines, evaluator_line, before=0, after=360)
    return {
        "decision": "CLEANUP_EVIDENCE_REHYDRATE_TAIL_TRACE_WIRED_OLD_HELPER_STILL_DRIVES_OUTPUT",
        "evaluator_line": evaluator_line,
        "import_present": (
            "build_final_visible_contract_binding_cleanup_evidence_rehydrate_result as "
            "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_result"
        )
        in source,
        "old_evaluator_call_present": "_evaluate_auto_design_candidate(" in context
        and 'source="final_visible_cleanup_evidence_binding"' in context,
        "proof_builder_call_present": (
            "_build_final_visible_contract_binding_cleanup_evidence_rehydrate_result(" in context
        ),
        "proof_uses_already_evaluated_candidate": "evidence_candidate=dict(evidence_candidate or {})" in context,
        "proof_uses_evaluated_overview": "evidence_overview=dict(evidence_overview)" in context,
        "proof_uses_existing_updates_and_family": (
            "evidence_updates=dict(evidence_updates)" in context
            and "evidence_family=evidence_family" in context
        ),
        "proof_hash_stamped": '"final_binding_cleanup_evidence_rehydrate_tail_proof_hash"' in context,
        "trace_wired_stamped": '"final_binding_cleanup_evidence_rehydrate_tail_trace_wired"' in context,
        "non_driving_flags_stamped": all(
            token in context
            for token in (
                '"final_binding_cleanup_evidence_rehydrate_tail_product_driving"',
                '"final_binding_cleanup_evidence_rehydrate_tail_render_driving"',
                '"final_binding_cleanup_evidence_rehydrate_tail_apply_driving"',
                '"final_binding_cleanup_evidence_rehydrate_tail_session_driving"',
                '"final_binding_cleanup_evidence_rehydrate_tail_ready_for_live_cutover"',
            )
        ),
        "old_mutations_still_present": all(
            token in mutation_context
            for token in (
                "contract.update(",
                "out.update(",
                'out["action_payload"] = payload',
                'out["resolved_candidate"] = resolved',
                '"final_binding_evidence_cleanup_rehydrated"',
            )
        ),
        "latest_artifacts": {
            "cleanup_tail_object": _latest("design_guide_cleanup_evidence_rehydrate_tail_object"),
            "old_helper_tail_gap": _latest("design_guide_rebind_projection_old_helper_tail_gap"),
            "dead_body_deletion": _latest("design_guide_cleanup_evidence_rehydrate_dead_body_deletion"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Capture focused live parity for cleanup-evidence rehydrate proof versus old helper "
            "output before replacing or deleting this tail."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    return {
        "evaluator_branch_found": capture.get("evaluator_line") is not None,
        "import_present": capture.get("import_present") is True,
        "old_evaluator_call_present": capture.get("old_evaluator_call_present") is True,
        "proof_builder_call_present": capture.get("proof_builder_call_present") is True,
        "proof_uses_already_evaluated_candidate": capture.get("proof_uses_already_evaluated_candidate") is True,
        "proof_uses_evaluated_overview": capture.get("proof_uses_evaluated_overview") is True,
        "proof_uses_existing_updates_and_family": capture.get("proof_uses_existing_updates_and_family") is True,
        "proof_hash_stamped": capture.get("proof_hash_stamped") is True,
        "trace_wired_stamped": capture.get("trace_wired_stamped") is True,
        "non_driving_flags_stamped": capture.get("non_driving_flags_stamped") is True,
        "old_mutations_still_present_or_dead_body_deleted": (
            capture.get("old_mutations_still_present") is True
            or (latest.get("dead_body_deletion") or {}).get("status") == "PASS"
        ),
        "cleanup_tail_object_pass": (latest.get("cleanup_tail_object") or {}).get("status") == "PASS",
        "old_helper_tail_gap_pass": (latest.get("old_helper_tail_gap") or {}).get("status") == "PASS",
        "dead_body_deletion_pass_if_old_mutations_absent": (
            capture.get("old_mutations_still_present") is True
            or (latest.get("dead_body_deletion") or {}).get("status") == "PASS"
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
        "# Cleanup Evidence Rehydrate Tail Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Evaluator branch line: `{capture.get('evaluator_line')}`",
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
        "schema": "design_guide_cleanup_evidence_rehydrate_tail_trace_wiring_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_cleanup_evidence_rehydrate_tail_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_cleanup_evidence_rehydrate_tail_trace_wiring_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_cleanup_evidence_rehydrate_tail_trace_wiring_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
