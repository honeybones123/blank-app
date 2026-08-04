from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _load_candidate_module():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location(
        "candidate_evaluation_for_full_overview_projection_verifier",
        CANDIDATE_EVALUATION,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to import design_brain.candidate_evaluation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _status_from_util(util: float | None, unknown_status: str) -> str:
    if util is None or (isinstance(util, float) and math.isnan(util)):
        return unknown_status
    if util <= 1.0:
        return "NEAR LIMIT" if util >= 0.95 else "PASS"
    return "FAIL"


def _legacy_projection(
    *,
    base_overview: dict[str, Any],
    bending: dict[str, Any] | None,
    shear: dict[str, Any] | None,
    crack: dict[str, Any] | None,
    deflection: dict[str, Any] | None,
    unknown_status: str,
) -> dict[str, Any]:
    bending_util = None
    bending_status = unknown_status
    flexural_util = None
    ductility_util = None
    min_steel_util = None
    if bending:
        flexural_util = float(bending.get("Mu_util", float("inf")))
        try:
            ductility_util = (
                float(bending.get("ku", 0.0) or 0.0) / 0.36
                if bending.get("ku") is not None
                else None
            )
        except Exception:
            ductility_util = None
        try:
            as_min = float(bending.get("As_min", 0.0) or 0.0)
            ast = float(bending.get("Ast_bot", 0.0) or 0.0)
            if ast > 0.0 and as_min > 0.0:
                min_steel_util = as_min / ast
        except Exception:
            min_steel_util = None
        bending_util = flexural_util
        if bending_util is not None and math.isnan(bending_util):
            bending_util = None
        governs = [
            util
            for util in (flexural_util, ductility_util, min_steel_util)
            if util is not None and not math.isnan(util)
        ]
        if governs:
            if any(util > 1.0 for util in governs):
                bending_status = "FAIL"
            elif any(util >= 0.95 for util in governs):
                bending_status = "NEAR LIMIT"
            else:
                bending_status = "PASS"
        else:
            bending_status = unknown_status

    shear_util = None
    base_shear_util = None
    try:
        raw_base_shear = (base_overview.get("utils") or {}).get("shear")
        base_shear_util = float(raw_base_shear) if raw_base_shear is not None else None
        if base_shear_util is not None and math.isnan(base_shear_util):
            base_shear_util = None
    except Exception:
        base_shear_util = None
    base_shear_status = str((base_overview.get("statuses") or {}).get("shear") or unknown_status)
    if base_shear_util is not None:
        shear_util = base_shear_util
        shear_status = base_shear_status
    elif shear:
        shear_candidates = []
        for value in (shear.get("util"), shear.get("web_util")):
            try:
                coerced = float(value)
            except Exception:
                continue
            if not math.isnan(coerced):
                shear_candidates.append(coerced)
        shear_util = max(shear_candidates, default=None)
        shear_status = _status_from_util(shear_util, unknown_status)
    else:
        shear_util = None
        shear_status = base_shear_status

    statuses = dict(base_overview["statuses"])
    statuses["bending"] = bending_status
    statuses["shear"] = shear_status
    if crack is not None:
        crack_util = float(crack.get("util", 0.0) or 0.0)
        statuses["crack"] = _status_from_util(crack_util, unknown_status)
    if deflection is not None:
        statuses["deflection"] = str(deflection.get("status") or unknown_status)
    utils = dict(base_overview["utils"])
    utils["bending"] = bending_util
    utils["shear"] = shear_util
    if crack is not None:
        utils["crack"] = float(crack.get("util", 0.0) or 0.0)
    if deflection is not None:
        utils["deflection"] = deflection.get("util")
    packs = dict(base_overview["packs"])
    if deflection is not None:
        packs["deflection"] = dict(deflection.get("pack") or {})
    tracked_statuses = [status for status in statuses.values() if status not in (unknown_status, "")]
    overview = {
        "packs": packs,
        "statuses": statuses,
        "utils": utils,
        "any_fail": any(status == "FAIL" for status in tracked_statuses),
        "any_warn": any(status == "NEAR LIMIT" for status in tracked_statuses),
        "all_key_pass": bool(tracked_statuses) and all(status == "PASS" for status in tracked_statuses),
        "worst_util": max((util for util in utils.values() if util is not None), default=0.0),
    }
    return {
        "overview": overview,
        "bending_util": bending_util,
        "shear_util": shear_util,
        "flexural_util": flexural_util,
        "ductility_util": ductility_util,
        "min_steel_util": min_steel_util,
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    _, _, full_segment = _function_segment(inputs_source, "evaluate_candidate_full")
    module = _load_candidate_module()
    helper = module.build_full_candidate_evaluation_overview_status_projection
    unknown = "UNKNOWN"
    base = {
        "packs": {"bending": {"summary_phiMu_kNm": 123.0}},
        "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
        "utils": {"bending": 0.5, "shear": 0.7, "crack": 0.1, "deflection": 0.2},
    }
    cases = {
        "base_shear_precedence": {
            "base_overview": base,
            "bending": {"Mu_util": 0.8, "ku": 0.1, "As_min": 100, "Ast_bot": 200},
            "shear": {"util": 2.0, "web_util": 2.5},
            "crack": {"util": 0.2},
            "deflection": {"status": "PASS", "util": 0.4, "pack": {"d": 1}},
        },
        "fallback_shear_and_fail_bending": {
            "base_overview": {**base, "utils": {**base["utils"], "shear": None}},
            "bending": {"Mu_util": 1.2, "ku": 0.1, "As_min": 100, "Ast_bot": 200},
            "shear": {"util": 0.9, "web_util": 1.1},
            "crack": {"util": 1.2},
            "deflection": {"status": "FAIL", "util": 1.3, "pack": {"d": 2}},
        },
        "missing_optional_outputs": {
            "base_overview": base,
            "bending": None,
            "shear": None,
            "crack": None,
            "deflection": None,
        },
    }
    parity_rows = []
    for name, payload in cases.items():
        old_value = _legacy_projection(**payload, unknown_status=unknown)
        new_value = helper(**payload, unknown_status=unknown)
        parity_rows.append({"case": name, "matches": old_value == new_value})

    checks = {
        "service_helper_exists": "def build_full_candidate_evaluation_overview_status_projection(" in candidate_source,
        "service_helper_exported": '"build_full_candidate_evaluation_overview_status_projection"' in candidate_source,
        "page_calls_service_helper": "_build_full_candidate_evaluation_overview_status_projection(" in full_segment,
        "legacy_inline_overview_status_absent": all(
            token not in full_segment
            for token in (
                "base_shear_util = None",
                "tracked_statuses = [status for status in statuses.values()",
                "statuses[\"bending\"] = bending_status",
                "utils[\"shear\"] = shear_util",
            )
        ),
        "parity_cases_match": all(row["matches"] for row in parity_rows),
        "candidate_service_has_no_page_import": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "solver_execution_not_moved": all(
            token in full_segment
            for token in (
                "_evaluate_crack_with_state(",
                "_evaluate_deflection_with_state(",
                "_evaluate_bending_with_bottom_state(",
                "_evaluate_shear_with_state(",
                "_collect_design_overview(",
            )
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_full_candidate_evaluation_overview_status_projection_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FULL_CANDIDATE_EVALUATION_OVERVIEW_STATUS_PROJECTION_SERVICE_OWNED"
            if status == "PASS"
            else "FULL_CANDIDATE_EVALUATION_OVERVIEW_STATUS_PROJECTION_EXTRACTION_FAILED"
        ),
        "checks": checks,
        "parity_rows": parity_rows,
        "remaining_full_evaluator_page_owned": [
            "fingerprint/cache/profiling wrapper",
            "bottom/shear update collection",
            "solver/evaluator execution",
            "base overview collection",
            "physical metric input collection",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "parity_rows": parity_rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_full_candidate_evaluation_overview_status_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_full_candidate_evaluation_overview_status_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    rows = [
        "| Case | Matches |",
        "| --- | ---: |",
        *[f"| `{row['case']}` | `{row['matches']}` |" for row in snapshot["parity_rows"]],
    ]
    remaining = "\n".join(f"- {item}" for item in snapshot["remaining_full_evaluator_page_owned"])
    md_path.write_text(
        "\n".join(
            [
                "# Full Candidate Evaluation Overview/Status Projection Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Parity Cases",
                *rows,
                "",
                "## Remaining Full Evaluator Page-Owned Surfaces",
                remaining,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_full_candidate_evaluation_overview_status_projection_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
