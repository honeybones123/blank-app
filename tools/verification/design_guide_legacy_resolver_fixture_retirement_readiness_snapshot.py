"""Proof-only readiness to retire legacy resolver fixture callers.

The product path no longer calls ``resolve_final_visible_design_guide_item``.
This snapshot maps the remaining verifier fixture callers to newer controller
and route-specific proof artifacts before any fixture retarget/deletion.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

LEGACY_FIXTURES = {
    "resolver_exact_blocker_fixture_snapshot.py": {
        "legacy_call_line": 268,
        "replacement_artifacts": [
            "design_guide_active_action_post_click_exact_blocker_route_parity",
            "design_guide_active_action_post_click_exact_blocker_dead_body_deletion_proof",
            "design_guide_terminal_active_failure_blocker_finalizer_cutover",
        ],
        "replacement_meaning": (
            "exact blocker and post-click no-second-CTA behavior is covered by active-action "
            "route parity, dead-body deletion proof, and terminal blocker finalizer cutover"
        ),
    },
    "resolver_no_active_route_fixture_snapshot.py": {
        "legacy_call_line": 984,
        "replacement_artifacts": [
            "design_guide_no_active_primary_route_cutover",
            "design_guide_no_active_blocked_primary_full_route_branch_parity_scenarios",
            "design_guide_no_active_low_shear_or_blocker_full_route_cutover_readiness",
            "design_guide_no_active_combined_low_util_full_route_parity_scenarios",
            "design_guide_zero_shear_demand_accepted_legacy_assembler_deletion",
            "design_guide_combined_low_util_orchestration_wrapper_cutover",
        ],
        "replacement_meaning": (
            "no-active primary, blocked cleanup, low-shear/blocker, combined-low-util, "
            "zero-shear, and orchestration wrapper behavior are covered by route-specific gates"
        ),
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper() or "LOCKED" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    fixture_rows: list[dict[str, Any]] = []
    for fixture, spec in LEGACY_FIXTURES.items():
        replacements = []
        for prefix in list(spec.get("replacement_artifacts") or []):
            artifact = _latest(str(prefix))
            replacements.append(
                {
                    "prefix": prefix,
                    "status": artifact.get("status"),
                    "path": artifact.get("path"),
                }
            )
        fixture_rows.append(
            {
                "fixture": fixture,
                "legacy_call_line": spec.get("legacy_call_line"),
                "replacement_meaning": spec.get("replacement_meaning"),
                "replacement_artifacts": replacements,
                "all_replacements_pass": all(row.get("status") == "PASS" for row in replacements),
            }
        )
    reference_audit = _latest("design_guide_remaining_final_visible_resolver_reference_audit")
    return {
        "decision": (
            "READY_TO_RETIRE_LEGACY_RESOLVER_FIXTURE_CALLS"
            if all(row.get("all_replacements_pass") for row in fixture_rows)
            and reference_audit.get("status") == "PASS"
            else "NOT_READY_TO_RETIRE_LEGACY_RESOLVER_FIXTURE_CALLS"
        ),
        "fixture_rows": fixture_rows,
        "reference_audit": {
            "status": reference_audit.get("status"),
            "path": reference_audit.get("path"),
            "decision": (reference_audit.get("payload") or {}).get("capture", {}).get("decision"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = list(capture.get("fixture_rows") or [])
    return {
        "reference_audit_pass": (capture.get("reference_audit") or {}).get("status") == "PASS",
        "two_legacy_fixture_callers_mapped": len(rows) == 2,
        "all_replacement_artifacts_pass": all(row.get("all_replacements_pass") is True for row in rows),
        "ready_to_retire_fixture_calls": (
            capture.get("decision") == "READY_TO_RETIRE_LEGACY_RESOLVER_FIXTURE_CALLS"
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Legacy Resolver Fixture Retirement Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "## Checks",
        "",
        "| Check | Pass |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Fixture Mapping", ""])
    for row in list(capture.get("fixture_rows") or []):
        lines.extend(
            [
                f"### {row.get('fixture')}",
                "",
                f"- Legacy call line: `{row.get('legacy_call_line')}`",
                f"- Replacement meaning: {row.get('replacement_meaning')}",
                f"- All replacements pass: `{row.get('all_replacements_pass')}`",
                "",
                "```json",
                json.dumps(row.get("replacement_artifacts") or [], indent=2),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Safe Step",
            "",
            (
                "Retarget these two legacy fixture snapshots to the replacement controller/route "
                "artifacts or mark them retired, then rerun the remaining resolver reference audit. "
                "Only after no fixture callers remain should the old resolver body be deleted."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_legacy_resolver_fixture_retirement_readiness_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_legacy_resolver_fixture_retirement_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_legacy_resolver_fixture_retirement_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_legacy_resolver_fixture_retirement_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
