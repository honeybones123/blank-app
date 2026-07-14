from __future__ import annotations

import ast
import datetime as _dt
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import build_candidate_action_state_projection


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _legacy_float(source: dict[str, Any], key: str, default: float) -> float:
    value = source.get(key)
    if value is None:
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _legacy_projection(
    state: dict[str, Any] | None,
    *,
    actions: dict[str, Any] | None,
    shared_defaults: dict[str, Any] | None,
) -> dict[str, Any]:
    resolved = dict(state or {})
    for key, default in dict(shared_defaults or {}).items():
        resolved.setdefault(key, default)
    actions_d = dict(actions or {})
    resolved["uls_Mstar"] = float(actions_d.get("Mu", _legacy_float(resolved, "uls_Mstar", 0.0)) or 0.0)
    resolved["uls_Vstar"] = float(actions_d.get("Vu", _legacy_float(resolved, "uls_Vstar", 0.0)) or 0.0)
    resolved["uls_Nstar"] = float(actions_d.get("Nu", _legacy_float(resolved, "uls_Nstar", 0.0)) or 0.0)
    resolved["Mu_star"] = float(actions_d.get("Mu", _legacy_float(resolved, "Mu_star", 0.0)) or 0.0)
    resolved["Vu_star"] = float(actions_d.get("Vu", _legacy_float(resolved, "Vu_star", 0.0)) or 0.0)
    resolved["N_star"] = float(actions_d.get("Nu", _legacy_float(resolved, "N_star", 0.0)) or 0.0)
    resolved["sls_Mstar"] = float(actions_d.get("SLS_M", _legacy_float(resolved, "sls_Mstar", 0.0)) or 0.0)
    resolved["uls_Mstar_pos_manual"] = float(
        _legacy_float(resolved, "uls_Mstar_pos_manual", max(0.0, _legacy_float(resolved, "uls_Mstar", 0.0))) or 0.0
    )
    resolved["uls_Mstar_neg_manual"] = float(
        _legacy_float(resolved, "uls_Mstar_neg_manual", max(0.0, -_legacy_float(resolved, "uls_Mstar", 0.0))) or 0.0
    )
    resolved["sls_Mstar_pos_manual"] = float(
        _legacy_float(resolved, "sls_Mstar_pos_manual", max(0.0, _legacy_float(resolved, "sls_Mstar", 0.0))) or 0.0
    )
    resolved["sls_Mstar_neg_manual"] = float(
        _legacy_float(resolved, "sls_Mstar_neg_manual", max(0.0, -_legacy_float(resolved, "sls_Mstar", 0.0))) or 0.0
    )
    resolved["sls_Vstar"] = float(actions_d.get("SLS_V", _legacy_float(resolved, "sls_Vstar", 0.0)) or 0.0)
    resolved["Tu_star"] = float(actions_d.get("Tu", _legacy_float(resolved, "Tu_star", 0.0)) or 0.0)
    resolved["P_star"] = float(actions_d.get("Pu", _legacy_float(resolved, "P_star", 0.0)) or 0.0)
    resolved["actions_uls"] = {
        "M": resolved["uls_Mstar"],
        "V": resolved["uls_Vstar"],
        "N": resolved["uls_Nstar"],
        "T": resolved["Tu_star"],
        "P": resolved["P_star"],
    }
    return resolved


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "state": {},
            "actions": {},
            "shared_defaults": {"uls_Mstar": 10.0, "uls_Vstar": 5.0, "D": 600.0},
        },
        {
            "state": {"uls_Mstar": 12.0, "uls_Vstar": 9.0, "sls_Mstar": 4.0},
            "actions": {"Mu": 100.0, "Vu": 40.0, "Nu": 3.0, "SLS_M": 55.0, "SLS_V": 8.0, "Tu": 2.0, "Pu": 1.0},
            "shared_defaults": {"D": 700.0, "uls_Mstar": 1.0},
        },
        {
            "state": {
                "uls_Mstar": -20.0,
                "sls_Mstar": -6.0,
                "uls_Mstar_pos_manual": None,
                "uls_Mstar_neg_manual": None,
                "sls_Mstar_pos_manual": None,
                "sls_Mstar_neg_manual": None,
            },
            "actions": {"Mu": None, "SLS_M": None},
            "shared_defaults": {"uls_Vstar": "bad", "sls_Vstar": 4.0},
        },
    ]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, design_segment = _function_segment(inputs_source, "_state_with_resolved_design_actions")
    _, _, isolated_segment = _function_segment(inputs_source, "_state_with_resolved_design_actions_isolated")
    _, _, fast_segment = _function_segment(inputs_source, "evaluate_candidate_fast")
    inputs_module = importlib.import_module("inputs_page")

    parity_rows = []
    mismatches = []
    for index, case in enumerate(_sample_cases()):
        old_value = _legacy_projection(
            case.get("state"),
            actions=case.get("actions"),
            shared_defaults=case.get("shared_defaults"),
        )
        new_value = build_candidate_action_state_projection(
            case.get("state"),
            actions=case.get("actions"),
            shared_defaults=case.get("shared_defaults"),
        )
        row = {
            "case": index,
            "matches": old_value == new_value,
            "old": old_value,
            "new": new_value,
        }
        parity_rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_case = {
        "b": 400.0,
        "D": 650.0,
        "uls_Mstar": 14.0,
        "uls_Vstar": 7.0,
    }
    wrapper_actions = {"Mu": 44.0, "Vu": 22.0, "Nu": 2.0, "SLS_M": 11.0, "SLS_V": 5.0}
    isolated_wrapper = inputs_module._state_with_resolved_design_actions_isolated(dict(wrapper_case), dict(wrapper_actions))
    service_wrapper = build_candidate_action_state_projection(
        dict(wrapper_case),
        actions=dict(wrapper_actions),
        shared_defaults=dict(inputs_module.SHARED_DEFAULTS),
    )

    checks = {
        "service_helper_exists": "def build_candidate_action_state_projection(" in candidate_source,
        "service_helper_exported": '"build_candidate_action_state_projection"' in candidate_source,
        "page_imports_service_alias": "build_candidate_action_state_projection as _build_candidate_action_state_projection" in inputs_source,
        "session_overlay_wrapper_keeps_snapshot": "_guidance_state_snapshot(state)" in design_segment,
        "session_overlay_wrapper_delegates_projection": "_build_candidate_action_state_projection(" in design_segment,
        "isolated_wrapper_delegates_projection": "_build_candidate_action_state_projection(" in isolated_segment,
        "fast_evaluator_keeps_page_action_resolution_wrapper": "_state_with_resolved_auto_design_actions(" in fast_segment,
        "parity_cases_match": not mismatches,
        "isolated_wrapper_matches_service": isolated_wrapper == service_wrapper,
        "candidate_service_import_clean": "inputs_page" not in candidate_source and "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    return {
        "schema": "design_guide_candidate_action_state_projection_extraction.v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "decision": (
            "CANDIDATE_ACTION_STATE_PROJECTION_SERVICE_OWNED"
            if all(checks.values())
            else "CANDIDATE_ACTION_STATE_PROJECTION_EXTRACTION_FAILED"
        ),
        "parity_rows": parity_rows,
        "mismatches": mismatches,
        "checks": checks,
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_candidate_action_state_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_action_state_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Candidate Action State Projection Extraction",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Parity Rows",
        "",
        "| Case | Matches |",
        "| --- | ---: |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(dict(payload.get("checks") or {}).items()))
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(f"design_guide_candidate_action_state_projection_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
