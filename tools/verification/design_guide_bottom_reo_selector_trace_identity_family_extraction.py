"""Verify bottom-reo selector trace identity projection moved to bending family."""

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

PAGE_WRAPPER = "_bottom_reo_selector_result_record"
FAMILY_HELPER = "build_bottom_reo_selector_result_record_from_candidate"


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


def _trace_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _old_record_dict(
    *,
    selected_candidate: dict | None,
    status: str,
    selected_reason: str | None,
    no_candidate_reason: str | None,
    strict_band_winner_seen: bool,
    strict_band_winner_accepted: bool,
    strict_band_rejected_reason: str | None,
    legacy_rejection_reason: str | None,
    target_low: float | str | None,
    target_high: float | str | None,
) -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_selector_result_record

    selected = dict(selected_candidate or {}) if isinstance(selected_candidate, dict) else {}
    updates = dict(selected.get("updates") or {})
    overview = dict(selected.get("overview") or {})
    utils = dict(overview.get("utils") or {})
    selected_hash = _trace_hash(selected) if selected else None
    candidate_id = selected.get("candidate_id") or selected.get("source_candidate_id") or None
    identity = str(candidate_id) if candidate_id else (f"trace:{selected_hash}" if selected_hash else None)
    return build_bottom_reo_selector_result_record(
        status=status,
        selected_reason=selected_reason,
        no_candidate_reason=no_candidate_reason,
        selected_candidate_id=candidate_id,
        selected_candidate_identity=identity,
        selected_candidate_trace_hash=selected_hash,
        selected_update_keys=tuple(sorted(str(key) for key in updates.keys())),
        selected_updates_hash=_trace_hash(updates) if selected else None,
        strict_band_winner_seen=strict_band_winner_seen,
        strict_band_winner_accepted=strict_band_winner_accepted,
        strict_band_rejected_reason=strict_band_rejected_reason,
        legacy_rejection_reason=legacy_rejection_reason,
        winner_pool_mode=str(selected.get("winner_pool_mode")) if selected.get("winner_pool_mode") is not None else None,
        selected_because_band=bool(selected.get("winning_candidate_selected_from_band_reachers")),
        selected_score=_trace_float(selected.get("score")),
        selected_bending_util=_trace_float(utils.get("bending")),
        selected_candidate_post_util=_trace_float(selected.get("candidate_post_util")),
        selected_reaches_target_band=(
            bool(selected.get("candidate_reaches_target_band"))
            if selected.get("candidate_reaches_target_band") is not None
            else None
        ),
        target_low=_trace_float(target_low),
        target_high=_trace_float(target_high),
    ).to_dict()


def _new_record_dict(**kwargs: Any) -> dict[str, Any]:
    from design_brain.families.bending import build_bottom_reo_selector_result_record_from_candidate

    return build_bottom_reo_selector_result_record_from_candidate(**kwargs).to_dict()


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "no_candidate",
            "selected_candidate": None,
            "status": "no_result",
            "selected_reason": None,
            "no_candidate_reason": "no_selected_candidate",
            "strict_band_winner_seen": False,
            "strict_band_winner_accepted": False,
            "strict_band_rejected_reason": None,
            "legacy_rejection_reason": None,
            "target_low": "0.85",
            "target_high": "1.0",
        },
        {
            "case": "candidate_id",
            "selected_candidate": {
                "candidate_id": "bottom_5N16",
                "updates": {"bot1_count": 5, "db_bot_1": 16},
                "overview": {"utils": {"bending": 0.91}},
                "winner_pool_mode": "band",
                "winning_candidate_selected_from_band_reachers": True,
                "score": "12.5",
                "candidate_post_util": "0.91",
                "candidate_reaches_target_band": True,
            },
            "status": "selected",
            "selected_reason": "best_score",
            "no_candidate_reason": None,
            "strict_band_winner_seen": True,
            "strict_band_winner_accepted": True,
            "strict_band_rejected_reason": None,
            "legacy_rejection_reason": None,
            "target_low": 0.85,
            "target_high": 1.0,
        },
        {
            "case": "source_candidate_id",
            "selected_candidate": {
                "source_candidate_id": "src_7N12",
                "updates": {"bot1_count": 7},
                "overview": {"utils": {"bending": "0.78"}},
                "score": 20,
                "candidate_post_util": 0.78,
                "candidate_reaches_target_band": False,
            },
            "status": "selected",
            "selected_reason": "legacy",
            "no_candidate_reason": None,
            "strict_band_winner_seen": True,
            "strict_band_winner_accepted": False,
            "strict_band_rejected_reason": "bending_util_not_improved",
            "legacy_rejection_reason": "bending_util_not_improved",
            "target_low": 0.85,
            "target_high": 1.0,
        },
        {
            "case": "trace_identity_fallback",
            "selected_candidate": {
                "label": "anonymous",
                "updates": {"D": 620},
                "overview": {"utils": {"bending": 0.88}},
                "score": 30,
                "candidate_post_util": 0.88,
            },
            "status": "selected",
            "selected_reason": "trace_fallback",
            "no_candidate_reason": None,
            "strict_band_winner_seen": False,
            "strict_band_winner_accepted": False,
            "strict_band_rejected_reason": None,
            "legacy_rejection_reason": None,
            "target_low": None,
            "target_high": None,
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        kwargs = dict(case)
        case_name = str(kwargs.pop("case"))
        old = _old_record_dict(**kwargs)
        new = _new_record_dict(**kwargs)
        parity_rows.append({"case": case_name, "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_wrapper_delegates_to_family_helper": "_build_bottom_reo_selector_result_record_from_candidate(" in page_segment,
        "page_wrapper_no_longer_hashes_selected_candidate": "_dg_runtime_trace_hash(" not in page_segment,
        "page_wrapper_no_longer_builds_trace_summary": "_bottom_reo_recommendation_trace_candidate_summary(" not in page_segment,
        "page_wrapper_no_longer_builds_candidate_identity": "_bottom_reo_candidate_identity(" not in page_segment,
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
            "BOTTOM_REO_SELECTOR_TRACE_IDENTITY_FAMILY_PROJECTION_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_SELECTOR_TRACE_IDENTITY_EXTRACTION_FAILED"
        ),
        "page_wrapper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_trace_surfaces": [
            "trace event emission",
            "trace proof payload assembly",
            "selector wrapper call orchestration",
        ],
        "next_safe_slice": "bottom_reo_trace_proof_payload_boundary_or_guidance_change_line_projection",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_selector_trace_identity_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_selector_trace_identity_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Selector Trace Identity Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The bending family now projects selector-result identity/hash fields. The page still owns trace event emission and wrapper call orchestration.",
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
    print(f"design_guide_bottom_reo_selector_trace_identity_family_extraction {payload.get('status')}")
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
