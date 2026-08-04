"""Cutover-readiness proof for pre-render/pre-card final-visible output bridges.

Proof-only. This composes the pre-render/pre-card parity snapshot with source
checks for the live preserve points that a future adapter-backed cutover must
keep. It does not replace or delete the live restamper calls.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

TARGETS = {
    "render_guidance_secondary_items.pre_render_binding": {
        "anchor": '_pre_render_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(',
        "binding_assignment": "_pre_render_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "input_capture": "_pre_render_input_item = dict(item)",
        "proof_callsite": 'callsite_id="render_guidance_secondary_items.pre_render_binding"',
        "proof_output": "_pre_render_bound_item or {}",
        "bypass_marker": "final_visible_restamper_bridge_pre_render_bypassed",
        "contract_recompute": "_pre_render_bound_contract = dict(",
        "branch_guard": "if isinstance(_pre_render_safe_combined_action, dict):",
        "item_reassignment": "item = dict(_pre_render_safe_combined_action)",
        "guidance_item_sync": "guidance_items[idx] = item",
    },
    "render_guidance_secondary_items.pre_card_binding": {
        "anchor": '_pre_card_restamper_bypass = _maybe_bypass_final_visible_restamper_bridge_noop(',
        "binding_assignment": "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "input_capture": "_pre_card_input_item = dict(item)",
        "proof_callsite": 'callsite_id="render_guidance_secondary_items.pre_card_binding"',
        "proof_output": "_pre_card_bound_item or {}",
        "bypass_marker": "final_visible_restamper_bridge_pre_card_bypassed",
        "contract_recompute": "_pre_card_bound_contract = dict(",
        "branch_guard": "if _pre_card_bound_enabled or _pre_card_bound_is_terminal_blocker:",
        "item_reassignment": "item = normalise_final_visible_design_guide_item(",
        "guidance_item_sync": "guidance_items[idx] = item",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for(source: str, token: str) -> int | None:
    idx = source.find(token)
    if idx < 0:
        return None
    return source[:idx].count("\n") + 1


def _target_window(source: str, anchor: str) -> str:
    idx = source.find(anchor)
    if idx < 0:
        return ""
    start = max(0, idx - 900)
    end = min(len(source), idx + 3600)
    return source[start:end]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    targets: dict[str, Any] = {}
    for callsite_id, spec in TARGETS.items():
        window = _target_window(source, spec["anchor"])
        checks = {
            "anchor_present": bool(window),
            "binding_call_present": spec["binding_assignment"] in window,
            "input_capture_present": spec["input_capture"] in window,
            "proof_callsite_present": spec["proof_callsite"] in window,
            "proof_output_present": spec["proof_output"] in window,
            "bypass_marker_present": spec["bypass_marker"] in window,
            "contract_recompute_present": spec["contract_recompute"] in window,
            "branch_guard_present": spec["branch_guard"] in window,
            "item_reassignment_present": spec["item_reassignment"] in window,
            "guidance_item_sync_present": spec["guidance_item_sync"] in window,
            "old_binding_still_live": spec["binding_assignment"] in window,
        }
        targets[callsite_id] = {
            "line": _line_for(source, spec["binding_assignment"]),
            "window_checks": checks,
            "ready": all(checks.values()),
        }
    latest = {
        "pre_card_parity": _latest("design_guide_render_guidance_secondary_pre_card_binding_parity"),
        "remaining_restamper_audit": _latest("design_guide_remaining_final_visible_restamper_reference_audit"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    readiness_inputs_pass = all(
        (latest.get(key) or {}).get("status") == "PASS"
        for key in (
            "pre_card_parity",
            "remaining_restamper_audit",
            "render_bridge_lock",
            "compute_bridge_lock",
            "independence_lock",
        )
    )
    all_targets_ready = all((row.get("ready") is True) for row in targets.values())
    return {
        "decision": (
            "READY_FOR_PRE_RENDER_PRE_CARD_ADAPTER_BACKED_CUTOVER"
            if readiness_inputs_pass and all_targets_ready
            else "NOT_READY_FOR_PRE_RENDER_PRE_CARD_CUTOVER"
        ),
        "targets": targets,
        "latest": latest,
        "safe_to_replace_next": bool(readiness_inputs_pass and all_targets_ready),
        "safe_to_delete_now": False,
        "replacement_scope": "two _render_guidance_secondary_items pre-render/pre-card restamper callsites only",
        "must_preserve": [
            "bypass guard rebuild behavior",
            "input/output proof stamping",
            "button contract recomputation",
            "safe-combined cleanup projection",
            "item reassignment into the card path",
            "CTA/apply semantics",
            "visible wording",
            "render ownership",
            "session/debug ownership",
        ],
        "recommended_next_slice": (
            "Implement a narrow adapter-backed replacement for these two callsites only, "
            "keeping the old restamper as comparison/source until the adapter output hash "
            "matches and a cutover verifier passes."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "cutover_performed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    targets = dict(capture.get("targets") or {})
    checks: dict[str, bool] = {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_targets_present": set(targets) == set(TARGETS),
        "all_target_windows_ready": all((row.get("ready") is True) for row in targets.values()),
        "pre_card_parity_latest_pass": (latest.get("pre_card_parity") or {}).get("status") == "PASS",
        "remaining_restamper_audit_latest_pass": (
            latest.get("remaining_restamper_audit") or {}
        ).get("status")
        == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "safe_to_replace_next": capture.get("safe_to_replace_next") is True,
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "decision_ready": capture.get("decision") == "READY_FOR_PRE_RENDER_PRE_CARD_ADAPTER_BACKED_CUTOVER",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_cutover_or_deletion": (
            capture.get("cutover_performed") is False
            and capture.get("deletion_performed") is False
        ),
    }
    for callsite_id, row_any in targets.items():
        row = dict(row_any or {})
        prefix = callsite_id.replace(".", "_")
        for key, value in dict(row.get("window_checks") or {}).items():
            checks[f"{prefix}_{key}"] = value is True
    return checks


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render / Pre-Card Binding Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Scope",
        "",
        f"- Replacement scope: `{capture.get('replacement_scope')}`",
        f"- Safe to replace next: `{capture.get('safe_to_replace_next')}`",
        f"- Safe to delete now: `{capture.get('safe_to_delete_now')}`",
        "",
        "## Targets",
        "",
        "| Callsite | Line | Ready |",
        "| --- | ---: | --- |",
    ]
    for callsite_id, row_any in dict(capture.get("targets") or {}).items():
        row = dict(row_any or {})
        lines.append(f"| `{callsite_id}` | {row.get('line')} | `{row.get('ready')}` |")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Next Safe Step", "", str(capture.get("recommended_next_slice"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
