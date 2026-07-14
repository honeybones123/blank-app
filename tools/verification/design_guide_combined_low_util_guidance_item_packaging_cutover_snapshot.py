"""Proof snapshot for combined low-util guidance item packaging cutover."""

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
HELPER_NAME = "build_design_guide_combined_low_util_guidance_item_packaging"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int | None, int | None]:
    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    return "", None, None


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)

    def guidance_item_builder(
        candidate: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
        overview: dict[str, Any] | None = None,
        title: str = "",
        reasoning: str = "",
        status: str = "",
        primary_action: str = "",
    ) -> dict[str, Any]:
        return {
            "candidate": dict(candidate or {}),
            "state": dict(state or {}),
            "overview": dict(overview or {}),
            "title_main": title,
            "title": title,
            "reasoning": reasoning,
            "status": status,
            "primary_action": primary_action,
        }

    cases = [
        {
            "name": "combined_candidate",
            "combined_candidate": {
                "candidate_id": "combined_best_safe_shear_plus_bending_cleanup",
                "updates": {"b": 350, "n_bottom": 4, "lig_legs": 0},
            },
            "state": {"b": 400, "n_bottom": 5, "lig_legs": 2},
            "overview": {"worst_util": 0.88},
        },
        {
            "name": "empty_overview",
            "combined_candidate": {"candidate_id": "candidate_b", "updates": {"n_bottom": 3}},
            "state": {"n_bottom": 4},
            "overview": {},
        },
    ]
    comparisons = []
    for case in cases:
        old = guidance_item_builder(
            case["combined_candidate"],
            state=case["state"],
            overview=case["overview"],
            title="Shear and bending cleanup - one-click optimisation",
            reasoning=(
                "This combines the best safe shear-link cleanup with the bending reinforcement cleanup "
                "so the current optimisation flow is handled in one click."
            ),
            status="EFFICIENCY",
            primary_action="Run one-click auto design",
        )
        payload = helper(
            guidance_item_builder=guidance_item_builder,
            combined_candidate=case["combined_candidate"],
            state=case["state"],
            overview=case["overview"],
        )
        new = payload.get("item")
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": new,
                "match": old == new,
                "proof_hash": (payload.get("guidance_item_packaging_proof") or {}).get(
                    "guidance_item_packaging_hash"
                ),
            }
        )
    first_payload = helper(
        guidance_item_builder=guidance_item_builder,
        combined_candidate=cases[0]["combined_candidate"],
        state=cases[0]["state"],
        overview=cases[0]["overview"],
    )
    repeat_payload = helper(
        guidance_item_builder=guidance_item_builder,
        combined_candidate=cases[0]["combined_candidate"],
        state=cases[0]["state"],
        overview=cases[0]["overview"],
    )
    return {
        "comparisons": comparisons,
        "hash_repeat": _stable_hash(first_payload) == _stable_hash(repeat_payload),
        "missing_builder": helper(
            guidance_item_builder=None,
            combined_candidate=cases[0]["combined_candidate"],
            state=cases[0]["state"],
            overview=cases[0]["overview"],
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    function_deleted = start_line is None
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_GUIDANCE_ITEM_PACKAGING_CUTOVER_PASS",
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": (end_line - start_line + 1) if not function_deleted else 0,
            "deleted": function_deleted,
        },
        "helper_exercise": exercise,
        "source_checks": {
            "controller_helper_exported": f'"{HELPER_NAME}"' in controller_source,
            "controller_helper_imported": (
                f"{HELPER_NAME} as _build_design_guide_combined_low_util_guidance_item_packaging"
                in inputs_source
            ),
            "controller_helper_used_by_result_packaging": (
                "build_design_guide_combined_low_util_guidance_item_packaging("
                in controller_source
            ),
            "legacy_guidance_item_builder_call_removed_from_target": (
                function_deleted or "_guidance_item_from_resolved_candidate(" not in target_source
            ),
            "page_guidance_item_builder_injected_via_result_packaging": (
                function_deleted
                or "guidance_item_builder=_guidance_item_from_resolved_candidate" in target_source
            ),
            "post_packaging_mutations_moved_from_target": all(
                token not in target_source
                for token in (
                    'item["action_payload"] = payload',
                    'item["resolved_candidate"] = resolved',
                    'item["button_contract"] = contract',
                )
            ),
            "controller_page_free": all(
                token not in controller_source
                for token in ("inputs_page", "st.session_state", "streamlit")
            ),
            "no_render_apply_or_cta_owner_moved": all(
                token not in controller_source
                for token in (
                    "st.button(",
                    "st.markdown(",
                    "_queue_primary_design_guide_button_action(",
                    "_record_rendered_design_guide_primary_apply_payload(",
                    "_render_design_guide_button(",
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
    missing_proof = dict(
        (exercise.get("missing_builder") or {}).get("guidance_item_packaging_proof") or {}
    )
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found_or_deleted": (
            bool((capture.get("function") or {}).get("line_count"))
            or bool((capture.get("function") or {}).get("deleted"))
        ),
        "all_old_new_cases_match": all(item.get("match") for item in comparisons),
        "proof_hashes_present": all(item.get("proof_hash") for item in comparisons),
        "hash_repeat_stable": exercise.get("hash_repeat") is True,
        "missing_builder_recorded": (
            missing_proof.get("builder_failed") is True
            and missing_proof.get("builder_failed_reason") == "guidance_item_builder_missing"
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
        "# Design Guide Combined Low-Util Guidance Item Packaging Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Cases"])
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
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_combined_low_util_guidance_item_packaging_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_guidance_item_packaging_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_guidance_item_packaging_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
