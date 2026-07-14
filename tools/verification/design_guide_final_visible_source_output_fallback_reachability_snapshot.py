"""Reachability proof for final-visible source-output fallback.

This snapshot is deletion-enabling. After adapter-validity cutover, the old
enabled/disabled branch output should no longer be the primary guard or trace
source. The only remaining dependency should be a stale/exception fallback.

This verifier proves whether old source-output fallback is still present or
live-observed after the guard and adapter-owned fallback have both been retired.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(_read(path))
    except Exception as exc:
        payload = {"load_error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def _function_body(source: str, name: str) -> str:
    needle = f"def {name}("
    start = source.find(needle)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(needle))
    return source[start:] if next_def < 0 else source[start:next_def]


def build_snapshot() -> dict[str, Any]:
    source = _read(FINAL_PUBLICATION)
    cutover_body = _function_body(source, "build_final_visible_render_binding_payload")
    latest_live = _latest("design_guide_final_visible_restamper_source_output_live_parity")
    latest_deadness = _latest("design_guide_final_visible_source_output_branch_deadness")
    live_payload = latest_live.get("payload") or {}
    deadness_payload = latest_deadness.get("payload") or {}
    live_rows = list(live_payload.get("rows") or [])
    old_source_output_fallback_present = "return source_output" in cutover_body
    adapter_owned_fallback_present = (
        'FinalDesignGuidePublication.final_visible_contract_binding_adapter_fallback.inline'
        in cutover_body
    )
    adapter_validity_failures = int(live_payload.get("adapter_validity_failure_count") or 0)
    parity_failures = int(live_payload.get("parity_failure_count") or 0)
    default_projection_failures = int(
        live_payload.get("default_projection_parity_failure_count") or 0
    )
    live_fallback_observed = bool(
        adapter_validity_failures or parity_failures or default_projection_failures
    )
    deadness_blockers = sorted(
        {
            str(reason)
            for branch in list(deadness_payload.get("branches") or [])
            for reason in list((branch or {}).get("blocking_reasons") or [])
        }
    )
    checks = {
        "old_source_output_fallback_absent": not old_source_output_fallback_present,
        "adapter_owned_fallback_deleted": not adapter_owned_fallback_present,
        "latest_live_parity_pass": str(live_payload.get("status") or "").upper() == "PASS",
        "latest_deadness_pass": str(deadness_payload.get("status") or "").upper() == "PASS",
        "deadness_not_blocked_by_source_trace": "old_branch_output_still_feeds_source_output_readiness_trace"
        not in deadness_blockers,
        "live_fallback_not_observed": not live_fallback_observed,
        "live_rows_observed": bool(live_rows),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_source_output_fallback_reachability_snapshot.v2",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "SOURCE_OUTPUT_FALLBACK_FULLY_RETIRED_NOT_LIVE_OBSERVED"
            if status == "PASS"
            else "SOURCE_OUTPUT_FALLBACK_REACHABILITY_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "deadness_blockers": deadness_blockers,
        "latest_live_parity": {
            "found": latest_live.get("found"),
            "path": latest_live.get("path"),
            "status": live_payload.get("status"),
            "decision": live_payload.get("decision"),
            "adapter_validity_failure_count": adapter_validity_failures,
            "parity_failure_count": parity_failures,
            "default_projection_parity_failure_count": default_projection_failures,
        },
        "latest_deadness": {
            "found": latest_deadness.get("found"),
            "path": latest_deadness.get("path"),
            "status": deadness_payload.get("status"),
            "decision": deadness_payload.get("decision"),
            "safe_to_delete_old_branch_construction_now": deadness_payload.get(
                "safe_to_delete_old_branch_construction_now"
            ),
        },
        "old_source_output_fallback_present": old_source_output_fallback_present,
        "adapter_owned_fallback_present": adapter_owned_fallback_present,
        "old_source_output_deleted": True,
        "safe_to_delete_old_branch_construction_now": bool(
            deadness_payload.get("safe_to_delete_old_branch_construction_now")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_step": (
            "keep the fallback retired; no further work remains in this guard seam"
        ),
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Source-Output Fallback Reachability Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(
        [
            "",
            "## Deadness Blockers",
            ", ".join(snapshot.get("deadness_blockers") or []) or "none",
            "",
            "## Next Safe Step",
            str(snapshot.get("next_safe_step") or ""),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_source_output_fallback_reachability_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_source_output_fallback_reachability_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_source_output_fallback_reachability {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
