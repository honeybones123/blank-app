from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        payload = {"load_error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def _active_item(*, scope: str, marker: str, active_blocker: bool = False) -> dict[str, Any]:
    return {
        "title": "Existing active blocker",
        "title_main": "Existing active blocker",
        "family": "bending",
        "source_marker": marker,
        "primary_action": "Bending repair blocked.",
        "active_under_capacity_blocker": bool(active_blocker),
        "candidate_search_evidence": {
            "search_scope": scope,
            "active_fail_repair_search_scope": scope,
            "repair_search_exhaustive": True,
            "exact_blockers_by_family": {
                "bending": {
                    "family": "bending",
                    "blocked_reason": "snapshot blocker",
                    "blocked_ladder": "BENDING_FAIL_GOVERNS",
                    "no_valid_candidate": True,
                }
            },
        },
    }


def build_snapshot() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_terminal_active_failure_blocker_source_proof,
        run_design_guide_controller_terminal_active_failure_blocker_finalizer_route,
    )

    cases = [
        {
            "name": "valid_active_source_kept",
            "active_item": _active_item(scope="active_fail_depth_width_exhausted", marker="active"),
            "raw_guidance_items": [{"source_marker": "fallback", "title": "Fallback blocker"}],
        },
        {
            "name": "active_under_capacity_source_kept",
            "active_item": _active_item(
                scope="cleanup_search",
                marker="active_under_capacity",
                active_blocker=True,
            ),
            "raw_guidance_items": [{"source_marker": "fallback", "title": "Fallback blocker"}],
        },
        {
            "name": "invalid_cleanup_source_falls_back",
            "active_item": _active_item(scope="cleanup_search", marker="invalid_cleanup"),
            "raw_guidance_items": [{"source_marker": "fallback", "title": "Fallback blocker"}],
        },
    ]
    rows = []
    for case in cases:
        proof = build_design_guide_controller_terminal_active_failure_blocker_source_proof(
            active_item=case["active_item"],
            raw_guidance_items=case["raw_guidance_items"],
        )
        route_result = run_design_guide_controller_terminal_active_failure_blocker_finalizer_route(
            active_item=case["active_item"],
            raw_guidance_items=case["raw_guidance_items"],
            active_family="bending",
            active_title="Bending repair blocked",
            active_failures=["bending"],
            final_overview={
                "bending": {"utilisation": 1.42, "status": "FAIL"},
                "shear": {"utilisation": 0.82, "status": "PASS"},
            },
            final_state={"D": 650.0, "b": 400.0, "Mu_pos": 800.0},
            debug_probe={"snapshot": "terminal_active_failure_blocker_source_proof_object"},
            state_fingerprint_fn=lambda state: "state:" + _stable(dict(state or {})),
            suppress_design_guide_blocker_cta_fn=lambda item: {
                **dict(item or {}),
                "primary_card_actionable": False,
                "button_contract": {
                    "enabled": False,
                    "actionable": False,
                    "reason": "terminal_active_failure_blocker_proof_object",
                },
            },
        )
        rows.append(
            {
                "case": case["name"],
                "active_source_marker_before_filter": (
                    dict(proof.get("active_blocker_source_before_filter") or {}).get("source_marker")
                ),
                "selected_blocker_source_marker": dict(proof.get("blocker_source") or {}).get("source_marker"),
                "route_selected_source_marker": dict(route_result.get("item") or {}).get("source_marker"),
                "active_scope": proof.get("active_scope"),
                "active_blocker_source_kept": proof.get("active_blocker_source_kept"),
                "blocker_source_hash_present": bool(proof.get("blocker_source_hash")),
                "fallback_item_hash_present": bool(proof.get("fallback_item_hash")),
                "selection_hash_present": bool(proof.get("blocker_source_selection_hash")),
                "proof_only": proof.get("proof_only"),
                "product_driving": proof.get("product_driving"),
            }
        )
    latest = {
        "route_object": _latest("design_guide_terminal_active_failure_blocker_finalizer_route_object"),
        "cutover": _latest("design_guide_terminal_active_failure_blocker_finalizer_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    checks = {
        "valid_case_keeps_active_marker": next(
            row["selected_blocker_source_marker"] == "active"
            for row in rows
            if row["case"] == "valid_active_source_kept"
        ),
        "active_under_capacity_keeps_active_marker": next(
            row["selected_blocker_source_marker"] == "active_under_capacity"
            for row in rows
            if row["case"] == "active_under_capacity_source_kept"
        ),
        "invalid_cleanup_falls_back": next(
            row["selected_blocker_source_marker"] == "fallback"
            for row in rows
            if row["case"] == "invalid_cleanup_source_falls_back"
        ),
        "proof_hash_fields_present": all(
            row["blocker_source_hash_present"]
            and row["fallback_item_hash_present"]
            and row["selection_hash_present"]
            for row in rows
        ),
        "route_uses_same_selected_markers": all(
            row["selected_blocker_source_marker"] == row["route_selected_source_marker"] or not row["route_selected_source_marker"]
            for row in rows
        ),
        "proof_only_not_product_driving": all(
            row["proof_only"] is True and row["product_driving"] is False for row in rows
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    for key, row in latest.items():
        status = str((row.get("payload") or {}).get("status") or (row.get("payload") or {}).get("result") or "").upper()
        if "PASS" not in status and "LOCKED" not in status and "COMPLETE" not in status:
            failures.append(f"{key}_latest_not_pass")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_brain_terminal_active_failure_blocker_source_proof_object.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
        "rows": rows,
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
        "# Design Brain Terminal Active Failure Blocker Source Proof Object",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Checks",
    ]
    for name, passed in (snapshot.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Cases"])
    for row in snapshot.get("rows") or []:
        lines.append(
            f"- `{row['case']}`: proof_marker=`{row['selected_blocker_source_marker']}` route_marker=`{row['route_selected_source_marker']}`"
        )
    lines.extend(["", "## Latest Gates"])
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
    json_path = ARTIFACT_DIR / f"design_brain_terminal_active_failure_blocker_source_proof_object_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_terminal_active_failure_blocker_source_proof_object_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_terminal_active_failure_blocker_source_proof_object {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
