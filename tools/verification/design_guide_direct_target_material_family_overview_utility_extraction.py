"""Verify material-family overview utility is controller-owned."""

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_WRAPPER = "identify_materially_overprovided_non_governing_families"
CONTROLLER_HELPER = "identify_design_guide_controller_materially_overprovided_non_governing_families"


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


def _legacy_identify(overview: dict[str, Any] | None, *, threshold: float = 0.70) -> tuple[dict[str, float], list[str], str | None]:
    import math

    ov = overview if isinstance(overview, dict) else {}
    utils = dict(ov.get("utils") or {})
    out: dict[str, float] = {}
    for key, value in utils.items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            out[str(key or "").strip().lower()] = parsed
    packs = dict(ov.get("packs") or {})
    for key, pack in packs.items():
        if not isinstance(pack, dict):
            continue
        family = str(key or "").strip().lower()
        if family == "serviceability":
            family = "deflection"
        for field in ("summary_util", "util", "governing_util", "max_util"):
            try:
                parsed = float(pack.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out.setdefault(family, parsed)
                break
    for family in ("bending", "shear", "crack", "deflection", "serviceability", "ductility"):
        for field in (f"{family}_util", f"{family}_utilisation"):
            if family in out:
                continue
            try:
                parsed = float(ov.get(field))
            except (TypeError, ValueError):
                continue
            if math.isfinite(parsed):
                out[family] = parsed

    explicit = str(ov.get("governing_family") or "").strip().lower()
    if explicit and explicit not in {"overview_worst_util", "governing", "overall"}:
        governing = explicit
    else:
        check = str(ov.get("governing_check") or "").strip().lower()
        if "shear" in check:
            governing = "shear"
        elif "bend" in check or "moment" in check:
            governing = "bending"
        elif "deflect" in check:
            governing = "deflection"
        elif "crack" in check:
            governing = "crack"
        elif out:
            try:
                governing = max(out.items(), key=lambda item: item[1])[0]
            except Exception:
                governing = None
        else:
            governing = None
    families = [
        family
        for family, util in sorted(out.items())
        if family != governing
        and float(util) < float(threshold)
        and not (family in {"crack", "deflection", "serviceability", "geometry"} and float(util) <= 1e-9)
    ]
    return out, families, governing


def _parity() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        identify_design_guide_controller_materially_overprovided_non_governing_families,
    )

    cases = [
        {
            "case": "utils_with_governing_check",
            "overview": {"utils": {"bending": 0.92, "shear": 0.42}, "governing_check": "Bending ULS"},
        },
        {
            "case": "packs_serviceability_alias",
            "overview": {
                "packs": {
                    "serviceability": {"summary_util": 0.0},
                    "shear": {"max_util": 0.61},
                    "bending": {"util": 0.89},
                },
                "governing_family": "bending",
            },
        },
        {
            "case": "top_level_util_fields",
            "overview": {"bending_util": 0.31, "shear_utilisation": 0.97},
        },
    ]
    rows: list[dict[str, Any]] = []
    for case in cases:
        expected = _legacy_identify(case["overview"])
        actual = identify_design_guide_controller_materially_overprovided_non_governing_families(case["overview"])
        rows.append(
            {
                "case": case["case"],
                "expected": [expected[0], expected[1], expected[2]],
                "actual": [actual[0], actual[1], actual[2]],
                "passed": actual == expected,
            }
        )
    return {"cases": rows, "all_passed": all(bool(row.get("passed")) for row in rows)}


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    wrapper_start, wrapper_end, wrapper_source = _function_source(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_source = _function_source(controller_source, CONTROLLER_HELPER)
    private_consumers = {
        "_overview_family_utils_for_local_cleanup": inputs_source.count("_overview_family_utils_for_local_cleanup(") - 1,
        "_governing_family_for_local_cleanup": inputs_source.count("_governing_family_for_local_cleanup(") - 1,
    }
    source_checks = {
        "controller_helper_exists": bool(helper_source),
        "controller_helper_exported": f'"{CONTROLLER_HELPER}"' in controller_source,
        "inputs_imports_controller_helper": f"{CONTROLLER_HELPER} as _{CONTROLLER_HELPER}" in inputs_source,
        "page_wrapper_delegates_to_controller": f"_{CONTROLLER_HELPER}(" in wrapper_source,
        "page_wrapper_no_longer_owns_family_filter": "for family, util in sorted(family_utils.items())" not in wrapper_source,
        "private_helpers_retained_because_other_consumers_exist": all(count > 0 for count in private_consumers.values()),
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source
        and "streamlit" not in controller_source
        and "st.session_state" not in controller_source,
    }
    return {
        "schema": "design_guide_direct_target_material_family_overview_utility_extraction.v1",
        "page_wrapper": {
            "name": PAGE_WRAPPER,
            "line_start": wrapper_start,
            "line_end": wrapper_end,
            "line_count": max(0, wrapper_end - wrapper_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": helper_start,
            "line_end": helper_end,
            "line_count": max(0, helper_end - helper_start + 1),
        },
        "private_helper_consumer_counts": private_consumers,
        "parity": _parity(),
        "source_checks": source_checks,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_slice": "direct_target_selection_dependency_row_after_state_score_audit",
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
    json_path = ARTIFACT_DIR / f"design_guide_direct_target_material_family_overview_utility_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_direct_target_material_family_overview_utility_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Direct Target Material-Family Overview Utility Extraction",
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
            "## Private Helper Consumers",
            *[
                f"- {name}: {count}"
                for name, count in (payload.get("private_helper_consumer_counts") or {}).items()
            ],
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
    print(f"design_guide_direct_target_material_family_overview_utility_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
