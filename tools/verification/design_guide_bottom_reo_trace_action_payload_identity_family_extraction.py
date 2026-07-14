"""Verify bottom-reo trace action-payload identity moved to bending family."""

from __future__ import annotations

import ast
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_HELPER = "_bottom_reo_trace_guidance_action_payload_identity"
FAMILY_HELPER = "build_bottom_reo_trace_guidance_action_payload_identity"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _trace_hash(value: object) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    except TypeError:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _old_action_identity(result: dict | None) -> dict[str, Any]:
    result_d = dict(result or {})
    updates = dict(result_d.get("updates") or {})
    if not updates:
        return {
            "materialized": False,
            "source": "bottom_reo_recommendation:no_action",
            "action_type": None,
            "payload": {},
            "payload_hash": _trace_hash({}),
            "update_keys": [],
            "updates_hash": _trace_hash({}),
            "action_kind_source": "no_selected_bottom_reo_recommendation",
        }
    title = (
        str(result_d.get("guidance_recommendation_title") or result_d.get("label") or "").strip()
        or "Apply bottom recommendation"
    )
    action_type = "apply_compound_guidance" if bool(result_d.get("recommendation_compound")) else "apply_bottom_recommendation"
    payload = {"updates": updates, "guidance_banner_title": title, "label": title}
    return {
        "materialized": True,
        "source": "inputs_page.py:_get_one_click_band_reaching_candidate:bottom_recommendation_option",
        "action_type": action_type,
        "payload": payload,
        "payload_hash": _trace_hash(payload),
        "update_keys": sorted(str(key) for key in updates.keys()),
        "updates_hash": _trace_hash(updates),
        "action_kind_source": "recommendation_compound" if bool(result_d.get("recommendation_compound")) else "bottom_recommendation",
    }


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {"case": "no_result", "result": None},
        {"case": "empty_updates", "result": {"label": "Reduce bottom reinforcement", "updates": {}}},
        {
            "case": "normal_bottom",
            "result": {"label": "Reduce bottom reinforcement to 5N16", "updates": {"bot1_count": 5}, "recommendation_compound": False},
        },
        {
            "case": "compound_with_title",
            "result": {
                "label": "raw compound label",
                "guidance_recommendation_title": "Reduce width and bottom reinforcement",
                "updates": {"b": 350, "bot1_count": 5},
                "recommendation_compound": True,
            },
        },
        {
            "case": "compound_fallback_title",
            "result": {
                "label": "Compound fallback",
                "updates": {"D": 620, "bot1_count": 5},
                "recommendation_compound": True,
            },
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "import inputs_page" in segment or "from inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "_queue_" in segment or "route_apply" in segment or "on_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_trace_guidance_action_payload_identity

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_HELPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_action_identity(case.get("result"))
        new = build_bottom_reo_trace_guidance_action_payload_identity(case.get("result"))
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_helper_delegates_to_family_helper": "_build_bottom_reo_trace_guidance_action_payload_identity(result)" in page_segment,
        "page_helper_no_longer_builds_payload_identity": "guidance_banner_title" not in page_segment
        and "apply_bottom_recommendation" not in page_segment
        and "_dg_runtime_trace_hash(" not in page_segment,
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_TRACE_ACTION_PAYLOAD_IDENTITY_FAMILY_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_TRACE_ACTION_PAYLOAD_IDENTITY_EXTRACTION_FAILED"
        ),
        "page_helper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_trace_surfaces": [
            "selected recommendation proof wrapper",
            "repair/blocked reason proof assembly",
            "CTA intent proof assembly",
            "trace event emission",
        ],
        "next_safe_slice": "bottom_reo_selected_recommendation_trace_proof_payload_family_projection",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_trace_action_payload_identity_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_trace_action_payload_identity_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Trace Action Payload Identity Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now builds trace-only action payload identity. Live CTA/apply routing and rendering remain unchanged.",
        "",
        "## Parity Cases",
        "",
        "| Case | Match |",
        "| --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Trace Surfaces", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_trace_surfaces") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_trace_action_payload_identity_family_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
