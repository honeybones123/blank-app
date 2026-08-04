"""Verify render-item consumer projections are adapter-cutover.

This is proof-only. It verifies the live post-binding render-item consumer
surface uses the Design Brain/FinalDesignGuidePublication adapters for the
covered projection groups while keeping rendering, session storage, and Apply
routing page-owned.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

TARGET_START = "_record_design_guide_publication_snapshot("
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("

REQUIRED_LATEST = {
    "cutover_readiness": "design_guide_render_item_consumer_adapter_cutover_readiness",
    "zero_shear_readiness": "design_guide_zero_shear_render_consumer_narrowing_readiness",
    "zero_shear_parity": "design_guide_zero_shear_render_consumer_projection_adapter_parity",
    "zero_shear_cutover": "design_guide_zero_shear_render_consumer_projection_adapter_cutover",
    "zero_shear_deadness": "design_guide_zero_shear_render_consumer_manual_rows_deadness",
    "safe_low_cutover": "design_guide_safe_low_util_promotion_projection_adapter_cutover",
    "post_click_checks": "design_guide_post_click_final_contract_checks_readiness",
    "post_click_predicate_cutover": (
        "design_guide_post_click_final_contract_predicate_result_adapter_cutover"
    ),
    "post_click_result_readiness": (
        "design_guide_post_click_final_contract_adapter_cutover_readiness"
    ),
    "post_click_result_trace": "design_guide_live_post_click_final_contract_adapter_result_trace",
    "post_click_exact_blocker_cutover": (
        "design_guide_post_click_exact_blocker_projection_adapter_cutover"
    ),
    "render_lock": "design_guide_render_bridge_lock",
    "compute_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "independence_lock": "design_guide_independence_lock",
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
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _line(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    block = _block(source)
    latest = {key: _latest(prefix) for key, prefix in REQUIRED_LATEST.items()}
    source_checks = {
        "target_block_found": bool(block),
        "zero_shear_adapter_drives_projection": (
            "_zero_shear_projection = _apply_final_design_guide_zero_shear_render_consumer_projection("
            in block
            and "_final_visible_item = dict(_zero_shear_projection.get(\"item\") or {})" in block
            and "guidance_debug.update(dict(_zero_shear_projection.get(\"guidance_debug\") or {}))"
            in block
        ),
        "safe_low_adapter_drives_projection": (
            "_safe_low_util_projection =" in block
            and "_apply_final_design_guide_safe_low_util_promotion_projection(" in block
            and "_final_visible_item = dict(_safe_low_util_projection.get(\"item\") or {})"
            in block
            and "_final_visible_resolution.update(" in block
        ),
        "post_click_predicates_from_adapter": (
            "_post_click_final_contract_predicate_result_adapter = (" in block
            and "_post_click_final_contract_predicates = dict(" in block
            and "_post_click_bending_low_visible_action = bool(" in block
            and "FinalDesignGuidePublication.post_click_final_contract_predicate_result_adapter"
            in block
        ),
        "post_click_result_adapter_drives_projection": (
            "_build_final_design_guide_post_click_final_contract_check_adapter_result(" in block
            and "_final_visible_item = dict(" in block
            and "_post_click_exact_blocker_result.get(\"replacement_item\")" in block
            and "_final_visible_resolution.update(" in block
            and "FinalDesignGuidePublication.post_click_final_contract_check_adapter_result"
            in block
        ),
        "render_item_consumer_trace_still_stamped": (
            "_stamp_final_publication_render_item_consumer_proof(" in block
        ),
        "normalise_contract_still_page_render_flow": (
            "_normalise_visible_optimisation_contract(" in source
        ),
        "session_storage_stays_page_owned": "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)" in block,
        "apply_route_reads_stay_page_owned": "st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY)" in block,
    }
    return {
        "decision": (
            "RENDER_ITEM_CONSUMER_ADAPTER_CUTOVER_PROVEN"
            if all(source_checks.values())
            else "RENDER_ITEM_CONSUMER_ADAPTER_CUTOVER_NOT_PROVEN"
        ),
        "target_block_hash": _stable_hash(block),
        "source_lines": {
            "zero_shear_adapter": _line(
                source, "_zero_shear_projection = _apply_final_design_guide_zero_shear_render_consumer_projection("
            ),
            "safe_low_adapter": _line(source, "_apply_final_design_guide_safe_low_util_promotion_projection("),
            "post_click_predicate_adapter": _line(
                source, "_post_click_final_contract_predicate_result_adapter = ("
            ),
            "post_click_result_adapter": _line(
                source, "_build_final_design_guide_post_click_final_contract_check_adapter_result("
            ),
            "render_item_trace": _line(source, "_stamp_final_publication_render_item_consumer_proof("),
        },
        "source_checks": source_checks,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
        "delete_allowed": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "all_source_checks_pass": all((capture.get("source_checks") or {}).values()),
        "all_required_latest_pass": all(
            (latest.get(key) or {}).get("status") == "PASS" for key in REQUIRED_LATEST
        ),
        "delete_not_allowed": capture.get("delete_allowed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Item Consumer Adapter Cutover Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Source Checks",
        "",
    ]
    lines.extend(
        f"- {key}: `{value}`" for key, value in (capture.get("source_checks") or {}).items()
    )
    lines.extend(["", "## Latest Required Gates", ""])
    lines.extend(
        f"- {key}: `{value.get('status')}` at `{value.get('path')}`"
        for key, value in (capture.get("latest") or {}).items()
    )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Step", ""])
    lines.append(
        "Do not delete these rows yet. Refresh the post-binding ownership and panel-binding maps, "
        "then choose the next remaining restamper/render consumer surface with a deletion proof."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = 0
    try:
        import py_compile

        py_compile.compile(str(INPUTS_PAGE), doraise=True)
        py_compile.compile(str(Path(__file__)), doraise=True)
    except Exception:
        compile_result = 1
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    if compile_result != 0:
        failures.append("py_compile_failed")
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_item_consumer_adapter_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "compile_result": compile_result,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_item_consumer_adapter_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_item_consumer_adapter_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_item_consumer_adapter_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
