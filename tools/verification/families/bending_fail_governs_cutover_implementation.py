"""Cutover implementation verifier for BENDING_FAIL_GOVERNS.

This verifies the narrow implementation cutover: the repair-ladder spec surface
is now driven by the contract runtime while page/shared evaluation, CTA,
publication, apply routing, visible wording, UI, session, and debug remain out
of the family runtime.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_fail import BendingFailFamily  # noqa: E402
from design_brain.families.bending_fail_governs.runtime import (  # noqa: E402
    bending_fail_governs_contract_lane_order,
)


EXPECTED_CONTRACT_ORDER = (
    "GEOMETRY_SANITY",
    "DEPTH_INCREASE",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "WIDTH_INCREASE",
    "MULTI_LAYER_REO",
    "EXACT_STOP",
    "NO_VALID_STRATEGY",
)

REQUIRED_SPEC_FIELDS = {
    "ladder_index",
    "contract_step",
    "stage_name",
    "strategy",
    "updates",
    "candidate_family_id",
    "stop_rule",
    "label",
    "contract_runtime_authority",
    "contract_runtime_lane_id",
    "selected_strategy_lane",
    "ladder_hash",
    "ladder_trace_evidence",
    "update_hash",
    "candidate_state_hash",
}

FORBIDDEN_RUNTIME_TERMS = {
    "button_label",
    "button_contract",
    "publication",
    "published_item",
    "rendered_html",
    "source_precedence",
    "st.session_state",
    "streamlit",
}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def _fixture_state() -> dict[str, Any]:
    return {
        "b": 300.0,
        "D": 350.0,
        "bot1_count": 2,
        "db_bot_1": 10,
        "bot_row_1_bars": 2,
        "bot_row_1_dia": 10,
        "cover_side": 40.0,
        "lig_d": 0,
    }


def _git_changed_shear_files() -> list[str]:
    paths = [
        "design_brain/families/shear_fail.py",
        "design_brain/families/shear_fail_governs",
        "design_brain/families/shear_overdesign_governs",
        "design_brain/families/shear_fail_bending_overdesign_governs",
    ]
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]


def _write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"bending_fail_governs_cutover_implementation_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_cutover_implementation_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# BENDING_FAIL_GOVERNS Cutover Implementation",
                "",
                f"Result: `{snapshot['result']}`",
                "",
                "## Checks",
                "",
                f"- delegated to contract runtime: `{snapshot['checks']['delegated_to_contract_runtime']}`",
                f"- contract order preserved: `{snapshot['checks']['contract_order_preserved']}`",
                f"- page evaluation loop retained: `{snapshot['checks']['page_evaluation_loop_retained']}`",
                f"- returned spec shape valid: `{snapshot['checks']['returned_spec_shape_valid']}`",
                f"- spec runtime evidence present: `{snapshot['checks']['spec_runtime_evidence_present']}`",
                f"- CTA/publication/apply/UI not moved: `{snapshot['checks']['cta_publication_apply_ui_not_moved']}`",
                f"- SHEAR files untouched: `{snapshot['checks']['shear_files_untouched']}`",
                "",
                "## Spec Lanes",
                "",
                "```text",
                " -> ".join(snapshot["spec_lane_order"]),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    bending_source = _read("design_brain/families/bending_fail.py")
    runtime_source = _read("design_brain/families/bending_fail_governs/runtime.py")
    inputs_source = _read("inputs_page.py")
    family = BendingFailFamily()
    ladder = family.contracted_repair_ladder_specs(_fixture_state(), geometry_locked=False)
    specs = [dict(spec) for spec in list(ladder.get("specs") or []) if isinstance(spec, dict)]
    spec_missing_fields = {
        str(spec.get("contract_runtime_lane_id") or f"index_{index}"): sorted(REQUIRED_SPEC_FIELDS - set(spec))
        for index, spec in enumerate(specs, start=1)
    }
    spec_lane_order = [str(spec.get("contract_runtime_lane_id") or "") for spec in specs]
    runtime_evidence_missing = [
        str(spec.get("contract_runtime_lane_id") or spec.get("label") or "")
        for spec in specs
        if not spec.get("ladder_hash")
        or not spec.get("update_hash")
        or not spec.get("candidate_state_hash")
        or not isinstance(spec.get("ladder_trace_evidence"), dict)
    ]
    forbidden_runtime_hits = sorted(
        term for term in FORBIDDEN_RUNTIME_TERMS if term.lower() in runtime_source.lower()
    )
    changed_shear_files = _git_changed_shear_files()
    inputs_surfaces = {
        "evaluate_loop": "def _evaluate(" in inputs_source,
        "auto_candidate_evaluator": "_evaluate_auto_design_candidate(" in inputs_source,
        "bending_family_strategy_dispatch": 'family_strategy_for("BENDING_FAIL_GOVERNS")' in inputs_source,
        "bending_ladder_call": "bending_family_strategy.contracted_repair_ladder_specs(" in inputs_source,
    }
    checks = {
        "delegated_to_contract_runtime": (
            bool(ladder.get("contract_runtime_driven"))
            and ladder.get("contract_runtime_authority") == "run_bending_fail_governs_ladder_runtime"
            and "run_bending_fail_governs_ladder_runtime(" in bending_source
        ),
        "contract_order_preserved": tuple(ladder.get("contract_lane_order") or ()) == EXPECTED_CONTRACT_ORDER
        and bending_fail_governs_contract_lane_order() == EXPECTED_CONTRACT_ORDER,
        "page_evaluation_loop_retained": (
            inputs_surfaces["evaluate_loop"]
            and inputs_surfaces["auto_candidate_evaluator"]
            and not inputs_surfaces["bending_family_strategy_dispatch"]
            and not inputs_surfaces["bending_ladder_call"]
        ),
        "returned_spec_shape_valid": bool(specs) and not any(spec_missing_fields.values()),
        "spec_runtime_evidence_present": bool(specs) and not runtime_evidence_missing,
        "cta_publication_apply_ui_not_moved": not forbidden_runtime_hits,
        "shear_files_untouched": not changed_shear_files,
    }
    snapshot = {
        "schema": "bending_fail_governs_cutover_implementation.v1",
        "result": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "contract_lane_order": list(bending_fail_governs_contract_lane_order()),
        "returned_ladder": {
            "contract_runtime_driven": ladder.get("contract_runtime_driven"),
            "contract_runtime_authority": ladder.get("contract_runtime_authority"),
            "candidate_strategy": ladder.get("candidate_strategy"),
            "ranking_rule": ladder.get("ranking_rule"),
            "stop_reason_if_no_candidate": ladder.get("stop_reason_if_no_candidate"),
            "ladder_hash": ladder.get("ladder_hash"),
            "known_bad_candidate_count": ladder.get("known_bad_candidate_count"),
            "spec_count": len(specs),
        },
        "spec_lane_order": spec_lane_order,
        "spec_missing_fields": spec_missing_fields,
        "runtime_evidence_missing": runtime_evidence_missing,
        "inputs_page_surfaces": inputs_surfaces,
        "forbidden_runtime_hits": forbidden_runtime_hits,
        "changed_shear_files": changed_shear_files,
        "scope_limits": {
            "moves_cta_rendering": False,
            "moves_publication": False,
            "moves_apply_routing": False,
            "moves_one_click": False,
            "moves_visible_wording": False,
            "moves_ui_session_debug": False,
            "touches_shear_fail_governs": False,
        },
    }
    json_path, report_path = _write_artifacts(snapshot)
    if snapshot["result"] != "PASS":
        print("cutover implementation FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        return 1
    print("cutover implementation PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
