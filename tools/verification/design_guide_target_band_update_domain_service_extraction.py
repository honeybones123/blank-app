"""Verify target-band update diff and domain resolution extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    diff_candidate_state_updates,
    resolve_target_band_candidate_domains_for_updates,
    resolve_target_band_domains_touched_by_updates,
)


APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

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


def _old_diff(base: dict[str, Any] | None, final: dict[str, Any] | None) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    base_d = dict(base or {})
    for key, value in dict(final or {}).items():
        if key not in base_d:
            delta[key] = value
            continue
        base_value = base_d[key]
        if isinstance(value, float) or isinstance(base_value, float):
            try:
                if abs(float(base_value) - float(value)) > 1e-9:
                    delta[key] = value
            except (TypeError, ValueError):
                if base_value != value:
                    delta[key] = value
        elif base_value != value:
            delta[key] = value
    return delta


def _old_domains_touched(updates: dict[str, Any] | None) -> set[str]:
    keys = set(dict(updates or {}).keys())
    touched: set[str] = set()
    if keys & SHEAR_KEYS:
        touched.add("shear")
    if keys & (BOTTOM_KEYS | GEOMETRY_KEYS):
        touched.add("bending")
    return touched


def _old_domains_for_eval(base_domains: Any, updates: dict[str, Any] | None = None) -> list[str]:
    domains = set(base_domains or [])
    domains |= _old_domains_touched(updates)
    return [domain for domain in ("bending", "shear") if domain in domains]


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        (
            "bottom_reduction_touches_bending",
            {"bot1_count": 5, "s_lig": 200.0, "unchanged": "x"},
            {"bot1_count": 4, "s_lig": 200.0, "unchanged": "x"},
            [],
        ),
        (
            "shear_spacing_touches_shear",
            {"bot1_count": 5, "s_lig": 200.0},
            {"bot1_count": 5, "s_lig": 250.0},
            ["bending"],
        ),
        (
            "geometry_and_shear_touch_both",
            {"b": 400.0, "lig_legs": 2},
            {"b": 350.0, "lig_legs": 0},
            [],
        ),
        (
            "new_unknown_key_no_domain",
            {"b": 400.0},
            {"b": 400.0, "comment": "same"},
            [],
        ),
        (
            "float_tolerance_no_update",
            {"D": 650.0},
            {"D": 650.0000000001},
            ["shear"],
        ),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, base, final, base_domains in cases:
        old_updates = _old_diff(base, final)
        new_updates = diff_candidate_state_updates(base, final)
        old_touched = sorted(_old_domains_touched(old_updates))
        new_touched = sorted(resolve_target_band_domains_touched_by_updates(new_updates))
        old_domains = _old_domains_for_eval(base_domains, old_updates)
        new_domains = resolve_target_band_candidate_domains_for_updates(base_domains, new_updates)
        row = {
            "case": name,
            "old_updates": old_updates,
            "new_updates": new_updates,
            "old_touched": old_touched,
            "new_touched": new_touched,
            "old_domains": old_domains,
            "new_domains": new_domains,
            "matches": old_updates == new_updates and old_touched == new_touched and old_domains == new_domains,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def build_payload() -> dict[str, Any]:
    inputs_source = _read(APP_CONTRACT_BRIDGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_segment(inputs_source, "_one_click_best_next_hop_improving_candidate")
    _, _, diff_wrapper = _function_segment(inputs_source, "_one_click_diff_accumulated_updates")
    _, _, domain_wrapper = _function_segment(inputs_source, "_one_click_target_domains_for_eval")
    _, _, attach_helper = _function_segment(inputs_source, "_one_click_attach_eval_target_domains")
    rows, mismatches = _case_rows()
    static_checks = {
        "diff_service_present": "def diff_candidate_state_updates(" in candidate_source,
        "domain_service_present": "def resolve_target_band_candidate_domains_for_updates(" in candidate_source,
        "loop_delegates_to_refinement_service": "_select_best_target_band_refinement_candidate(" in helper,
        "diff_wrapper_delegates": "_diff_candidate_state_updates(base, final)" in diff_wrapper,
        "domain_wrapper_delegates": "_resolve_target_band_candidate_domains_for_updates(base_domains, updates)" in domain_wrapper,
        "page_attachment_retained": "_build_design_actions_context_isolated(" in attach_helper
        and "_shear_demands_negligible(" in attach_helper
        and "_bending_demands_negligible(" in attach_helper,
        "generator_and_evaluator_boundary_retained": all(
            token in helper
            for token in (
                "_build_auto_design_context(",
                "generate_compliant_refinement_candidates(",
                "target_domain_attachment_fn=_one_click_attach_eval_target_domains",
                "evaluator_fn=evaluate_candidate_full",
            )
        ),
    }
    forbidden_service_hits = [
        token
        for token in (
            "one_click",
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    static_checks["forbidden_service_hits"] = forbidden_service_hits
    status = "PASS"
    if mismatches or not all(value is True for key, value in static_checks.items() if key != "forbidden_service_hits") or forbidden_service_hits:
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_update_diff_and_domain_resolution",
        "inputs_segment": {
            "function": "_one_click_best_next_hop_improving_candidate",
            "start_line": start,
            "end_line": end,
        },
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "static_checks": static_checks,
        "ownership": {
            "moved_to_candidate_evaluation": [
                "candidate state update diff",
                "domains touched by candidate updates",
                "target-domain merge from base domains plus update domains",
            ],
            "remains_page_owned": [
                "demand-aware target-domain attachment",
                "auto-design context construction",
                "refinement candidate generation",
                "canonical state pack construction",
                "callback injection for full candidate evaluation",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit demand-aware target-domain attachment or begin generator/evaluator handoff proof",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_update_domain_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_update_domain_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Update/Domain Service Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved candidate update diff and target-domain merge policy into `design_brain.candidate_evaluation`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Parity",
            f"- Cases checked: `{payload['case_count']}`",
            f"- Mismatches: `{len(payload['mismatches'])}`",
            "",
            "## Remaining Page-Owned Logic",
        ]
    )
    for item in payload["ownership"]["remains_page_owned"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
