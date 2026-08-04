from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.calculations import (  # noqa: E402
    InputsCalculationExplainerSourceSnapshot,
    build_inputs_calculation_explainer_view_model,
    stable_calculation_explainer_hash,
)
from inputs_page_modules.calculations.contracts import (  # noqa: E402
    CALCULATION_EXPLAINER_CARD_ORDER,
    CALCULATION_EXPLAINER_CARD_TITLES,
    CALCULATION_EXPLAINER_ROUTE_PAGES,
)


SCENARIOS: dict[str, dict[str, tuple[dict[str, Any], ...]]] = {
    "all_pass": {
        "bending": (
            {"uid": "bend_capacity", "title": "Positive bending", "capacity": "phiM_u = 240.0 kNm", "action": "M* = 180.0 kNm", "util": "0.75", "status": "PASS", "tab": "1.1"},
            {"uid": "bend_ku", "title": "Neutral axis ratio", "value": "k_u = 0.22", "limit": "k_u,lim = 0.36", "util": "0.61", "status": "PASS", "tab": "1.6"},
        ),
        "shear": (
            {"uid": "shear_capacity", "title": "Shear capacity", "capacity": "phiVu = 300.0 kN", "action": "V*eq = 120.0 kN", "util": "0.40", "status": "PASS", "tab": "2.1"},
        ),
        "crack": (
            {"uid": "crk_step_3", "title": "Direct crack width check", "value": "w = 0.120 mm", "limit": "w'max = 0.300 mm", "util": "0.40", "status": "PASS"},
        ),
        "deflection": (
            {"uid": "defl_total", "title": "Total deflection", "calculated": "delta_total = 5.20 mm", "requirement": "delta_lim = 8.00 mm", "util": "0.65", "status": "PASS"},
        ),
    },
    "bending_fail": {
        "bending": (
            {"uid": "bend_capacity", "title": "Positive bending", "capacity": "phiM_u = 246.5 kNm", "action": "M* = 300.0 kNm", "util": "1.22", "status": "FAIL", "tab": "1.1"},
        ),
        "shear": (
            {"uid": "shear_capacity", "title": "Shear capacity", "capacity": "phiVu = 670.4 kN", "action": "Not supplied", "util": "", "status": "CAPACITY"},
        ),
        "crack": (),
        "deflection": (),
    },
    "shear_fail_deflection_not_run": {
        "bending": (
            {"uid": "bend_capacity", "title": "Positive bending", "capacity": "phiM_u = 221.5 kNm", "action": "M* = 200.0 kNm", "util": "0.90", "status": "NEAR LIMIT"},
        ),
        "shear": (
            {"uid": "shear_capacity", "title": "Shear capacity", "capacity": "phiVu = 80.3 kN", "action": "V*eq = 100.0 kN", "util": "1.25", "status": "FAIL"},
            {"uid": "shear_spacing", "title": "Link spacing", "value": "s = 250 mm", "limit": "smax = 300 mm", "util": "0.83", "status": "PASS"},
        ),
        "crack": (
            {"uid": "crk_not_run", "title": "Crack control", "value": "Not supplied", "limit": "w'max = 0.300 mm", "util": "", "status": "CAPACITY", "is_informational": True},
        ),
        "deflection": (
            {"uid": "defl_not_run", "title": "Deflection", "calculated": "delta_total = 0.00 mm", "requirement": "delta_lim = 8.00 mm", "util": "", "status": "NOT RUN", "is_informational": True},
        ),
    },
}


def _old_row_projection(row: dict[str, Any], route_page: str) -> dict[str, Any]:
    calculated = row.get("calculated") or row.get("capacity") or row.get("value") or ""
    requirement = row.get("requirement") or row.get("limit") or row.get("action") or ""
    payload = {
        "uid": str(row.get("uid") or row.get("id") or ""),
        "title": str(row.get("title") or row.get("label") or ""),
        "calculated": str(calculated),
        "requirement": str(requirement),
        "utilisation": str(row.get("util") or row.get("utilisation") or ""),
        "status": str(row.get("status") or ""),
        "route_page": str(row.get("route_page") or route_page),
        "tab": str(row.get("tab") or ""),
        "is_informational": bool(row.get("is_informational")),
    }
    payload["display_hash"] = stable_calculation_explainer_hash({k: v for k, v in payload.items() if k != "display_hash"})
    return payload


def _old_card_status(rows: tuple[dict[str, Any], ...]) -> str:
    statuses = [str(row.get("status") or "").strip().upper() for row in rows if str(row.get("status") or "").strip()]
    if any(status in {"FAIL", "NG"} for status in statuses):
        return "FAIL"
    if any(status in {"NEAR LIMIT", "WARN", "CHECK"} for status in statuses):
        return "NEAR LIMIT"
    if any(status == "PASS" for status in statuses):
        return "PASS"
    if any(status in {"NOT RUN", "CAPACITY", "INFO"} for status in statuses):
        return statuses[0]
    return ""


def _old_section_projection(scenario: dict[str, tuple[dict[str, Any], ...]]) -> dict[str, Any]:
    cards = []
    for check_id in CALCULATION_EXPLAINER_CARD_ORDER:
        route = CALCULATION_EXPLAINER_ROUTE_PAGES[check_id]
        rows = tuple(dict(row) for row in scenario.get(check_id) or ())
        row_models = tuple(_old_row_projection(row, route) for row in rows)
        card_payload = {
            "check_id": check_id,
            "title": CALCULATION_EXPLAINER_CARD_TITLES[check_id],
            "status": _old_card_status(rows),
            "route_page": route,
            "rows": tuple(row["display_hash"] for row in row_models),
        }
        cards.append(
            {
                **card_payload,
                "row_models": row_models,
                "display_hash": stable_calculation_explainer_hash(card_payload),
            }
        )
    return {
        "cards": tuple(cards),
        "display_hash": stable_calculation_explainer_hash(
            {
                "cards": tuple(card["display_hash"] for card in cards),
                "order": CALCULATION_EXPLAINER_CARD_ORDER,
                "run_state": {},
            }
        ),
    }


def _new_source(scenario: dict[str, tuple[dict[str, Any], ...]]) -> InputsCalculationExplainerSourceSnapshot:
    return InputsCalculationExplainerSourceSnapshot(
        bending_rows=tuple(dict(row) for row in scenario.get("bending") or ()),
        shear_rows=tuple(dict(row) for row in scenario.get("shear") or ()),
        crack_rows=tuple(dict(row) for row in scenario.get("crack") or ()),
        deflection_rows=tuple(dict(row) for row in scenario.get("deflection") or ()),
        run_state={},
    )


def _new_projection(source: InputsCalculationExplainerSourceSnapshot) -> dict[str, Any]:
    view_model = build_inputs_calculation_explainer_view_model(source)
    return {
        "cards": tuple(
            {
                "check_id": card.check_id,
                "title": card.title,
                "status": card.status,
                "route_page": card.route_page,
                "rows": tuple(row.display_hash for row in card.rows),
                "row_models": tuple(
                    {
                        "uid": row.uid,
                        "title": row.title,
                        "calculated": row.calculated,
                        "requirement": row.requirement,
                        "utilisation": row.utilisation,
                        "status": row.status,
                        "route_page": row.route_page,
                        "tab": row.tab,
                        "is_informational": row.is_informational,
                        "display_hash": row.display_hash,
                    }
                    for row in card.rows
                ),
                "display_hash": card.display_hash,
            }
            for card in view_model.cards
        ),
        "display_hash": view_model.display_hash,
    }


def _scenario_result(name: str, scenario: dict[str, tuple[dict[str, Any], ...]]) -> dict[str, Any]:
    old = _old_section_projection(scenario)
    new = _new_projection(_new_source(scenario))
    mismatches: list[dict[str, Any]] = []
    if old["display_hash"] != new["display_hash"]:
        mismatches.append({"field": "display_hash", "old": old["display_hash"], "new": new["display_hash"]})
    if len(old["cards"]) != len(new["cards"]):
        mismatches.append({"field": "card_count", "old": len(old["cards"]), "new": len(new["cards"])})
    for old_card, new_card in zip(old["cards"], new["cards"]):
        for field in ("check_id", "title", "status", "route_page", "display_hash", "rows"):
            if old_card[field] != new_card[field]:
                mismatches.append(
                    {
                        "card": old_card.get("check_id"),
                        "field": field,
                        "old": old_card[field],
                        "new": new_card[field],
                    }
                )
        for old_row, new_row in zip(old_card["row_models"], new_card["row_models"]):
            for field in ("uid", "title", "calculated", "requirement", "utilisation", "status", "route_page", "tab", "is_informational", "display_hash"):
                if old_row[field] != new_row[field]:
                    mismatches.append(
                        {
                            "card": old_card.get("check_id"),
                            "row": old_row.get("uid"),
                            "field": field,
                            "old": old_row[field],
                            "new": new_row[field],
                        }
                    )
    return {
        "scenario": name,
        "old_hash": old["display_hash"],
        "new_hash": new["display_hash"],
        "match": not mismatches,
        "mismatches": mismatches,
    }


def _module_source_checks() -> dict[str, Any]:
    module_root = ROOT / "inputs_page_modules" / "calculations"
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in module_root.glob("*.py")
    }
    combined = "\n".join(sources.values())
    imports: list[str] = []
    for source in sources.values():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
    return {
        "module_files": sorted(sources),
        "imports_streamlit": any(imported == "streamlit" or imported.startswith("streamlit.") for imported in imports),
        "imports_inputs_page": any(imported == "inputs_page" or imported.startswith("inputs_page.") for imported in imports),
        "imports_solver_modules": any(
            imported in {
                "run_shear_calc",
                "calc_deflection_as3600",
                "calc_eps_diff",
                "build_bending_check_rows_from_state",
            }
            for imported in imports
        ),
    }


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Calculations & Explainers View-Model Parity Snapshot",
        "",
        f"## Executive Summary: {payload['decision']}",
        "",
        "This is trace-only. The live Inputs page renderer was not switched.",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Match | Old hash | New hash | Mismatches |",
        "|---|---:|---|---|---:|",
    ]
    for row in payload["scenarios"]:
        lines.append(
            f"| {row['scenario']} | {row['match']} | `{row['old_hash']}` | `{row['new_hash']}` | {len(row['mismatches'])} |"
        )
    lines.extend(
        [
            "",
            "## Module Ownership Checks",
            "",
            f"- imports Streamlit: `{payload['module_checks']['imports_streamlit']}`",
            f"- imports inputs_page: `{payload['module_checks']['imports_inputs_page']}`",
            f"- imports solver modules/functions directly: `{payload['module_checks']['imports_solver_modules']}`",
            "",
            "## Next Safe Slice",
            "",
            "Wire this builder trace-only beside the live calculation/explainer path in `inputs_page.py`, then rerun parity with real live rows before delegation.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = [_scenario_result(name, scenario) for name, scenario in SCENARIOS.items()]
    module_checks = _module_source_checks()
    failures = [row for row in scenarios if not row["match"]]
    ownership_failure = (
        module_checks["imports_streamlit"]
        or module_checks["imports_inputs_page"]
        or module_checks["imports_solver_modules"]
    )
    decision = (
        "CALCULATION_PARITY_GAPS_REMAIN"
        if failures or ownership_failure
        else "READY_FOR_CALCULATION_TRACE_INTEGRATION"
    )
    payload: dict[str, Any] = {
        "audit": "inputs_calculations_view_model_parity_snapshot",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "live_renderer_switched": False,
        "scenarios": scenarios,
        "module_checks": module_checks,
    }
    json_path = VERIFICATION_DIR / f"inputs_calculations_view_model_parity_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_calculations_view_model_parity_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_calculations_view_model_parity_snapshot PASS")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if decision == "READY_FOR_CALCULATION_TRACE_INTEGRATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
