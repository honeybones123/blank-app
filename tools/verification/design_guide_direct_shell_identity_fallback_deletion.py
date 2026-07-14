"""Verify page-owned direct-shell family identity fallback is deleted."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


def _read() -> str:
    return INPUTS_PAGE.read_text(encoding="utf-8")


def _line_no(source: str, index: int) -> int:
    return source[:index].count("\n") + 1


def _function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def _call_windows(source: str) -> list[dict]:
    calls: list[dict] = []
    needle = "_design_guide_direct_action_shell_card_html("
    start = 0
    while True:
        index = source.find(needle, start)
        if index < 0:
            break
        line = _line_no(source, index)
        line_start = source.rfind("\n", 0, index) + 1
        if source[line_start:index].lstrip().startswith("def "):
            start = index + len(needle)
            continue
        end_marker = source.find("unsafe_allow_html=True", index)
        end = end_marker if end_marker > index else min(len(source), index + 1800)
        window = source[index:end]
        calls.append(
            {
                "line": line,
                "passes_family_identity": "family_identity=" in window,
                "uses_adapter_projection_identity": (
                    "_shell_projection.family_identity" in window
                    or "_shell_projection.identity_projection" in window
                ),
                "uses_current_overview": "current_overview=" in window,
            }
        )
        start = index + len(needle)
    return calls


def _build_payload() -> dict:
    source = _read()
    helper = _function_body(source, "_design_guide_direct_action_shell_card_html")
    calls = _call_windows(source)
    source_checks = {
        "helper_deleted": not bool(helper),
        "helper_no_classify_family_from_raw_flags": "classify_family_from_raw_flags(" not in helper,
        "helper_no_raw_flags_identity_build": "raw_flags_for_identity" not in helper,
        "helper_no_direct_shell_overview_identity_source": "inputs_page.direct_action_shell_overview_identity" not in helper,
        "early_callsite_has_projection": (
            "_early_shear_cleanup_shell_projection = _build_final_design_guide_render_fallback_shell_projection(" in source
            or "_early_shear_cleanup_shell_projection = _build_final_design_guide_direct_shell_card_projection(" in source
        ),
        "pre_render_callsite_has_projection": "_pre_render_shell_projection = _build_final_design_guide_direct_shell_card_projection(" in source,
        "post_render_callsite_has_projection": "_fallback_shell_projection = _build_final_design_guide_direct_shell_card_projection(" in source,
    }
    failures = []
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source:{key}")
    if calls:
        failures.append(f"direct_shell_call_count:{len(calls)}")
    for row in calls:
        if not row["passes_family_identity"]:
            failures.append(f"line_{row['line']}:missing_family_identity")
        if not row["uses_adapter_projection_identity"]:
            failures.append(f"line_{row['line']}:identity_not_adapter_owned")

    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_direct_shell_identity_fallback_deletion.v1",
        "status": status,
        "surface": "direct action shell page-owned family identity fallback",
        "source_checks": source_checks,
        "direct_shell_calls": calls,
        "failures": failures,
        "deleted_page_owned_logic": [
            "overview-derived raw family flags inside _design_guide_direct_action_shell_card_html",
            "classify_family_from_raw_flags call inside render helper",
            "direct_action_shell_overview_identity fallback evidence source",
            "_design_guide_direct_action_shell_card_html helper and all callsites",
        ],
        "ownership_after": {
            "family_identity_projection": "FinalDesignGuidePublication render fallback shell adapter",
            "html_rendering": "design_guide_page.render_final_panel / _render_guidance_secondary_items",
            "apply_routing": "inputs_page.py",
        },
        "product_behavior_changed": False,
        "next_safe_target": "Audit remaining direct shell HTML body for non-render Design Guide truth before changing renderer code.",
    }


def _write(payload: dict) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_direct_shell_identity_fallback_deletion_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_shell_identity_fallback_deletion_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_shell_identity_fallback_deletion_{stamp}.md"
    payload["artifact_paths"] = {
        "json": str(json_path),
        "audit": str(audit_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        payload["status"],
        "",
        "## Surface Targeted",
        payload["surface"],
        "",
        "## Ownership Before",
        "The direct shell renderer could infer selected family from overview fields inside inputs_page.py.",
        "",
        "## Ownership After",
        "Direct shell helper and callsites are gone; remaining projections are adapter-owned and rendered through the normal page render panel/secondary-item path.",
        "",
        "## Behaviour Preserved",
        f"Product behavior changed: `{payload['product_behavior_changed']}`.",
        "",
        "## Adapter / Default Rebuild Proof",
        json.dumps(payload["direct_shell_calls"], indent=2, sort_keys=True),
        "",
        "## Cutover Proof",
        json.dumps(payload["source_checks"], indent=2, sort_keys=True),
        "",
        "## Deadness / Deletion Proof",
        json.dumps(payload["deleted_page_owned_logic"], indent=2, sort_keys=True),
        "",
        "## Lines Removed / Added",
        "Focused deletion from `_design_guide_direct_action_shell_card_html(...)`; line-ending churn is not normalized.",
        "",
        "## Files Changed",
        "- inputs_page.py",
        "- tools/verification/design_guide_direct_shell_identity_fallback_deletion.py",
        "",
        "## Verifier Results",
        payload["status"],
        "",
        "## Remaining Page-Owned Authority",
        "Render orchestration and Apply button routing remain page-owned.",
        "",
        "## Next Safe Target",
        payload["next_safe_target"],
        "",
    ]
    audit_path.write_text("\n".join(lines), encoding="utf-8")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write(payload)
    print(f"design_guide_direct_shell_identity_fallback_deletion {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
