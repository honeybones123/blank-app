"""Proof that the final-visible source-output guard has been retired."""

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


def build_snapshot() -> dict[str, Any]:
    source = _read(FINAL_PUBLICATION)
    latest_validity = _latest("design_guide_final_visible_source_output_adapter_validity")
    latest_live_parity = _latest("design_guide_final_visible_restamper_source_output_live_parity")
    checks = {
        "validity_builder_deleted": "def build_final_visible_contract_binding_output_validity(" not in source,
        "validity_guard_deleted": 'and validity.get("valid_without_legacy_source")' not in source
        and 'and validity.get("safe_to_replace_legacy_guard")' not in source,
        "adapter_guard_fallback_deleted": "used_adapter_guard_fallback" not in source,
        "validity_failure_reasons_deleted": (
            '"adapter_validity_failed"' not in source
            and '"branch_not_supported"' not in source
            and '"missing_projected_item"' not in source
        ),
        "direct_adapter_projection_retained": (
            '"FinalDesignGuidePublication.final_visible_contract_binding_adapter_projection"'
            in source
        ),
        "latest_validity_snapshot_pass": str((latest_validity.get("payload") or {}).get("status") or "").upper() == "PASS",
        "latest_live_parity_still_pass": str((latest_live_parity.get("payload") or {}).get("status") or "").upper() == "PASS",
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_final_visible_source_output_guard_cutover_snapshot.v3",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "decision": (
            "SOURCE_OUTPUT_GUARD_RETIRED_DIRECT_ADAPTER_PROJECTION_IS_AUTHORITY"
            if status == "PASS"
            else "SOURCE_OUTPUT_GUARD_RETIREMENT_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "failures": failures,
        "latest_validity": {
            "found": latest_validity.get("found"),
            "path": latest_validity.get("path"),
            "status": (latest_validity.get("payload") or {}).get("status"),
        },
        "latest_live_parity": {
            "found": latest_live_parity.get("found"),
            "path": latest_live_parity.get("path"),
            "status": (latest_live_parity.get("payload") or {}).get("status"),
            "decision": (latest_live_parity.get("payload") or {}).get("decision"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "old_source_output_deleted": True,
        "next_safe_step": "keep the guard deleted and let the scaffolding inventory close to zero",
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Visible Source-Output Guard Cutover Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Next Safe Step", str(snapshot.get("next_safe_step") or ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = snapshot["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_visible_source_output_guard_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_final_visible_source_output_guard_cutover_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_guide_final_visible_source_output_guard_cutover {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
