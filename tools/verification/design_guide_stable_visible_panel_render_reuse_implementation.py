"""Implementation proof for stable visible-panel render reuse keys.

This verifier checks the narrow Inputs smoothness cutover that replaces
transient pre-render session fingerprints with authority/result based panel
reuse keys for the Inputs summary and Design Guide panels. It does not approve
DOM skipping; Streamlit rendering remains live.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TRANSIENT_FIELDS = {
    "state_fingerprint_hash",
    "panel_baseline_fingerprint_hash",
    "design_guide_needs_refresh",
}

SUMMARY_REQUIRED = {
    "results_version",
    "result_cache_hash",
}

DESIGN_GUIDE_REQUIRED = {
    "results_version",
    "final_publication_hash",
    "final_publication_display_hash",
    "final_publication_cta_hash",
    "button_contract_hash",
    "apply_payload_hash",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _nested_function_block(source: str, name: str) -> str:
    match = re.search(rf"^\s{{4}}def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^\s{4}def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _call_region(block: str, surface: str, end_marker: str) -> str:
    start = block.find(f'surface="{surface}"')
    if start < 0:
        return ""
    end = block.find(end_marker, start)
    if end < 0:
        end = len(block)
    return block[start:end]


def _last_call_region(block: str, surface: str, end_marker: str) -> str:
    start = block.rfind(f'surface="{surface}"')
    if start < 0:
        return ""
    end = block.find(end_marker, start)
    if end < 0:
        end = len(block)
    return block[start:end]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "status": payload.get("status")}


def _required_keys_present(region: str, required: set[str]) -> bool:
    return all(f'"{key}"' in region for key in sorted(required))


def _classify() -> dict[str, Any]:
    inputs = _read(ROOT / "inputs_page.py")
    helper = _function_block(inputs, "_record_inputs_stable_render_reuse_trace")
    summary = _nested_function_block(inputs, "_render_current_inputs_summary")
    design_guide = _nested_function_block(inputs, "_render_fresh_design_guide_panel")
    summary_region = _call_region(
        summary,
        "inputs_summary_panel",
        '_phase5c_render_trace("summary_card_render_start")',
    )
    design_region = _call_region(
        design_guide,
        "design_guide_panel",
        '_phase5c_render_trace("design_guide_build_start")',
    )
    design_post_region = _last_call_region(
        design_guide,
        "design_guide_panel",
        'render_timing_mark(',
    )
    checks = {
        "helper_exists": bool(helper),
        "helper_supports_required_fingerprint_keys": "required_fingerprint_keys" in helper,
        "helper_supports_diagnostic_only_trace": "store_trace: bool = True" in helper
        and '"_diagnostic_probes"' in helper,
        "helper_records_missing_required_keys": "missing_required_render_fingerprint_fields" in helper,
        "helper_trace_only": '"trace_only": True' in helper and '"render_skipped": False' in helper,
        "summary_region_exists": bool(summary_region),
        "design_guide_region_exists": bool(design_region),
        "design_guide_post_region_exists": bool(design_post_region),
        "summary_uses_stable_required_keys": _required_keys_present(summary_region, SUMMARY_REQUIRED),
        "design_guide_uses_stable_required_keys": _required_keys_present(
            design_region,
            DESIGN_GUIDE_REQUIRED,
        ),
        "design_guide_post_uses_stable_required_keys": _required_keys_present(
            design_post_region,
            DESIGN_GUIDE_REQUIRED,
        ),
        "summary_excludes_transient_fields": not any(field in summary_region for field in TRANSIENT_FIELDS),
        "design_guide_excludes_transient_fields": not any(field in design_region for field in TRANSIENT_FIELDS),
        "design_guide_post_excludes_transient_fields": not any(
            field in design_post_region for field in TRANSIENT_FIELDS
        ),
        "summary_requires_keys_at_callsite": "required_fingerprint_keys" in summary_region,
        "design_guide_requires_keys_at_callsite": "required_fingerprint_keys" in design_region,
        "design_guide_pre_render_trace_is_diagnostic_only": "store_trace=False" in design_region,
        "design_guide_post_render_trace_stores_authority_fingerprint": "store_trace=False" not in design_post_region
        and "apply_in_flight=False" in design_post_region,
        "no_render_skip_branch_added": "render_skipped = True" not in inputs
        and "if row.get(\"reuse_eligible\")" not in inputs
        and "if trace.get(\"reuse_eligible\")" not in inputs,
    }
    required_checks = sorted(checks)
    missing = [key for key in required_checks if not checks.get(key)]
    return {
        "status": "PASS" if not missing else "FAIL",
        "checks": checks,
        "missing_checks": missing,
        "summary_required_keys": sorted(SUMMARY_REQUIRED),
        "design_guide_required_keys": sorted(DESIGN_GUIDE_REQUIRED),
        "transient_fields_removed_from_reuse_keys": sorted(TRANSIENT_FIELDS),
        "render_skipping_implemented": False,
        "product_behaviour_changed": False,
        "latest": {
            "readiness": _latest("design_guide_stable_visible_panel_render_reuse_readiness"),
            "render_fingerprint_drift": _latest("design_guide_same_session_render_fingerprint_drift"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Stable Visible Panel Render Reuse Implementation",
            "",
            f"Status: `{payload.get('status')}`",
            "",
            "## Executive Summary",
            "",
            "- Inputs summary and Design Guide panel trace keys now use stable authority/result fields.",
            "- Transient pre-render fields are excluded from the reuse fingerprint.",
            "- Missing required authority/result keys force trace-render-required.",
            "- Streamlit rendering remains live; no DOM skip branch was added.",
            "",
            "## Checks",
            "",
            "```json",
            json.dumps(cls.get("checks") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Latest Related Artifacts",
            "",
            "```json",
            json.dumps(cls.get("latest") or {}, indent=2, sort_keys=True),
            "```",
            "",
        ]
    )


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_stable_visible_panel_render_reuse_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_stable_visible_panel_render_reuse_implementation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    created_at = _stamp()
    classification = _classify()
    payload = {
        "schema": "design_guide_stable_visible_panel_render_reuse_implementation.v1",
        "created_at": created_at,
        "status": classification["status"],
        "classification": classification,
        "product_behaviour_changed": False,
    }
    json_path, md_path = _write(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
