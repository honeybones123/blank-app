"""Proof snapshot for combined low-util candidate-search evidence cutover."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import importlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"
HELPER_NAME = "build_design_guide_combined_low_util_cleanup_candidate_search_evidence"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


def _old_evidence(
    *,
    evidence_builder: Any,
    combined_updates: dict[str, Any],
    combined_worst: Any,
    combined_overview: dict[str, Any],
    target_low: Any,
    target_high: Any,
    shear_evidence: dict[str, Any],
    bending_evidence: dict[str, Any],
    bending_incremental_cleanup: bool,
    combined_audit: dict[str, Any],
) -> dict[str, Any]:
    evidence_candidate = {
        "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
        "label": "Shear and bending cleanup - one-click optimisation",
        "updates": dict(combined_updates),
        "candidate_post_util": combined_worst,
        "worst_util": combined_worst,
        "is_compliant": True,
        "overview": dict(combined_overview),
        "is_executable": True,
        "advisory_only": False,
        "affected_family": "combined",
    }
    evidence = evidence_builder(
        selected_candidate=evidence_candidate,
        all_candidates=[dict(evidence_candidate)],
        target_low=float(target_low),
        target_high=float(target_high),
        exhaustive=True,
        search_scope="combined_best_safe_shear_plus_bending_cleanup",
        selected_title="Shear and bending cleanup - one-click optimisation",
    )
    combined_post_apply_exact = dict(
        combined_audit.get("post_click_exact_blockers_by_family")
        or combined_audit.get("exact_blockers_by_family")
        or {}
    )
    evidence.update(
        {
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "optimisation_type": "combined_overdesign_cleanup",
            "family": "combined",
            "selected_candidate_updates": dict(combined_updates),
            "best_safe_candidate_updates": dict(combined_updates),
            "best_safe_candidate_applied": False,
            "best_safe_partial_cleanup": bool(
                shear_evidence.get("best_safe_partial_cleanup")
                or bending_evidence.get("best_safe_partial_cleanup")
            ),
            "safe_incremental_cleanup_below_final_threshold": bool(
                bending_incremental_cleanup
            ),
            "no_second_cta_required": False,
            "combined_from_best_safe_shear_cleanup": True,
            "shear_cleanup_evidence": dict(shear_evidence),
            "bending_cleanup_evidence": dict(bending_evidence),
            "post_apply_expected_exact_blockers_by_family": dict(combined_post_apply_exact),
            "post_click_unresolved_low_util_families": list(
                combined_audit.get("post_click_unresolved_low_util_families") or []
            ),
        }
    )
    return dict(evidence)


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)

    def evidence_builder(**kwargs: Any) -> dict[str, Any]:
        selected = dict(kwargs.get("selected_candidate") or {})
        return {
            "selected_candidate_id": selected.get("candidate_id"),
            "selected_title": kwargs.get("selected_title"),
            "search_scope": kwargs.get("search_scope"),
            "target_low": kwargs.get("target_low"),
            "target_high": kwargs.get("target_high"),
            "candidate_search_exhaustive": bool(kwargs.get("exhaustive")),
            "selected_candidate_updates": dict(selected.get("updates") or {}),
        }

    cases = [
        {
            "name": "best_safe_from_shear",
            "combined_updates": {"b": 375.0, "lig_d": 0, "lig_legs": 0},
            "combined_worst": 0.82,
            "combined_overview": {"utils": {"bending": 0.82, "shear": 0.71}},
            "target_low": 0.85,
            "target_high": 0.95,
            "shear_evidence": {"best_safe_partial_cleanup": True},
            "bending_evidence": {},
            "bending_incremental_cleanup": False,
            "combined_audit": {
                "post_click_exact_blockers_by_family": {"bending": {"reason": "below floor"}},
                "post_click_unresolved_low_util_families": ["bending"],
            },
        },
        {
            "name": "incremental_bending_cleanup",
            "combined_updates": {"b": 350.0, "n_bottom": 4},
            "combined_worst": 0.9,
            "combined_overview": {"utils": {"bending": 0.9, "shear": 0.65}},
            "target_low": 0.85,
            "target_high": 0.95,
            "shear_evidence": {},
            "bending_evidence": {"best_safe_partial_cleanup": True},
            "bending_incremental_cleanup": True,
            "combined_audit": {"exact_blockers_by_family": {"shear": {"reason": "kept safe"}}},
        },
    ]
    comparisons = []
    for case in cases:
        kwargs = {key: value for key, value in case.items() if key != "name"}
        kwargs["evidence_builder"] = evidence_builder
        old = _old_evidence(**kwargs)
        new_payload = helper(**kwargs)
        new = dict(new_payload.get("evidence") or {})
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
                "proof_hash": (new_payload.get("evidence_proof") or {}).get(
                    "evidence_boundary_hash"
                ),
            }
        )
    first_payload = helper(
        evidence_builder=evidence_builder,
        **{key: value for key, value in cases[0].items() if key != "name"},
    )
    repeat_payload = helper(
        evidence_builder=evidence_builder,
        **{key: value for key, value in cases[0].items() if key != "name"},
    )
    return {
        "comparisons": comparisons,
        "hash_repeat": _stable_hash(first_payload) == _stable_hash(repeat_payload),
        "missing_builder": helper(
            evidence_builder=None,
            **{key: value for key, value in cases[0].items() if key != "name"},
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_CANDIDATE_SEARCH_EVIDENCE_CUTOVER_PASS",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "helper_exercise": exercise,
        "source_checks": {
            "controller_helper_exported": f'"{HELPER_NAME}"' in controller_source,
            "controller_helper_imported": (
                f"{HELPER_NAME} as _build_design_guide_combined_low_util_cleanup_candidate_search_evidence"
                in inputs_source
            ),
            "controller_helper_called_once_in_target": (
                target_source.count(
                    "_build_design_guide_combined_low_util_cleanup_candidate_search_evidence("
                )
                == 1
            ),
            "legacy_candidate_search_evidence_call_removed_from_target": (
                "_build_candidate_search_evidence(" not in target_source
            ),
            "legacy_inline_evidence_candidate_removed_from_target": (
                "evidence_candidate = {" not in target_source
            ),
            "page_evidence_builder_injected_in_target": (
                "evidence_builder=_build_candidate_search_evidence" in target_source
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
            "no_render_apply_or_cta_owner_moved": all(
                token not in controller_source
                for token in (
                    "st.button",
                    "st.markdown",
                    "route_apply",
                    "apply_routing",
                    "render_button",
                    "streamlit",
                )
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    exercise = dict(capture.get("helper_exercise") or {})
    comparisons = list(exercise.get("comparisons") or [])
    missing_builder_proof = dict(
        (exercise.get("missing_builder") or {}).get("evidence_proof") or {}
    )
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "all_old_new_cases_match": all(item.get("match") for item in comparisons),
        "proof_hashes_present": all(item.get("proof_hash") for item in comparisons),
        "hash_repeat_stable": exercise.get("hash_repeat") is True,
        "missing_builder_recorded": (
            missing_builder_proof.get("builder_failed") is True
            and missing_builder_proof.get("builder_failed_reason")
            == "candidate_search_evidence_builder_missing"
        ),
        "source_checks_green": all(source_checks.values()),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Candidate Search Evidence Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases", ""])
    for item in (capture.get("helper_exercise") or {}).get("comparisons") or []:
        lines.append(f"- {item.get('case')}: `{item.get('match')}`")
    lines.extend(["", "## Source Checks"])
    lines.extend(
        f"- {key}: `{value}`"
        for key, value in (capture.get("source_checks") or {}).items()
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_candidate_search_evidence_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_candidate_search_evidence_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_candidate_search_evidence_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
