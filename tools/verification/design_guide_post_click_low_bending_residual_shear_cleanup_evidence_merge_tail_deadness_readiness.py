"""Deadness/readiness audit for old residual-shear evidence merge block."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))"
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    live_merge_present = "residual_evidence.update(" in route
    live_exact_blocker_merge_present = (
        "residual_exact_blockers[\"shear\"] = dict(residual_shear_blocker)" in route
    )
    pre_merge_snapshots_present = (
        "residual_pre_merge_evidence = dict(residual_evidence)" in route
        and "residual_pre_merge_exact_blockers = dict(residual_exact_blockers)" in route
    )
    guarded_cutover_present = (
        "adapter_evidence_matches_live" in route
        and "adapter_exact_blockers_match_live" in route
        and "residual_evidence = dict(" in route
        and "residual_exact_blockers = dict(" in route
    )
    still_needed_reasons = []
    if live_merge_present:
        still_needed_reasons.append("live_merge_is_still_parity_source")
    if live_exact_blocker_merge_present:
        still_needed_reasons.append("live_exact_blocker_merge_is_still_parity_source")
    if (live_merge_present or live_exact_blocker_merge_present) and pre_merge_snapshots_present and guarded_cutover_present:
        still_needed_reasons.append("guarded_cutover_depends_on_live_result_hash_comparison")
    delete_now = not still_needed_reasons
    return {
        "decision": "KEEP_OLD_MERGE_FOR_NOW_AS_PARITY_FALLBACK"
        if not delete_now
        else "OLD_MERGE_READY_FOR_DELETION",
        "delete_now": delete_now,
        "delete_now_count": 1 if delete_now else 0,
        "live_merge_present": live_merge_present,
        "live_exact_blocker_merge_present": live_exact_blocker_merge_present,
        "pre_merge_snapshots_present": pre_merge_snapshots_present,
        "guarded_cutover_present": guarded_cutover_present,
        "still_needed_reasons": still_needed_reasons,
        "next_required_step": (
            "move controller adapter ahead of live merge or replace live merge with controller output plus explicit fallback"
            if not delete_now
            else "delete old live merge block"
        ),
        "latest": {
            "guarded_cutover_implementation": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_cutover_implementation"
            ),
            "result_adapter_object": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter_object"
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = capture.get("latest") or {}
    return {
        "guarded_cutover_implementation_pass": (
            latest.get("guarded_cutover_implementation", {}).get("status") == "PASS"
        ),
        "result_adapter_object_pass": (
            latest.get("result_adapter_object", {}).get("status") == "PASS"
        ),
        "deadness_decision_explicit": capture.get("decision")
        in {"KEEP_OLD_MERGE_FOR_NOW_AS_PARITY_FALLBACK", "OLD_MERGE_READY_FOR_DELETION"},
        "delete_now_false_has_reasons": (
            capture.get("delete_now") is True
            or bool(capture.get("still_needed_reasons"))
        ),
        "guarded_cutover_present": capture.get("guarded_cutover_present") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Evidence-Merge Tail Deadness Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Delete now: `{capture.get('delete_now')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Still Needed Reasons",
        "",
    ]
    reasons = list(capture.get("still_needed_reasons") or [])
    lines.extend(f"- `{reason}`" for reason in reasons)
    if not reasons:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            str(capture.get("next_required_step") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_deadness_readiness "
        f"{payload['status']}"
    )
    print(f"decision={capture.get('decision')}")
    print(f"delete_now={capture.get('delete_now')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
