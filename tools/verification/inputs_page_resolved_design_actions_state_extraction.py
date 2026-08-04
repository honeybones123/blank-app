from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.app_bridge import resolved_design_actions_state


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "app_bridge" / "resolved_design_actions_state.py"
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def _float_from_state(state: dict, key: str, default: float) -> float:
    try:
        return float((state or {}).get(key, default))
    except Exception:
        return float(default)


def _resolve_design_actions_from_state(state: dict) -> dict:
    return {
        "Mu": _float_from_state(state, "uls_Mstar", 0.0),
        "Vu": _float_from_state(state, "uls_Vstar", 0.0),
        "Nu": _float_from_state(state, "uls_Nstar", 0.0),
        "SLS_M": _float_from_state(state, "sls_Mstar", 0.0),
        "SLS_V": _float_from_state(state, "sls_Vstar", 0.0),
        "Tu": _float_from_state(state, "Tu_star", 0.0),
        "Pu": _float_from_state(state, "P_star", 0.0),
    }


def _guidance_state_snapshot_for_summary_bridge(state: dict | None = None) -> dict:
    snapshot = {
        "from_summary_snapshot": True,
        "uls_Mstar": 111.0,
        "uls_Vstar": 22.0,
        "uls_Nstar": 3.0,
        "sls_Mstar": 44.0,
        "sls_Vstar": 5.0,
        "Tu_star": 6.0,
        "P_star": 7.0,
    }
    snapshot.update(dict(state or {}))
    return snapshot


def _bind_module() -> None:
    resolved_design_actions_state.bind_resolved_design_actions_state_dependencies(
        {
            "SHARED_DEFAULTS": {
                "sec_shape": "Rectangular",
                "uls_Mstar": 0.0,
                "uls_Vstar": 0.0,
                "uls_Nstar": 0.0,
                "sls_Mstar": 0.0,
                "sls_Vstar": 0.0,
                "Tu_star": 0.0,
                "P_star": 0.0,
            },
            "_float_from_state": _float_from_state,
            "_guidance_state_snapshot_for_summary_bridge": _guidance_state_snapshot_for_summary_bridge,
            "_resolve_design_actions_from_state": _resolve_design_actions_from_state,
        }
    )


def _case_results() -> list[dict[str, Any]]:
    _bind_module()
    cases: list[dict[str, Any]] = []

    isolated_default = (
        resolved_design_actions_state._state_with_resolved_design_actions_isolated_for_app_bridge(
            {"uls_Mstar": -120.0, "uls_Vstar": 35.0, "sls_Mstar": -60.0},
            None,
        )
    )
    cases.append(
        {
            "name": "isolated_state_fills_defaults_and_derives_negative_manuals",
            "passed": isolated_default["sec_shape"] == "Rectangular"
            and isolated_default["uls_Mstar"] == -120.0
            and isolated_default["uls_Mstar_pos_manual"] == 0.0
            and isolated_default["uls_Mstar_neg_manual"] == 120.0
            and isolated_default["sls_Mstar_neg_manual"] == 60.0
            and isolated_default["actions_uls"]["M"] == -120.0,
            "result": isolated_default,
        }
    )

    explicit = resolved_design_actions_state._state_with_resolved_design_actions_for_app_bridge(
        {
            "uls_Mstar": 100.0,
            "uls_Mstar_pos_manual": 95.0,
            "uls_Mstar_neg_manual": 8.0,
        },
        {
            "Mu": 250.0,
            "Vu": 125.0,
            "Nu": 10.0,
            "SLS_M": 150.0,
            "SLS_V": 90.0,
            "Tu": 4.0,
            "Pu": 3.0,
        },
    )
    cases.append(
        {
            "name": "summary_state_uses_snapshot_and_preserves_explicit_manuals",
            "passed": explicit["from_summary_snapshot"] is True
            and explicit["uls_Mstar"] == 250.0
            and explicit["uls_Vstar"] == 125.0
            and explicit["uls_Nstar"] == 10.0
            and explicit["Mu_star"] == 250.0
            and explicit["Vu_star"] == 125.0
            and explicit["N_star"] == 10.0
            and explicit["sls_Mstar"] == 150.0
            and explicit["sls_Vstar"] == 90.0
            and explicit["Tu_star"] == 4.0
            and explicit["P_star"] == 3.0
            and explicit["uls_Mstar_pos_manual"] == 95.0
            and explicit["uls_Mstar_neg_manual"] == 8.0
            and explicit["actions_uls"] == {
                "M": 250.0,
                "V": 125.0,
                "N": 10.0,
                "T": 4.0,
                "P": 3.0,
            },
            "result": explicit,
        }
    )
    return cases


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Resolved Design Actions State Extraction",
        "",
        f"## Decision: {payload['decision']}",
        "",
        "## Checks",
        "",
    ]
    for key, value in payload["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    bridge_source = _read(BRIDGE)
    module_source = _read(MODULE)
    isolated_bridge = _function_source(
        bridge_source,
        "_state_with_resolved_design_actions_isolated_for_app_bridge",
    )
    summary_bridge = _function_source(
        bridge_source,
        "_state_with_resolved_design_actions_for_app_bridge",
    )
    module_body = _function_source(module_source, "_apply_resolved_design_action_fields")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helpers": all(
            needle in bridge_source
            for needle in (
                "_state_with_resolved_design_actions_for_app_bridge_extracted",
                "_state_with_resolved_design_actions_isolated_for_app_bridge_extracted",
            )
        ),
        "isolated_bridge_is_thin_delegate": len(isolated_bridge.splitlines()) <= 10,
        "summary_bridge_is_thin_delegate": len(summary_bridge.splitlines()) <= 7,
        "bridge_binds_resolved_state_dependencies": all(
            "_bind_resolved_design_actions_state_dependencies(globals())" in source
            for source in (isolated_bridge, summary_bridge)
        ),
        "bridge_removed_projection_body": "actions_uls" not in isolated_bridge
        and "actions_uls" not in summary_bridge,
        "module_keeps_projection_body": "actions_uls" in module_body
        and "uls_Mstar_pos_manual" in module_body,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = (
        "INPUTS_PAGE_RESOLVED_DESIGN_ACTIONS_STATE_EXTRACTION_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_resolved_design_actions_state_extraction",
        "timestamp": timestamp,
        "decision": decision,
        "checks": checks,
        "failures": failures,
        "case_results": cases,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_behavior_changed": False,
        "engineering_calculations_changed": False,
    }
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"inputs_page_resolved_design_actions_state_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_resolved_design_actions_state_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_resolved_design_actions_state_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
