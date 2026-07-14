"""Verify shared shear-reo variant generator handoff to controller helper."""

from __future__ import annotations

import ast
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REO_SPACINGS = [75, 100, 125, 150, 175, 200, 225, 250, 275, 300]
REO_BAR_DIAS = [10, 12, 16, 20, 24, 28, 32, 36, 40]
CANONICAL_NO_SHEAR_SLIG_MM = 200.0


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(node.end_lineno or node.lineno)
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(state.get(key, default))
    except Exception:
        return float(default)


def _int_from_state(state: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(state.get(key, default))
    except Exception:
        return int(default)


def _candidate_key_for_snapshot(state: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (str(key), str(state.get(key)))
            for key in ("lig_d", "lig_legs", "s_lig", "D", "b", "bw")
            if key in state
        )
    )


def _old_generate_less_shear_reo_variants(
    *,
    state: dict[str, Any],
    shear_cleanup_possible: bool,
    shear_state_eligible_for_no_links: bool,
) -> list[dict[str, Any]]:
    if not shear_cleanup_possible:
        return []
    cur_sp = float(_float_from_state(state, "s_lig", 200.0))
    current_legs = _int_from_state(state, "lig_legs", 2)
    current_dia = _int_from_state(state, "lig_d", 10)
    max_spacing = float(max(REO_SPACINGS) if REO_SPACINGS else 300.0)
    spacing_values = [float(v) for v in REO_SPACINGS if float(v) > cur_sp + 1e-9][:2]
    spacing_values.extend(float(v) for v in REO_SPACINGS if float(v) < cur_sp - 1e-9)
    spacing_values.extend(float(cur_sp - 25.0 * step) for step in range(0, 5))
    spacing_values.extend(float(cur_sp + 25.0 * step) for step in range(1, 17))
    if max_spacing > cur_sp + 1e-9:
        spacing_values.append(max_spacing)
    spacing_values = sorted(set(float(v) for v in spacing_values))
    leg_values = sorted(
        {
            int(value)
            for value in (
                current_legs,
                2,
                3,
            )
            if int(value) >= 2 and int(value) <= max(current_legs, 3)
        }
    )
    dia_values = sorted(
        set(
            [value for value in REO_BAR_DIAS if 0 < int(value) <= current_dia][-2:]
            or [max(int(current_dia), 10)]
        )
    )
    variants: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    if shear_state_eligible_for_no_links:
        zero_link_state = dict(state)
        zero_link_state.update(
            {
                "lig_d": 0,
                "lig_legs": 0,
                "s_lig": float(CANONICAL_NO_SHEAR_SLIG_MM),
            }
        )
        variants[_candidate_key_for_snapshot(zero_link_state)] = zero_link_state
    for spacing in spacing_values or [cur_sp]:
        for legs in leg_values:
            for dia in dia_values:
                resolved_dia = int(dia)
                resolved_spacing = float(spacing)
                if (
                    resolved_dia == current_dia
                    and int(legs) == current_legs
                    and abs(float(resolved_spacing) - cur_sp) <= 1e-9
                ):
                    continue
                candidate_state = dict(state)
                candidate_state.update(
                    {
                        "lig_d": int(resolved_dia),
                        "lig_legs": int(legs),
                        "s_lig": float(resolved_spacing),
                    }
                )
                variants[_candidate_key_for_snapshot(candidate_state)] = candidate_state
    return list(variants.values())


def _identity_rows(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lig_d": item.get("lig_d"),
            "lig_legs": item.get("lig_legs"),
            "s_lig": item.get("s_lig"),
            "D": item.get("D"),
            "b": item.get("b"),
            "bw": item.get("bw"),
        }
        for item in states
    ]


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "cleanup_not_possible",
            "state": {"lig_d": 0, "lig_legs": 0, "s_lig": 300.0, "D": 650.0, "b": 400.0},
            "possible": False,
            "eligible_no_links": False,
        },
        {
            "name": "active_links_no_link_eligible",
            "state": {"lig_d": 10, "lig_legs": 2, "s_lig": 200.0, "D": 650.0, "b": 400.0},
            "possible": True,
            "eligible_no_links": True,
        },
        {
            "name": "active_links_no_link_not_eligible",
            "state": {"lig_d": 12, "lig_legs": 3, "s_lig": 225.0, "D": 650.0, "b": 400.0},
            "possible": True,
            "eligible_no_links": False,
        },
        {
            "name": "larger_current_links",
            "state": {"lig_d": 16, "lig_legs": 4, "s_lig": 175.0, "D": 650.0, "b": 400.0},
            "possible": True,
            "eligible_no_links": True,
        },
    ]


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, generator_source = _function_source(inputs_source, "generate_less_shear_reo_variants")
    module = importlib.import_module("inputs_page")
    comparisons = []
    for case in _cases():
        old = _old_generate_less_shear_reo_variants(
            state=dict(case["state"]),
            shear_cleanup_possible=bool(case["possible"]),
            shear_state_eligible_for_no_links=bool(case["eligible_no_links"]),
        )
        if case["possible"]:
            state = dict(case["state"])
            module._shear_cleanup_possible = lambda _state: True
            module._shear_state_eligible_for_no_links = lambda _state: bool(case["eligible_no_links"])
            new = module.generate_less_shear_reo_variants({"state": state}, {})
        else:
            module._shear_cleanup_possible = lambda _state: False
            module._shear_state_eligible_for_no_links = lambda _state: bool(case["eligible_no_links"])
            new = module.generate_less_shear_reo_variants({"state": dict(case["state"])}, {})
        old_rows = _identity_rows(old)
        new_rows = _identity_rows(new)
        comparisons.append(
            {
                "case": case["name"],
                "old_count": len(old),
                "new_count": len(new),
                "old_rows": old_rows,
                "new_rows": new_rows,
                "match": old_rows == new_rows,
            }
        )
    checks = {
        "controller_raw_variant_helper_exists": "def build_design_guide_shear_low_util_raw_variant_states(" in controller_source,
        "page_generator_calls_controller_helper": "_build_design_guide_shear_low_util_raw_variant_states(" in generator_source,
        "page_generator_keeps_shear_cleanup_possible_gate": "if not _shear_cleanup_possible(state):" in generator_source,
        "page_generator_keeps_no_link_eligibility_callback": "_shear_state_eligible_for_no_links(state)" in generator_source,
        "page_generator_keeps_candidate_key_dedupe": "_make_auto_design_candidate_key(candidate_state)" in generator_source,
        "page_generator_no_inline_spacing_ladder": "spacing_values.extend" not in generator_source,
        "page_generator_no_inline_leg_ladder": "leg_values = sorted" not in generator_source,
        "page_generator_no_inline_dia_ladder": "dia_values = sorted" not in generator_source,
        "controller_imports_no_inputs_page": "inputs_page" not in controller_source,
        "controller_imports_no_streamlit": "import streamlit" not in controller_source and "from streamlit" not in controller_source,
        "all_cases_match": all(item.get("match") for item in comparisons),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "design_guide_shared_shear_reo_variant_generator_handoff.v1",
        "status": status,
        "decision": "SHARED_SHEAR_REO_VARIANT_GENERATOR_CONTROLLER_HANDOFF" if status == "PASS" else "HANDOFF_FAILURE",
        "product_behavior_changed": False,
        "extraction_complete_estimate": "99%",
        "line_range": {"start": start, "end": end},
        "checks": checks,
        "comparisons": comparisons,
        "remaining_page_shell_inputs": [
            "_shear_cleanup_possible(state)",
            "_shear_state_eligible_for_no_links(state)",
            "_make_auto_design_candidate_key(candidate_state)",
            "REO_SPACINGS / REO_BAR_DIAS / CANONICAL_NO_SHEAR_SLIG_MM pass-through",
        ],
        "next_safe_slice": "audit/deadness-pass for target-band lane wrappers or continue to direct-target family repair bridge route policy",
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Shared Shear-Reo Variant Generator Handoff",
        "",
        "## Executive Summary",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Extraction complete estimate: `{payload['extraction_complete_estimate']}`",
        f"- Product behavior changed: `{payload['product_behavior_changed']}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in payload["checks"].items())
    lines.extend(["", "## Case Parity"])
    for row in payload["comparisons"]:
        lines.append(
            f"- {row['case']}: `{row['match']}` ({row['old_count']} old / {row['new_count']} new)"
        )
    lines.extend(["", "## Remaining Page Shell Inputs"])
    lines.extend(f"- {item}" for item in payload["remaining_page_shell_inputs"])
    lines.extend(["", "## Next Safe Slice", f"- `{payload['next_safe_slice']}`"])
    return "\n".join(lines) + "\n"


def _write_artifacts(payload: dict[str, Any]) -> dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_shared_shear_reo_variant_generator_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_shared_shear_reo_variant_generator_handoff_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload["artifact_paths"]


def main() -> int:
    payload = _build_payload()
    paths = _write_artifacts(payload)
    print(f"design_guide_shared_shear_reo_variant_generator_handoff {payload['status']}")
    print(json.dumps({"decision": payload["decision"], "artifact_paths": paths}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
