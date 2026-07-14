"""Cutover readiness for post-click final-contract predicate/result adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

TARGET_START = "_final_contract_for_post_click = dict(_final_visible_item.get(\"button_contract\") or {})"
TARGET_END = "_post_click_bending_audit = {}"
ADAPTER_STAMP = "_stamp_final_publication_post_click_final_contract_predicate_result_adapter("
PAGE_PREDICATE_ROWS = {
    "contract_enabled": "_post_click_bending_low_contract_enabled =",
    "exact_blocker": "_post_click_bending_exact_blocker_on_visible_item =",
    "requires_exact_blocker": "_post_click_bending_low_requires_exact_blocker =",
    "visible_action": "_post_click_bending_low_visible_action =",
}
PAGE_INPUT_ROWS = {
    "last_apply_route": "_last_apply_route_for_visible =",
    "binding_audit": "_binding_audit_for_visible =",
    "unresolved_families": "_post_click_unresolved_families_for_visible =",
    "below_floor_families": "_post_click_below_floor_families_for_visible =",
    "current_state": "current_state",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(source)
    latest = {
        "object": _latest("design_guide_post_click_final_contract_predicate_result_adapter_object"),
        "trace": _latest("design_guide_live_post_click_final_contract_predicate_result_adapter_trace"),
        "parity": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios"
        ),
        "decomposition": _latest("design_guide_post_click_final_contract_consumer_decomposition"),
        "render_item_cutover_readiness": _latest(
            "design_guide_render_item_consumer_adapter_cutover_readiness"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    page_predicate_rows_present = {
        name: token in target for name, token in PAGE_PREDICATE_ROWS.items()
    }
    page_input_rows_present = {
        name: token in target for name, token in PAGE_INPUT_ROWS.items()
    }
    adapter_ready = all(
        (latest.get(key) or {}).get("status") == "PASS"
        for key in (
            "object",
            "trace",
            "parity",
            "decomposition",
            "render_item_cutover_readiness",
            "independence_lock",
            "render_bridge_lock",
            "compute_bridge_lock",
        )
    )
    return {
        "decision": "READY_FOR_PREDICATE_RESULT_ADAPTER_CUTOVER"
        if adapter_ready
        else "NOT_READY_FOR_PREDICATE_RESULT_ADAPTER_CUTOVER",
        "target_block_found": bool(target),
        "adapter_stamp_present": ADAPTER_STAMP in target,
        "page_predicate_rows_present": page_predicate_rows_present,
        "page_input_rows_present": page_input_rows_present,
        "page_predicate_rows_still_live": all(page_predicate_rows_present.values()),
        "page_input_rows_still_live": all(page_input_rows_present.values()),
        "cutover_allowed": bool(adapter_ready and target and ADAPTER_STAMP in target),
        "deletion_allowed": False,
        "allowed_next_change": (
            "replace page-local predicate result reads with adapter predicate_result values; "
            "keep page-owned input collection, bending audit construction, replacement item building, "
            "CTA/apply/render/session behavior, visible wording, and family runtime behavior unchanged"
        ),
        "must_remain_page_owned": sorted(PAGE_INPUT_ROWS),
        "must_not_change": (
            "engineering_behavior",
            "visible_wording",
            "cta_apply_semantics",
            "family_runtimes",
            "solver_math",
            "target_bands",
            "widget_keys",
            "session_state_behavior",
            "render_apply_ownership",
        ),
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "adapter_stamp_present": capture.get("adapter_stamp_present") is True,
        "page_predicate_rows_still_live": capture.get("page_predicate_rows_still_live") is True,
        "page_input_rows_still_live": capture.get("page_input_rows_still_live") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "decomposition_pass": (latest.get("decomposition") or {}).get("status") == "PASS",
        "render_item_cutover_readiness_pass": (
            latest.get("render_item_cutover_readiness") or {}
        ).get("status")
        == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "cutover_allowed": capture.get("cutover_allowed") is True,
        "deletion_not_allowed": capture.get("deletion_allowed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Predicate/Result Adapter Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Cutover allowed: `{capture.get('cutover_allowed')}`",
        f"- Deletion allowed: `{capture.get('deletion_allowed')}`",
        f"- Page predicate rows still live: `{capture.get('page_predicate_rows_still_live')}`",
        f"- Page input rows still live: `{capture.get('page_input_rows_still_live')}`",
        "",
        "## Allowed Next Change",
        "",
        str(capture.get("allowed_next_change")),
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            (
                "Next safe implementation slice: replace only the page-local predicate result "
                "booleans with values read from the adapter payload, then rerun parity and locks. "
                "Do not delete the surrounding page-owned input collection or replacement builder."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
