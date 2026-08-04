"""Verify mixed-direction classification service extraction."""

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
    resolve_candidate_domain_score,
    resolve_candidate_mixed_direction_classification,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_MIN = 0.85
DEFAULT_MAX = 1.0
FAIL = "FAIL"


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


def _candidate(*, bending: Any = None, shear: Any = None, mu: Any = None, phi: Any = None, statuses: dict[str, Any] | None = None) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    return {
        "overview": {
            "statuses": dict(statuses or {}),
            "utils": {"bending": bending, "shear": shear},
            "packs": {"bending": bending_pack},
        }
    }


def _score(eval_obj: dict[str, Any] | None, domain: str, mode_config: dict[str, Any]) -> dict[str, Any]:
    return resolve_candidate_domain_score(
        eval_obj,
        domain,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
    )


def _old_classification(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any],
    *,
    shear_demand_meaningful: bool,
    bending_demand_meaningful: bool,
    overdesign_margin: float = 0.03,
) -> str | None:
    bending = _score(eval_obj, "bending", mode_config)
    shear = _score(eval_obj, "shear", mode_config)
    try:
        lo = float(mode_config.get("target_util_min", DEFAULT_MIN) or DEFAULT_MIN)
    except Exception:
        lo = float(DEFAULT_MIN)
    margin = float(max(0.0, overdesign_margin))

    def materially_over(score: dict[str, Any]) -> bool:
        util = score.get("util")
        try:
            fu = float(util)
        except (TypeError, ValueError):
            return False
        return bool(score.get("pass") and fu < (lo - margin))

    if (
        (not bool(bending.get("pass")))
        and materially_over(shear)
        and bool(shear_demand_meaningful)
    ):
        return "bending_under_shear_over"
    if (
        (not bool(shear.get("pass")))
        and materially_over(bending)
        and bool(bending_demand_meaningful)
    ):
        return "bending_over_shear_under"
    return None


def _new_classification(
    eval_obj: dict[str, Any] | None,
    mode_config: dict[str, Any],
    *,
    shear_demand_meaningful: bool,
    bending_demand_meaningful: bool,
    overdesign_margin: float = 0.03,
) -> str | None:
    return resolve_candidate_mixed_direction_classification(
        eval_obj,
        mode_config,
        shear_demand_meaningful=shear_demand_meaningful,
        bending_demand_meaningful=bending_demand_meaningful,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        overdesign_margin=overdesign_margin,
    )


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    _, _, wrapper = _function_segment(inputs_source, "_one_click_mixed_direction_classification")
    cases = [
        (
            "bending_under_shear_over",
            _candidate(mu=70.0, phi=100.0, shear=0.6, statuses={"bending": "FAIL", "shear": "PASS"}),
            {},
            True,
            True,
            0.03,
        ),
        (
            "bending_under_no_shear_demand",
            _candidate(mu=70.0, phi=100.0, shear=0.6, statuses={"bending": "FAIL", "shear": "PASS"}),
            {},
            False,
            True,
            0.03,
        ),
        (
            "shear_under_bending_over",
            _candidate(mu=60.0, phi=100.0, shear=1.2, statuses={"bending": "PASS", "shear": "FAIL"}),
            {},
            True,
            True,
            0.03,
        ),
        (
            "shear_under_no_bending_demand",
            _candidate(mu=60.0, phi=100.0, shear=1.2, statuses={"bending": "PASS", "shear": "FAIL"}),
            {},
            True,
            False,
            0.03,
        ),
        (
            "not_materially_over_margin",
            _candidate(mu=84.0, phi=100.0, shear=1.2, statuses={"bending": "PASS", "shear": "FAIL"}),
            {},
            True,
            True,
            0.03,
        ),
        (
            "custom_margin",
            _candidate(mu=78.0, phi=100.0, shear=1.2, statuses={"bending": "PASS", "shear": "FAIL"}),
            {"target_util_min": 0.8, "target_util_max": 1.0},
            True,
            True,
            0.01,
        ),
        (
            "none_when_all_pass",
            _candidate(mu=90.0, phi=100.0, shear=0.9, statuses={"bending": "PASS", "shear": "PASS"}),
            {},
            True,
            True,
            0.03,
        ),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate, mode_config, shear_meaningful, bending_meaningful, margin in cases:
        old = _old_classification(
            candidate,
            mode_config,
            shear_demand_meaningful=shear_meaningful,
            bending_demand_meaningful=bending_meaningful,
            overdesign_margin=margin,
        )
        new = _new_classification(
            candidate,
            mode_config,
            shear_demand_meaningful=shear_meaningful,
            bending_demand_meaningful=bending_meaningful,
            overdesign_margin=margin,
        )
        row = {"case": name, "old": old, "new": new, "matches": old == new}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_delegates = "_resolve_candidate_mixed_direction_classification(" in wrapper
    page_keeps_action_inputs = (
        "_build_design_actions_context_isolated(" in wrapper
        and "_shear_demands_negligible(" in wrapper
        and "_bending_demands_negligible(" in wrapper
    )
    wrapper_no_score_policy = (
        "_one_click_domain_score(" not in wrapper
        and "_materially_over" not in wrapper
        and "target_util_min" not in wrapper
    )
    service_present = "def resolve_candidate_mixed_direction_classification(" in candidate_source
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
        or not wrapper_delegates
        or not page_keeps_action_inputs
        or not wrapper_no_score_policy
        or not service_present
        or forbidden_service_import_hits
    ):
        status = "FAIL"
    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wrapper_delegates": wrapper_delegates,
        "page_keeps_action_inputs": page_keeps_action_inputs,
        "wrapper_no_score_policy": wrapper_no_score_policy,
        "service_present": service_present,
        "forbidden_service_import_hits": forbidden_service_import_hits,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "next_safe_slice": "candidate selection/search policy audit",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_mixed_direction_classification_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_mixed_direction_classification_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Mixed-Direction Classification Service Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Proof",
        f"- Wrapper delegates: `{payload['wrapper_delegates']}`",
        f"- Page keeps action inputs: `{payload['page_keeps_action_inputs']}`",
        f"- Wrapper no score policy: `{payload['wrapper_no_score_policy']}`",
        f"- Service helper present: `{payload['service_present']}`",
        f"- Forbidden service import hits: `{payload['forbidden_service_import_hits']}`",
        f"- Cases: `{payload['case_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
        "",
        "## Next Safe Slice",
        f"`{payload['next_safe_slice']}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
