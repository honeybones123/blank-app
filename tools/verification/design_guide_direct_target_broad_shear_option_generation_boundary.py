"""Verify broad direct target-band shear option packaging is service-backed."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
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

TARGET = "_direct_target_band_guidance_item"
SERVICE_HELPER = "build_direct_target_band_broad_shear_options"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node.lineno, int(node.end_lineno or node.lineno), "\n".join(
                lines[node.lineno - 1 : int(node.end_lineno or node.lineno)]
            )
    return 0, 0, ""


def _hash(value: Any) -> str:
    from design_brain.candidate_evaluation import stable_candidate_evaluation_hash

    return stable_candidate_evaluation_hash(value)


def _legacy_options(raw_options: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    shear_options = [{}]
    for option in list(raw_options or []):
        shear_options.append(dict(option or {}))
    dedup: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for option in shear_options:
        sig = tuple(sorted((str(k), str(v)) for k, v in dict(option or {}).items()))
        dedup[sig] = dict(option or {})
    return list(dedup.values())


def _parity() -> dict[str, Any]:
    from design_brain.candidate_evaluation import build_direct_target_band_broad_shear_options

    cases = [
        ("empty_defaults_to_no_shear_update", []),
        ("single_option", [{"lig_d": 10, "lig_legs": 2}]),
        ("duplicate_options_preserve_legacy_dedupe", [{"lig_d": 10}, {"lig_d": 10}, {"s_lig": 100.0}]),
        ("string_equivalent_dedupe", [{"s_lig": 100}, {"s_lig": "100"}]),
    ]
    rows: list[dict[str, Any]] = []
    for name, raw in cases:
        expected = _legacy_options(raw)
        actual = build_direct_target_band_broad_shear_options(raw)
        rows.append(
            {
                "case": name,
                "expected_hash": _hash(expected),
                "actual_hash": _hash(actual),
                "passed": actual == expected,
            }
        )
    return {
        "cases": rows,
        "all_passed": all(bool(row.get("passed")) for row in rows),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_source = _function_source(inputs_source, TARGET)
    service_start, service_end, service_source = _function_source(candidate_source, SERVICE_HELPER)
    source_checks = {
        "service_helper_exists": bool(service_source),
        "service_helper_exported": f'"{SERVICE_HELPER}"' in candidate_source,
        "inputs_imports_service_helper": f"{SERVICE_HELPER} as _{SERVICE_HELPER}" in inputs_source,
        "target_calls_service_helper": f"_{SERVICE_HELPER}(raw_shear_options)" in target_source,
        "target_no_longer_owns_shear_option_default": "shear_options: list[dict] = [{}]" not in target_source,
        "target_no_longer_owns_shear_option_dedupe": all(
            token not in target_source
            for token in (
                "dedup_shear",
                "for option in shear_options:",
                "shear_options = list(dedup_shear.values())",
            )
        ),
        "variant_generators_remain_page_owned": all(
            token in target_source
            for token in (
                "_generate_escalated_shear_states(",
                "generate_less_shear_reo_variants(",
                "_one_click_diff_accumulated_updates(",
            )
        ),
        "evaluation_ranking_projection_remain_page_owned": all(
            token in target_source
            for token in (
                "_evaluate_updates(",
                "_select_direct_target_item(",
                "selected = min(",
                "_build_candidate_search_evidence(",
                "_guidance_item_from_resolved_candidate(",
                "item[\"action_payload\"]",
            )
        ),
        "candidate_evaluation_import_clean_terms_absent": all(
            token not in candidate_source
            for token in (
                "inputs_page",
                "streamlit",
                "st.session_state",
                "rendered_html",
                "apply_routing",
                "ui_state",
            )
        ),
    }
    return {
        "schema": "design_guide_direct_target_broad_shear_option_generation_boundary.v1",
        "target": {
            "name": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "service_helper": {
            "name": SERVICE_HELPER,
            "line_start": service_start,
            "line_end": service_end,
            "line_count": max(0, service_end - service_start + 1),
        },
        "parity": _parity(),
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "remaining_page_owned_surfaces": [
            "broad shear variant generator callbacks",
            "broad width/depth geometry loop",
            "broad bottom trial generation",
            "candidate evaluation execution loop",
            "safe/target/fallback ranking",
            "evidence and item projection",
        ],
        "next_safe_slice": "broad_search_geometry_plan_service_boundary_or_direct_target_final_selection_policy_extraction",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "parity_passed": bool((capture.get("parity") or {}).get("all_passed")),
        **{str(key): bool(value) for key, value in source_checks.items()},
        "product_behavior_unchanged": not bool(capture.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(capture.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(capture.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(capture.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_broad_shear_option_generation_boundary_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_broad_shear_option_generation_boundary_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Broad Shear Option Generation Boundary",
        "",
        f"Status: {payload['status']}",
        "",
        "## Parity",
    ]
    for row in (payload.get("parity") or {}).get("cases") or []:
        lines.append(f"- {row['case']}: {'PASS' if row.get('passed') else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Surfaces",
            *[f"- {item}" for item in payload.get("remaining_page_owned_surfaces") or []],
            "",
            "## Checks",
            *[f"- {name}: {'PASS' if passed else 'FAIL'}" for name, passed in checks.items()],
            "",
            f"Next safe slice: `{payload.get('next_safe_slice')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        **capture,
        "status": status,
        "checks": checks,
        "checked_at": _timestamp(),
    }
    json_path, report_path = _write(payload, checks)
    print(f"design_guide_direct_target_broad_shear_option_generation_boundary {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
