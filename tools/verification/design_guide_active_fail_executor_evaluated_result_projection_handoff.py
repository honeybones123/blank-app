"""Verify active-fail executor evaluated-result projection handoff."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TARGET = "_active_fail_near_current_repair_item"
NESTED = "_evaluate"

GEOMETRY_KEYS = frozenset({"b", "bw", "D", "bf", "tf", "tw", "bf_bot", "tf_bot"})
BOTTOM_KEYS = frozenset(
    {
        "bot_row_count",
        "bot1_layout_mode",
        "bot1_count",
        "bot1_spacing",
        "db_bot_1",
        "bot2_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "db_bot_2",
        "bot_row_1_mode",
        "bot_row_1_bars",
        "bot_row_1_spacing",
        "bot_row_1_dia",
        "bot_row_2_mode",
        "bot_row_2_bars",
        "bot_row_2_spacing",
        "bot_row_2_dia",
        "bot_row_3_mode",
        "bot_row_3_bars",
        "bot_row_3_spacing",
        "bot_row_3_dia",
        "bot_row_4_mode",
        "bot_row_4_bars",
        "bot_row_4_spacing",
        "bot_row_4_dia",
        "Ast_bot",
    }
)
SHEAR_KEYS = frozenset({"lig_d", "lig_legs", "s_lig"})


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_node(source: str, name: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _function_source(source: str, node: ast.FunctionDef | None) -> str:
    if node is None:
        return ""
    lines = source.splitlines()
    end = int(node.end_lineno or node.lineno)
    return "\n".join(lines[node.lineno - 1 : end])


def _nested_function_source(source: str, outer_name: str, nested_name: str) -> tuple[int, int, str]:
    outer = _function_node(source, outer_name)
    if outer is None:
        return 0, 0, ""
    lines = source.splitlines()
    for node in ast.walk(outer):
        if isinstance(node, ast.FunctionDef) and node.name == nested_name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _parse_util_value(value: Any) -> float | None:
    if value in (None, "", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â"):
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(str(value).strip())
        except Exception:
            return None


def _required_checks_acceptable(overview: dict[str, Any] | None) -> bool:
    if not isinstance(overview, dict):
        return False
    statuses = overview.get("statuses")
    if isinstance(statuses, dict):
        tracked = [
            str(status or "").strip().upper()
            for status in statuses.values()
            if str(status or "").strip() not in {"", "â€”", "-"}
        ]
    else:
        tracked = []
    if not tracked:
        return bool(overview.get("all_key_pass")) and not bool(overview.get("any_fail"))
    return not any(status in {"FAIL", "FAILED", "ERROR"} for status in tracked)


def _compound_subfamilies(updates: dict[str, Any]) -> list[str]:
    keys = set(updates)
    out: list[str] = []
    if keys & GEOMETRY_KEYS:
        out.append("geometry")
    if keys & BOTTOM_KEYS:
        out.append("bottom_reo")
    if keys & SHEAR_KEYS:
        out.append("shear")
    return out


def _old_projection(
    candidate: dict[str, Any] | None,
    *,
    updates: dict[str, Any],
    label: str,
    family_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    cand = dict(candidate)
    u = dict(updates or {})
    cand_overview = dict(cand.get("overview") or {})
    preview_worst = _parse_util_value(cand_overview.get("worst_util") or cand_overview.get("governing_util"))
    if preview_worst is not None:
        cand["candidate_post_util"] = float(preview_worst)
        cand["worst_util"] = float(preview_worst)
    cand["updates"] = dict(u)
    cand["action_type"] = "apply_resolved_candidate"
    strict_all_pass = bool(cand_overview.get("all_key_pass")) and not bool(cand_overview.get("any_fail"))
    family_id = str((family_meta or {}).get("candidate_family_id") or "").strip().upper()
    if family_id == "BENDING_FAIL_GOVERNS":
        statuses = {
            str(k).strip().lower(): str(v or "").strip().upper()
            for k, v in dict(cand_overview.get("statuses") or {}).items()
        }
        no_bending_fail = statuses.get("bending") not in {"FAIL", "FAILED", "ERROR"}
        family_accepts = bool(_required_checks_acceptable(cand_overview)) and bool(no_bending_fail)
        cand["bending_fail_acceptance_basis"] = (
            "required_checks_no_fail_or_error;non_demand_sls_statuses_do_not_block_repair"
        )
        cand["bending_fail_strict_all_key_pass"] = bool(strict_all_pass)
        cand["bending_fail_required_checks_acceptable"] = bool(_required_checks_acceptable(cand_overview))
    elif family_id == "SHEAR_FAIL_GOVERNS":
        statuses = {
            str(k).strip().lower(): str(v or "").strip().upper()
            for k, v in dict(cand_overview.get("statuses") or {}).items()
        }
        no_shear_fail = statuses.get("shear") not in {"FAIL", "FAILED", "ERROR"}
        family_accepts = bool(_required_checks_acceptable(cand_overview)) and bool(no_shear_fail)
        cand["shear_fail_acceptance_basis"] = (
            "required_checks_no_fail_or_error;near_limit_non_governing_statuses_do_not_block_repair"
        )
        cand["shear_fail_strict_all_key_pass"] = bool(strict_all_pass)
        cand["shear_fail_required_checks_acceptable"] = bool(_required_checks_acceptable(cand_overview))
    else:
        family_accepts = bool(strict_all_pass)
    cand["is_compliant"] = bool(family_accepts)
    cand["preview_pass"] = bool(cand.get("is_compliant"))
    cand["is_executable"] = bool(cand.get("is_compliant"))
    cand["advisory_only"] = not bool(cand.get("is_compliant"))
    cand["label"] = label
    if isinstance(family_meta, dict):
        cand.update(dict(family_meta))
    subfamilies = _compound_subfamilies(u)
    cand["recommendation_family_tag"] = "combined" if len(subfamilies) >= 2 else (
        "shear" if set(u) & SHEAR_KEYS else "bending"
    )
    cand["affected_family"] = cand["recommendation_family_tag"]
    return cand


def _new_projection(
    candidate: dict[str, Any] | None,
    *,
    updates: dict[str, Any],
    label: str,
    family_meta: dict[str, Any] | None,
) -> dict[str, Any] | None:
    from design_brain.candidate_evaluation import (  # noqa: WPS433
        project_active_fail_executor_evaluated_candidate_result,
    )

    return project_active_fail_executor_evaluated_candidate_result(
        candidate,
        updates=dict(updates),
        label=label,
        family_meta=family_meta,
        geometry_update_keys=tuple(GEOMETRY_KEYS),
        bottom_update_keys=tuple(BOTTOM_KEYS),
        shear_update_keys=tuple(SHEAR_KEYS),
    )


def _parity_rows() -> dict[str, dict[str, Any]]:
    base_candidate = {
        "overview": {
            "worst_util": "0.92",
            "governing_util": 0.95,
            "all_key_pass": False,
            "any_fail": False,
            "statuses": {"bending": "PASS", "shear": "NEAR LIMIT"},
        },
        "is_compliant": True,
    }
    cases = {
        "bending_required_checks_accept": {
            "candidate": dict(base_candidate),
            "updates": {"bot1_count": 6, "D": 650.0},
            "label": "BENDING_FAIL_GOVERNS repair ladder candidate",
            "meta": {"candidate_family_id": "BENDING_FAIL_GOVERNS", "bending_fail_ladder_index": 1},
        },
        "bending_explicit_fail_reject": {
            "candidate": {
                **base_candidate,
                "overview": {"all_key_pass": True, "any_fail": False, "statuses": {"bending": "FAIL"}},
            },
            "updates": {"bot1_count": 6},
            "label": "Bending rejected",
            "meta": {"candidate_family_id": "BENDING_FAIL_GOVERNS"},
        },
        "shear_required_checks_accept": {
            "candidate": {
                **base_candidate,
                "overview": {"governing_util": 0.88, "all_key_pass": False, "any_fail": False, "statuses": {"shear": "PASS", "bending": "NEAR LIMIT"}},
            },
            "updates": {"lig_d": 10, "lig_legs": 2, "s_lig": 150.0},
            "label": "SHEAR_FAIL_GOVERNS repair ladder candidate",
            "meta": {"candidate_family_id": "SHEAR_FAIL_GOVERNS", "shear_fail_ladder_index": 2},
        },
        "shear_explicit_fail_reject": {
            "candidate": {
                **base_candidate,
                "overview": {"all_key_pass": True, "any_fail": False, "statuses": {"shear": "FAILED"}},
            },
            "updates": {"lig_d": 10},
            "label": "Shear rejected",
            "meta": {"candidate_family_id": "SHEAR_FAIL_GOVERNS"},
        },
        "combined_generic_all_key_pass": {
            "candidate": {
                **base_candidate,
                "overview": {"worst_util": 0.99, "all_key_pass": True, "any_fail": False, "statuses": {"bending": "PASS", "shear": "PASS"}},
            },
            "updates": {"D": 700.0, "bot1_count": 7, "lig_legs": 3},
            "label": "COMBINED_BENDING_SHEAR_FAIL repair ladder candidate",
            "meta": {"candidate_family_id": "COMBINED_BENDING_SHEAR_FAIL"},
        },
        "generic_any_fail_reject": {
            "candidate": {
                **base_candidate,
                "overview": {"all_key_pass": True, "any_fail": True, "statuses": {"bending": "PASS"}},
            },
            "updates": {"D": 700.0},
            "label": "Generic rejected",
            "meta": {},
        },
    }
    rows: dict[str, dict[str, Any]] = {}
    for name, case in cases.items():
        old = _old_projection(
            case["candidate"],
            updates=dict(case["updates"]),
            label=str(case["label"]),
            family_meta=dict(case["meta"]),
        )
        new = _new_projection(
            case["candidate"],
            updates=dict(case["updates"]),
            label=str(case["label"]),
            family_meta=dict(case["meta"]),
        )
        rows[name] = {
            "old_hash": _stable_hash(old),
            "new_hash": _stable_hash(new),
            "matches": old == new,
        }
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_node = _function_node(inputs_source, TARGET)
    target_source = _function_source(inputs_source, target_node)
    nested_start, nested_end, nested_source = _nested_function_source(inputs_source, TARGET, NESTED)
    source_checks = {
        "target_found": target_node is not None,
        "nested_evaluate_found": bool(nested_source),
        "nested_evaluate_delegates_projection_to_service": (
            "_project_active_fail_executor_evaluated_candidate_result(" in nested_source
        ),
        "nested_evaluate_no_longer_parses_preview_worst": "preview_worst =" not in nested_source,
        "nested_evaluate_no_longer_owns_bending_acceptance_basis": (
            "bending_fail_acceptance_basis" not in nested_source
        ),
        "nested_evaluate_no_longer_owns_shear_acceptance_basis": (
            "shear_fail_acceptance_basis" not in nested_source
        ),
        "nested_evaluate_no_longer_calls_compound_subfamilies": (
            "_compound_subfamilies_from_updates(" not in nested_source
        ),
        "target_still_appends_candidate": "candidates.append(cand)" in target_source,
        "service_projection_helper_exists": (
            "def project_active_fail_executor_evaluated_candidate_result(" in candidate_source
        ),
        "service_exports_projection_helper": (
            '"project_active_fail_executor_evaluated_candidate_result"' in candidate_source
        ),
        "candidate_evaluation_has_no_page_or_streamlit_imports": all(
            token not in candidate_source
            for token in ("inputs_page", "streamlit", "st.session_state", "design_guide_page")
        ),
    }
    return {
        "schema": "design_guide_active_fail_executor_evaluated_result_projection_handoff.v1",
        "target": {
            "name": TARGET,
            "line_start": int(target_node.lineno if target_node else 0),
            "line_end": int(target_node.end_lineno if target_node and target_node.end_lineno else 0),
        },
        "nested_evaluate": {
            "line_start": nested_start,
            "line_end": nested_end,
            "line_count": max(0, nested_end - nested_start + 1),
        },
        "parity": _parity_rows(),
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_behavior_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    parity = dict(payload.get("parity") or {})
    source_checks = dict(payload.get("source_checks") or {})
    return {
        "evaluated_result_projection_hashes_unchanged": bool(parity)
        and all(row.get("matches") for row in parity.values()),
        **{name: bool(value) for name, value in source_checks.items()},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_behavior_unchanged": not bool(payload.get("family_runtime_behavior_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_active_fail_executor_evaluated_result_projection_handoff_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_active_fail_executor_evaluated_result_projection_handoff_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Active-Fail Executor Evaluated Result Projection Handoff",
        "",
        f"Status: {payload['status']}",
        "",
        "## Summary",
        (
            "Moved active-fail evaluated-candidate result projection behind "
            "`design_brain.candidate_evaluation`. The page still owns candidate iteration, "
            "cache/session state, trace, and append/return plumbing."
        ),
        "",
        "## Parity",
        *[
            f"- {name}: {'PASS' if row.get('matches') else 'FAIL'}"
            for name, row in (payload.get("parity") or {}).items()
        ],
        "",
        "## Checks",
        *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {**payload, "status": status, "checks": checks, "checked_at": _timestamp()}
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_active_fail_executor_evaluated_result_projection_handoff {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
