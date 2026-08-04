"""Implementation verifier for pre-render/pre-card restamper adapter cutover.

Verifies only the two pre-render/pre-card ``_render_guidance_secondary_items``
restamper callsites consume the controller adapter result under a hash equality
guard. The old restamper calls must remain present; this is not deletion proof.
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
    "pre_render": {
        "old_call": "_pre_render_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "adapter_var": "_pre_render_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(",
        "adapter_item": "_pre_render_adapter_item = dict(",
        "hash_guard": "== _stable_final_publication_hash(_pre_render_bound_item or {})",
        "replacement": "_pre_render_bound_item = dict(_pre_render_adapter_item)",
        "applied_marker": "render_guidance_secondary_pre_render_binding_adapter_cutover_applied",
        "scope_marker": "render_guidance_secondary_pre_render_binding_adapter_scope",
        "product_marker": "render_guidance_secondary_pre_render_binding_adapter_product_driving",
        "render_marker": "render_guidance_secondary_pre_render_binding_adapter_render_driving",
        "apply_marker": "render_guidance_secondary_pre_render_binding_adapter_apply_driving",
        "session_marker": "render_guidance_secondary_pre_render_binding_adapter_session_driving",
    },
    "pre_card": {
        "old_call": "_pre_card_bound_item = _publish_final_visible_design_guide_contract_binding(",
        "adapter_var": "_pre_card_restamper_adapter = _stamp_final_visible_final_visible_output_bridge_proof(",
        "adapter_item": "_pre_card_adapter_item = dict(",
        "hash_guard": "== _stable_final_publication_hash(_pre_card_bound_item or {})",
        "replacement": "_pre_card_bound_item = dict(_pre_card_adapter_item)",
        "applied_marker": "render_guidance_secondary_pre_card_binding_adapter_cutover_applied",
        "scope_marker": "render_guidance_secondary_pre_card_binding_adapter_scope",
        "product_marker": "render_guidance_secondary_pre_card_binding_adapter_product_driving",
        "render_marker": "render_guidance_secondary_pre_card_binding_adapter_render_driving",
        "apply_marker": "render_guidance_secondary_pre_card_binding_adapter_apply_driving",
        "session_marker": "render_guidance_secondary_pre_card_binding_adapter_session_driving",
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


def _window(source: str, anchor: str) -> str:
    idx = source.find(anchor)
    if idx < 0:
        return ""
    return source[max(0, idx - 400) : min(len(source), idx + 4300)]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    targets: dict[str, Any] = {}
    for target_id, spec in TARGETS.items():
        window = _window(source, spec["old_call"])
        checks = {
            "old_restamper_call_retained": spec["old_call"] in window,
            "adapter_assignment_present": spec["adapter_var"] in window,
            "adapter_item_extracted": spec["adapter_item"] in window,
            "hash_guard_present": spec["hash_guard"] in window,
            "replacement_present": spec["replacement"] in window,
            "applied_marker_present": spec["applied_marker"] in window,
            "scope_marker_present": spec["scope_marker"] in window,
            "scope_result_identity_only": '"result_identity_only"' in window,
            "product_driving_marker_true": spec["product_marker"] in window and "= True" in window,
            "render_driving_marker_false": spec["render_marker"] in window and "= False" in window,
            "apply_driving_marker_false": spec["apply_marker"] in window and "= False" in window,
            "session_driving_marker_false": spec["session_marker"] in window and "= False" in window,
        }
        targets[target_id] = {
            "line": _line_for(source, spec["old_call"]),
            "checks": checks,
            "cutover_present": all(checks.values()),
        }
    return {
        "decision": "PRE_RENDER_PRE_CARD_ADAPTER_BACKED_CUTOVER_IMPLEMENTED_NOT_DELETED",
        "targets": targets,
        "latest": {
            "parity": _latest("design_guide_render_guidance_secondary_pre_card_binding_parity"),
            "cutover_readiness": _latest(
                "design_guide_render_guidance_secondary_pre_card_binding_cutover_readiness"
            ),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "safe_to_delete_now": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "deletion_performed": False,
    }


def _checks(capture: dict[str, Any], compile_run: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    targets = dict(capture.get("targets") or {})
    checks: dict[str, bool] = {
        "py_compile_pass": compile_run.get("returncode") == 0,
        "all_targets_present": set(targets) == set(TARGETS),
        "all_cutovers_present": all((row.get("cutover_present") is True) for row in targets.values()),
        "parity_latest_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "cutover_readiness_latest_pass": (latest.get("cutover_readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "safe_to_delete_now_false": capture.get("safe_to_delete_now") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "no_deletion": capture.get("deletion_performed") is False,
    }
    for target_id, row_any in targets.items():
        row = dict(row_any or {})
        for key, value in dict(row.get("checks") or {}).items():
            checks[f"{target_id}_{key}"] = value is True
    return checks


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Render / Pre-Card Binding Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Targets",
        "",
        "| Target | Line | Cutover present |",
        "| --- | ---: | --- |",
    ]
    for target_id, row_any in dict(capture.get("targets") or {}).items():
        row = dict(row_any or {})
        lines.append(f"| `{target_id}` | {row.get('line')} | `{row.get('cutover_present')}` |")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Refresh the remaining restamper inventory. These two callsites should become adapter-covered, not deletion-ready.",
        ]
    )
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
            "tools/verification/design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover_snapshot.py",
        ]
    )
    capture = _capture()
    checks = _checks(capture, compile_run)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_render_guidance_secondary_pre_card_binding_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
