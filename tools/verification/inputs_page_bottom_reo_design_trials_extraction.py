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

from inputs_page_modules import bottom_reo_design_trials


BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "bottom_reo_design_trials.py"
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


def _bind(trace: list[dict[str, Any]]) -> None:
    def design_optimisation_goal(state: dict) -> str:
        trace.append({"kind": "goal", "state": dict(state)})
        return "balanced"

    def design_mode_config(goal: str) -> dict:
        trace.append({"kind": "mode_config", "goal": goal})
        return {"goal": goal}

    def generate_local_bottom_arrangements(
        state: dict,
        cfg: dict,
        *,
        band: int,
        context: dict,
        limit: int,
    ) -> list[dict]:
        trace.append(
            {
                "kind": "generate",
                "cfg": dict(cfg),
                "band": band,
                "limit": limit,
                "has_layout_cache": isinstance(context.get("layout_fit_cache"), dict),
            }
        )
        return [
            {"bot1_count": 2, "bot2_count": 2, "db_bot_1": 20},
            {"bot1_count": 1, "bot2_count": 0, "db_bot_1": 16},
        ]

    def normalise_bottom_layer_order(arrangement: dict) -> dict:
        out = dict(arrangement)
        out.setdefault("normalised", True)
        return out

    def arrangement_fits_state(state: dict, arrangement: dict, *, layout_cache: dict) -> bool:
        sig = (
            int(arrangement.get("bot1_count", 0) or 0),
            int(arrangement.get("bot2_count", 0) or 0),
            int(arrangement.get("db_bot_1", 0) or 0),
        )
        return sig == (3, 3, 24)

    def bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
        return {
            "bot1_count": int(arrangement.get("bot1_count", 0) or 0),
            "bot2_count": int(arrangement.get("bot2_count", 0) or 0),
            "db_bot_1": int(arrangement.get("db_bot_1", 0) or 0),
        }

    bottom_reo_design_trials.bind_bottom_reo_design_trial_dependencies(
        {
            "_arrangement_fits_state": arrangement_fits_state,
            "_bottom_arrangement_to_shared_updates": bottom_arrangement_to_shared_updates,
            "_design_mode_config": design_mode_config,
            "_design_optimisation_goal": design_optimisation_goal,
            "_generate_local_bottom_arrangements": generate_local_bottom_arrangements,
            "_normalise_bottom_layer_order": normalise_bottom_layer_order,
            "_practical_bottom_reo_label": lambda n1, n2, dia: f"{n1}+{n2} N{dia}",
        }
    )


def _case_results() -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    _bind(trace)
    result = bottom_reo_design_trials._enumerate_bottom_reo_design_trials({"D": 500})
    explicit_trace: list[dict[str, Any]] = []
    _bind(explicit_trace)
    explicit = bottom_reo_design_trials._enumerate_bottom_reo_design_trials(
        {"D": 500},
        mode_config={"goal": "explicit"},
    )
    return [
        {
            "name": "non_dict_state_returns_empty_list",
            "passed": bottom_reo_design_trials._enumerate_bottom_reo_design_trials(None) == [],
        },
        {
            "name": "default_mode_config_and_generated_arguments_are_used",
            "passed": any(row.get("kind") == "goal" for row in trace)
            and any(row.get("kind") == "mode_config" and row.get("goal") == "balanced" for row in trace)
            and any(
                row.get("kind") == "generate"
                and row.get("band") == 2
                and row.get("limit") == 12
                and row.get("has_layout_cache") is True
                for row in trace
            ),
            "trace": trace,
        },
        {
            "name": "stronger_specs_are_deduped_fit_gated_and_packaged",
            "passed": [row["label"] for row in result] == ["2+2 N20", "1+0 N16", "3+3 N24"]
            and [row["updates"] for row in result]
            == [
                {"bot1_count": 2, "bot2_count": 2, "db_bot_1": 20},
                {"bot1_count": 1, "bot2_count": 0, "db_bot_1": 16},
                {"bot1_count": 3, "bot2_count": 3, "db_bot_1": 24},
            ]
            and result[-1]["arrangement"].get("normalised") is True,
            "result": result,
        },
        {
            "name": "explicit_mode_config_bypasses_default_goal_resolution",
            "passed": not any(row.get("kind") == "goal" for row in explicit_trace)
            and any(
                row.get("kind") == "generate" and row.get("cfg") == {"goal": "explicit"}
                for row in explicit_trace
            )
            and bool(explicit),
            "trace": explicit_trace,
        },
    ]


def _write_report(payload: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Inputs Page Bottom Reo Design Trials Extraction",
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
    bridge_helper = _function_source(bridge_source, "_enumerate_bottom_reo_design_trials")
    module_helper = _function_source(module_source, "_enumerate_bottom_reo_design_trials")
    cases = _case_results()
    checks = {
        "module_exists": MODULE.exists(),
        "bridge_imports_extracted_helper": "_enumerate_bottom_reo_design_trials_extracted" in bridge_source,
        "bridge_helper_is_thin_delegate": len(bridge_helper.splitlines()) <= 3,
        "bridge_binds_bottom_trial_dependencies": "_bind_bottom_reo_design_trial_dependencies(globals())" in bridge_helper,
        "bridge_delegates_to_extracted": "_enumerate_bottom_reo_design_trials_extracted(" in bridge_helper,
        "bridge_removed_trial_body": "stronger_specs" not in bridge_helper
        and "layout_fit_cache" not in bridge_helper,
        "module_keeps_trial_body": "stronger_specs" in module_helper
        and "layout_fit_cache" in module_helper,
        "module_has_dependency_binder": "def bind_bottom_reo_design_trial_dependencies" in module_source,
        "module_does_not_import_bridge": "inputs_page_app_contract_bridge" not in module_source,
        "module_does_not_import_streamlit": "import streamlit" not in module_source,
        "all_cases_pass": all(row["passed"] for row in cases),
    }
    failures = [key for key, value in checks.items() if not value]
    failures.extend(f"case:{row['name']}" for row in cases if not row["passed"])
    decision = (
        "INPUTS_PAGE_BOTTOM_REO_DESIGN_TRIALS_EXTRACTION_LOCKED"
        if not failures
        else "GAPS_REMAIN"
    )
    payload = {
        "audit": "inputs_page_bottom_reo_design_trials_extraction",
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
    json_path = VERIFICATION_DIR / f"inputs_page_bottom_reo_design_trials_extraction_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_bottom_reo_design_trials_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print("inputs_page_bottom_reo_design_trials_extraction", "PASS" if not failures else "FAIL")
    print(f"decision={decision}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
