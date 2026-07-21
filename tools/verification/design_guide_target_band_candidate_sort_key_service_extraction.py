"""Verify target-band candidate sort-key service extraction."""

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

from design_brain.candidate_evaluation import resolve_target_band_candidate_sort_key  # noqa: E402


AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _old_sort_key(
    *,
    tier: int,
    mixed_sort_prefix: tuple[Any, ...] = (),
    tightening_mode_active: bool,
    governing_domain: str,
    has_target_domains: bool,
    new_max: Any = None,
    new_total: Any = None,
    required_fail_count: int = 0,
    required_unsatisfied_count: int = 0,
    prefer_total_before_max: bool = False,
    shear_sort_util: Any = float("inf"),
    web_sort_util: Any = float("inf"),
    practical_spacing_penalty: int = 0,
    congestion_penalty: int = 0,
    goal_bias: int = 0,
    new_distance: Any = float("inf"),
    wrong_dir_penalty: Any = 0.0,
    directional_tie_key: Any = 0.0,
    reduction_bias: int = 0,
    update_count: int = 0,
) -> tuple[Any, ...]:
    prefix = tuple(mixed_sort_prefix or ())
    if tightening_mode_active:
        if governing_domain == "shear":
            if has_target_domains and new_total is not None:
                return (
                    tier,
                    *prefix,
                    required_fail_count,
                    required_unsatisfied_count,
                    float(new_max),
                    float(new_total),
                    shear_sort_util,
                    web_sort_util,
                    practical_spacing_penalty,
                    congestion_penalty,
                    goal_bias,
                    wrong_dir_penalty,
                    reduction_bias,
                    update_count,
                )
            return (
                tier,
                *prefix,
                shear_sort_util,
                web_sort_util,
                practical_spacing_penalty,
                congestion_penalty,
                goal_bias,
                new_distance,
                wrong_dir_penalty,
                reduction_bias,
                update_count,
            )
        if has_target_domains and new_total is not None:
            if prefer_total_before_max:
                return (
                    tier,
                    *prefix,
                    required_fail_count,
                    required_unsatisfied_count,
                    float(new_total),
                    float(new_max),
                    wrong_dir_penalty,
                    reduction_bias,
                    update_count,
                )
            return (
                tier,
                *prefix,
                required_fail_count,
                required_unsatisfied_count,
                float(new_max),
                float(new_total),
                wrong_dir_penalty,
                reduction_bias,
                update_count,
            )
        return (
            tier,
            *prefix,
            new_distance,
            wrong_dir_penalty,
            reduction_bias,
            update_count,
        )

    if has_target_domains and new_max is not None and new_total is not None:
        if prefer_total_before_max:
            return (
                tier,
                *prefix,
                required_fail_count,
                required_unsatisfied_count,
                float(new_total),
                float(new_max),
                directional_tie_key,
                update_count,
            )
        return (
            tier,
            *prefix,
            required_fail_count,
            required_unsatisfied_count,
            float(new_max),
            float(new_total),
            directional_tie_key,
            update_count,
        )
    return (
        tier,
        *prefix,
        new_distance,
        directional_tie_key,
        update_count,
    )


def _new_sort_key(**kwargs: Any) -> tuple[Any, ...]:
    return resolve_target_band_candidate_sort_key(**kwargs)


def build_payload() -> dict[str, Any]:
    inputs_source = _read(AUTO_DESIGN_COMPUTE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_loop = _function_segment(inputs_source, "_solve_one_click_to_target")

    cases = [
        {
            "case": "tightening_shear_target_domains",
            "tier": 0,
            "mixed_sort_prefix": (),
            "tightening_mode_active": True,
            "governing_domain": "shear",
            "has_target_domains": True,
            "new_max": 0.05,
            "new_total": 0.12,
            "required_fail_count": 0,
            "required_unsatisfied_count": 1,
            "shear_sort_util": 0.82,
            "web_sort_util": 0.31,
            "practical_spacing_penalty": 0,
            "congestion_penalty": 1,
            "goal_bias": 0,
            "wrong_dir_penalty": 0.0,
            "reduction_bias": 1,
            "update_count": 2,
        },
        {
            "case": "tightening_shear_no_target_domains",
            "tier": 1,
            "mixed_sort_prefix": (),
            "tightening_mode_active": True,
            "governing_domain": "shear",
            "has_target_domains": False,
            "new_distance": 0.18,
            "shear_sort_util": 0.91,
            "web_sort_util": 0.7,
            "practical_spacing_penalty": 1,
            "congestion_penalty": 0,
            "goal_bias": 1,
            "wrong_dir_penalty": 0.04,
            "reduction_bias": 0,
            "update_count": 1,
        },
        {
            "case": "tightening_non_shear_prefer_total",
            "tier": 0,
            "mixed_sort_prefix": (),
            "tightening_mode_active": True,
            "governing_domain": "bending",
            "has_target_domains": True,
            "new_max": 0.04,
            "new_total": 0.09,
            "required_fail_count": 0,
            "required_unsatisfied_count": 2,
            "prefer_total_before_max": True,
            "wrong_dir_penalty": 0.01,
            "reduction_bias": 0,
            "update_count": 3,
        },
        {
            "case": "tightening_non_shear_prefer_max",
            "tier": 0,
            "mixed_sort_prefix": (),
            "tightening_mode_active": True,
            "governing_domain": "bending",
            "has_target_domains": True,
            "new_max": 0.04,
            "new_total": 0.09,
            "required_fail_count": 1,
            "required_unsatisfied_count": 3,
            "prefer_total_before_max": False,
            "wrong_dir_penalty": 0.02,
            "reduction_bias": 1,
            "update_count": 2,
        },
        {
            "case": "tightening_non_shear_no_target_domains",
            "tier": 2,
            "mixed_sort_prefix": (),
            "tightening_mode_active": True,
            "governing_domain": "bending",
            "has_target_domains": False,
            "new_distance": 0.22,
            "wrong_dir_penalty": 0.03,
            "reduction_bias": 1,
            "update_count": 1,
        },
        {
            "case": "not_tightening_target_domains_prefer_total",
            "tier": 0,
            "mixed_sort_prefix": (),
            "tightening_mode_active": False,
            "governing_domain": "combined",
            "has_target_domains": True,
            "new_max": 0.02,
            "new_total": 0.08,
            "required_fail_count": 0,
            "required_unsatisfied_count": 1,
            "prefer_total_before_max": True,
            "directional_tie_key": 0.11,
            "update_count": 4,
        },
        {
            "case": "not_tightening_target_domains_prefer_max",
            "tier": 0,
            "mixed_sort_prefix": (),
            "tightening_mode_active": False,
            "governing_domain": "combined",
            "has_target_domains": True,
            "new_max": 0.02,
            "new_total": 0.08,
            "required_fail_count": 0,
            "required_unsatisfied_count": 1,
            "prefer_total_before_max": False,
            "directional_tie_key": 0.12,
            "update_count": 4,
        },
        {
            "case": "not_tightening_no_target_domains",
            "tier": 3,
            "mixed_sort_prefix": (),
            "tightening_mode_active": False,
            "governing_domain": "combined",
            "has_target_domains": False,
            "new_distance": 0.31,
            "directional_tie_key": 0.2,
            "update_count": 1,
        },
        {
            "case": "mixed_direction_prefix_preserved",
            "tier": 0,
            "mixed_sort_prefix": (0, 0.01, 0.07),
            "tightening_mode_active": False,
            "governing_domain": "combined",
            "has_target_domains": True,
            "new_max": 0.03,
            "new_total": 0.1,
            "required_fail_count": 0,
            "required_unsatisfied_count": 2,
            "prefer_total_before_max": False,
            "directional_tie_key": 0.09,
            "update_count": 2,
        },
    ]

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "case"}
        old = _old_sort_key(**kwargs)
        new = _new_sort_key(**kwargs)
        row = {
            "case": str(case["case"]),
            "old": list(old),
            "new": list(new),
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    service_present = "def resolve_target_band_candidate_sort_key(" in candidate_source
    page_delegates = target_loop.count("_resolve_target_band_candidate_sort_key(") >= 2
    old_tuple_literals_removed = "sort_key = (" not in target_loop
    page_keeps_scoring_inputs = all(
        token in target_loop
        for token in (
            "web_crushing_penalty_applied",
            "practical_spacing_penalty",
            "congestion_penalty",
            "goal_bias",
            "wrong_dir_penalty",
            "_one_click_directional_tie_key(",
        )
    )
    forbidden_service_import_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]

    status = "PASS"
    if (
        mismatches
        or not service_present
        or not page_delegates
        or not old_tuple_literals_removed
        or not page_keeps_scoring_inputs
        or forbidden_service_import_hits
    ):
        status = "FAIL"

    return {
        "status": status,
        "surface": "target_band_candidate_sort_key",
        "inputs_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": target_start,
            "end_line": target_end,
        },
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "old_tuple_literals_removed": old_tuple_literals_removed,
            "page_keeps_scoring_inputs": page_keeps_scoring_inputs,
            "forbidden_service_import_hits": forbidden_service_import_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": [
                "target-band ranking tuple shape",
                "tightening-mode shear sort-key ordering",
                "tightening-mode non-shear sort-key ordering",
                "non-tightening sort-key ordering",
                "mixed-direction prefix preservation",
            ],
            "remains_page_shell_or_runtime_input": [
                "candidate loop orchestration",
                "candidate penalties and scalar input collection",
                "trace emission",
                "fallback next-hop injection",
                "winner selection callsite",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit/extract target-band candidate pruning or final winner selection policy",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_candidate_sort_key_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_candidate_sort_key_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        "# Target-Band Candidate Sort-Key Service Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved target-band candidate ranking tuple construction behind `design_brain.candidate_evaluation.resolve_target_band_candidate_sort_key(...)`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        md.append(f"- `{key}`: `{value}`")
    md.extend(
        [
            "",
            "## Parity",
            "",
            f"- Cases checked: `{payload['case_count']}`",
            f"- Mismatches: `{len(payload['mismatches'])}`",
            "",
            "## Ownership After",
            "",
            "- Candidate evaluation owns pure sort-key tuple shape.",
            "- `inputs_page.py` still collects scalar scoring inputs, traces, and orchestrates candidate loop flow.",
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
            "",
            f"JSON artifact: `{json_path}`",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
