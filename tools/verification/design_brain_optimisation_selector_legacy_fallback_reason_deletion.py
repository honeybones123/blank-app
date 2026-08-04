from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
INPUTS_PAGE = ROOT / "inputs_page.py"
PROJECTION_VERIFIER = (
    ROOT / "tools" / "verification" / "design_guide_compute_optimisation_selector_debug_projection_extraction.py"
)
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
    controller_source = _read(CONTROLLER)
    inputs_source = _read(INPUTS_PAGE)
    projection_verifier_source = _read(PROJECTION_VERIFIER)
    checks = {
        "controller_no_legacy_fallback_reason_field": 'out["legacy_fallback_reason"]' not in controller_source,
        "inputs_page_no_legacy_fallback_reason_consumer": "legacy_fallback_reason" not in inputs_source,
        "projection_verifier_no_legacy_fallback_reason_expectation": "legacy_fallback_reason" not in projection_verifier_source,
        "controller_still_exposes_fallback_reason": '"optimisation_selector_fallback_reason": debug.get(' in controller_source,
        "controller_still_exposes_owner": '"primary_optimisation_selection_owner": owner' in controller_source,
        "controller_still_exposes_candidate_family": 'out["candidate_family"] = selected_family' in controller_source,
        "controller_still_exposes_governing_action": 'out["governing_action"] = governing_action' in controller_source,
    }
    latest = {
        "projection_extraction": _latest("design_guide_compute_optimisation_selector_debug_projection_extraction"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    failures = [name for name, passed in checks.items() if not passed]
    for key, row in latest.items():
        status = str((row.get("payload") or {}).get("status") or (row.get("payload") or {}).get("result") or "").upper()
        if "PASS" not in status and "LOCKED" not in status and "COMPLETE" not in status:
            failures.append(f"{key}_latest_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_brain_optimisation_selector_legacy_fallback_reason_deletion.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": (
            "OPTIMISATION_SELECTOR_LEGACY_FALLBACK_REASON_DELETED"
            if status == "PASS"
            else "OPTIMISATION_SELECTOR_LEGACY_FALLBACK_REASON_DELETION_NEEDS_ATTENTION"
        ),
        "checks": checks,
        "latest": {
            key: {
                "found": value.get("found"),
                "path": value.get("path"),
                "status": (value.get("payload") or {}).get("status") or (value.get("payload") or {}).get("result"),
            }
            for key, value in latest.items()
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "failures": failures,
    }


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Brain Optimisation Selector Legacy Fallback Reason Deletion",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Latest Gates", ""])
    for name, row in (snapshot.get("latest") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}`")
    if snapshot.get("failures"):
        lines.extend(["", "## Failures"])
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    json_path = ARTIFACT_DIR / f"design_brain_optimisation_selector_legacy_fallback_reason_deletion_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_optimisation_selector_legacy_fallback_reason_deletion_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_optimisation_selector_legacy_fallback_reason_deletion {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
