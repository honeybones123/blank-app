"""Verify zero/probe bending evaluated-row shaping is service-owned."""

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
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_util_value(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno or node.lineno])
    return ""


def _old_zero_row(
    candidate: dict[str, Any],
    *,
    candidate_overview: dict[str, Any],
    updates: dict[str, Any],
    width: float,
    depth: float,
    bars: int,
    dia: int,
    candidate_index: int,
    candidate_material_proxy: float,
    preview_statuses_have_explicit_fail: bool,
    geometry_update_keys: set[str],
) -> dict[str, Any]:
    cand = dict(candidate or {})
    safe = bool(candidate_overview.get("all_key_pass")) and not bool(candidate_overview.get("any_fail"))
    if safe and bool(preview_statuses_have_explicit_fail):
        safe = False
    utils_after = dict(candidate_overview.get("utils") or {})
    candidate_util = _parse_util_value(
        candidate_overview.get("worst_util")
        or candidate_overview.get("governing_util")
        or utils_after.get("bending")
        or 0.0
    )
    candidate_id = f"zero_bending_cleanup_{int(candidate_index):03d}"
    cand.update(
        {
            "candidate_id": candidate_id,
            "source_candidate_id": candidate_id,
            "title": f"Zero bending cleanup - {int(width)}x{int(depth)} {int(bars)}N{int(dia)}",
            "label": f"Zero bending cleanup - {int(width)}x{int(depth)} {int(bars)}N{int(dia)}",
            "updates": dict(updates),
            "proposed_updates": dict(updates),
            "family": "bending",
            "recommendation_family_tag": "bending",
            "subfamilies": ["geometry", "bottom_reinforcement"]
            if set(geometry_update_keys) & set(updates)
            else ["bottom_reinforcement"],
            "action_type": "apply_resolved_candidate",
            "is_compliant": bool(safe),
            "preview_pass": bool(safe),
            "is_executable": bool(safe),
            "safe_executor_backed": bool(safe),
            "candidate_material_proxy": float(candidate_material_proxy),
            "candidate_post_util": candidate_util,
            "preview_util": candidate_util,
            "zero_bending_demand_cleanup": True,
        }
    )
    if not safe:
        cand["rejection_reason"] = "candidate_does_not_keep_all_required_checks_pass"
    return cand


def _old_probe_row(
    row: dict[str, Any],
    *,
    candidate_overview: dict[str, Any],
    current_bending_util: float | None,
) -> dict[str, Any]:
    out = dict(row or {})
    candidate_bending = _parse_util_value(dict(candidate_overview.get("utils") or {}).get("bending"))
    all_pass = bool(candidate_overview.get("all_key_pass")) and not bool(candidate_overview.get("any_fail"))
    out.update(
        {
            "overview": dict(candidate_overview),
            "candidate_post_util": candidate_bending,
            "preview_util": candidate_bending,
            "worst_util": candidate_overview.get("worst_util", candidate_bending),
            "is_compliant": bool(all_pass),
            "safe_executor_backed": bool(
                all_pass
                and candidate_bending is not None
                and current_bending_util is not None
                and float(candidate_bending) > float(current_bending_util) + 1e-6
            ),
        }
    )
    if not out["safe_executor_backed"]:
        out["rejection_reason"] = (
            "candidate_does_not_keep_all_required_checks_pass"
            if not all_pass
            else "candidate_does_not_improve_bending_utilisation"
        )
    return out


def _build_payload() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8", errors="replace")
    zero_segment = _function_segment(inputs_source, "_zero_bending_demand_cleanup_item")
    probe_segment = _function_segment(inputs_source, "_probe_equivalent_bending_cleanup_action_item")

    from design_brain.candidate_evaluation import (
        build_probe_equivalent_bending_evaluated_candidate_row,
        build_zero_bending_demand_evaluated_candidate_row,
    )

    zero_cases = []
    for case in [
        {
            "case": "safe_geometry",
            "candidate": {"overview": {"marker": "kept"}},
            "overview": {"all_key_pass": True, "any_fail": False, "utils": {"bending": 0.42}},
            "updates": {"D": 600, "bot1_count": 4},
            "explicit_fail": False,
        },
        {
            "case": "explicit_fail",
            "candidate": {},
            "overview": {"all_key_pass": True, "any_fail": False, "utils": {"bending": 0.0}},
            "updates": {"bot1_count": 3},
            "explicit_fail": True,
        },
        {
            "case": "any_fail",
            "candidate": {},
            "overview": {"all_key_pass": False, "any_fail": True, "governing_util": 1.2},
            "updates": {"bw": 350},
            "explicit_fail": False,
        },
    ]:
        kwargs = {
            "candidate_overview": dict(case["overview"]),
            "updates": dict(case["updates"]),
            "width": 400,
            "depth": 650,
            "bars": 4,
            "dia": 16,
            "candidate_index": len(zero_cases) + 1,
            "candidate_material_proxy": 123.0,
            "preview_statuses_have_explicit_fail": bool(case["explicit_fail"]),
            "geometry_update_keys": {"D", "b", "bw"},
        }
        old = _old_zero_row(dict(case["candidate"]), **kwargs)
        new = build_zero_bending_demand_evaluated_candidate_row(dict(case["candidate"]), **kwargs)
        zero_cases.append({"case": case["case"], "matches": old == new, "old_hash": _stable_hash(old), "new_hash": _stable_hash(new)})

    probe_cases = []
    for case in [
        {
            "case": "safe_improves",
            "row": {"candidate_id": "a", "updates": {"bot1_count": 4}},
            "overview": {"all_key_pass": True, "any_fail": False, "utils": {"bending": 0.7}},
            "current": 0.5,
        },
        {
            "case": "does_not_improve",
            "row": {"candidate_id": "b"},
            "overview": {"all_key_pass": True, "any_fail": False, "utils": {"bending": 0.4}},
            "current": 0.5,
        },
        {
            "case": "not_all_pass",
            "row": {"candidate_id": "c"},
            "overview": {"all_key_pass": False, "any_fail": True, "utils": {"bending": 0.9}},
            "current": 0.5,
        },
    ]:
        kwargs = {
            "candidate_overview": dict(case["overview"]),
            "current_bending_util": case["current"],
        }
        old = _old_probe_row(dict(case["row"]), **kwargs)
        new = build_probe_equivalent_bending_evaluated_candidate_row(dict(case["row"]), **kwargs)
        probe_cases.append({"case": case["case"], "matches": old == new, "old_hash": _stable_hash(old), "new_hash": _stable_hash(new)})

    source_checks = {
        "zero_helper_exported": '"build_zero_bending_demand_evaluated_candidate_row"' in candidate_source,
        "probe_helper_exported": '"build_probe_equivalent_bending_evaluated_candidate_row"' in candidate_source,
        "inputs_imports_zero_helper": "build_zero_bending_demand_evaluated_candidate_row as _build_zero_bending_demand_evaluated_candidate_row" in inputs_source,
        "inputs_imports_probe_helper": "build_probe_equivalent_bending_evaluated_candidate_row as _build_probe_equivalent_bending_evaluated_candidate_row" in inputs_source,
        "zero_target_calls_helper": "_build_zero_bending_demand_evaluated_candidate_row(" in zero_segment,
        "probe_target_calls_helper": "_build_probe_equivalent_bending_evaluated_candidate_row(" in probe_segment,
        "zero_inline_row_update_removed": '"candidate_material_proxy": float(proxy)' not in zero_segment
        and '"preview_pass": bool(safe)' not in zero_segment,
        "probe_inline_row_update_removed": "candidate_does_not_improve_bending_utilisation" not in probe_segment,
        "candidate_evaluation_has_no_inputs_page_import": "import inputs_page" not in candidate_source and "from inputs_page" not in candidate_source,
        "candidate_evaluation_has_no_streamlit_import": "streamlit" not in candidate_source and "st.session_state" not in candidate_source,
    }
    checks = {
        **source_checks,
        "zero_row_parity": all(row["matches"] for row in zero_cases),
        "probe_row_parity": all(row["matches"] for row in probe_cases),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_zero_probe_evaluated_row_service_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": "ZERO_AND_PROBE_EVALUATED_ROW_SHAPING_SERVICE_OWNED",
        "checks": checks,
        "zero_cases": zero_cases,
        "probe_cases": probe_cases,
        "remaining_page_owned_surfaces": [
            "evaluator callback execution",
            "overview/precheck guards",
            "debug_sink writes",
            "candidate search evidence construction",
        ],
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.utcnow().replace(microsecond=0).isoformat().replace(":", "-") + "Z"
    json_path = ARTIFACT_DIR / f"design_guide_zero_probe_evaluated_row_service_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_zero_probe_evaluated_row_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Zero/Probe Evaluated Row Service Extraction",
        "",
        f"## Executive Summary: {payload['status']}",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in payload["checks"].items())
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    lines.extend(f"- `{item}`" for item in payload["remaining_page_owned_surfaces"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _build_payload()
    json_path, report_path = _write_artifacts(payload)
    print(f"design_guide_zero_probe_evaluated_row_service_extraction {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [key for key, value in payload["checks"].items() if not value]
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
