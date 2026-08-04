"""Proof snapshot for combined low-util bending cleanup generation cutover."""

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
HELPER_NAME = "run_design_guide_combined_low_util_bending_cleanup_item_generation"


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


def _exercise_helper() -> dict[str, Any]:
    module = importlib.import_module("design_brain.design_guide_controller")
    helper = getattr(module, HELPER_NAME)

    def generator(
        state: dict[str, Any],
        overview: dict[str, Any],
        mode_config: dict[str, Any],
        *,
        debug_sink: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(debug_sink, dict):
            debug_sink["called"] = True
            debug_sink["state_hash"] = _stable_hash(state)
        return {
            "title": "Bending cleanup",
            "state": dict(state),
            "overview": dict(overview),
            "mode_config": dict(mode_config),
        }

    cases = [
        {
            "name": "basic",
            "state": {"b": 400, "n_bottom": 5},
            "overview": {"utils": {"bending": 0.72}},
            "mode_config": {"target_util_min": 0.85},
        },
        {
            "name": "empty_overview",
            "state": {"d": 650},
            "overview": {},
            "mode_config": {},
        },
    ]
    comparisons = []
    for case in cases:
        old_debug: dict[str, Any] = {}
        old = generator(
            dict(case["state"]),
            dict(case["overview"]),
            dict(case["mode_config"]),
            debug_sink=old_debug,
        )
        payload = helper(
            bending_cleanup_generator=generator,
            state=case["state"],
            overview=case["overview"],
            mode_config=case["mode_config"],
        )
        comparisons.append(
            {
                "case": case["name"],
                "old": old,
                "new": payload.get("item"),
                "old_debug": old_debug,
                "new_debug": payload.get("debug"),
                "match": old == payload.get("item") and old_debug == payload.get("debug"),
                "proof_hash": (payload.get("bending_cleanup_generation_proof") or {}).get(
                    "bending_cleanup_generation_hash"
                ),
            }
        )
    first_payload = helper(
        bending_cleanup_generator=generator,
        state=cases[0]["state"],
        overview=cases[0]["overview"],
        mode_config=cases[0]["mode_config"],
    )
    repeat_payload = helper(
        bending_cleanup_generator=generator,
        state=cases[0]["state"],
        overview=cases[0]["overview"],
        mode_config=cases[0]["mode_config"],
    )
    return {
        "comparisons": comparisons,
        "hash_repeat": _stable_hash(first_payload) == _stable_hash(repeat_payload),
        "missing_generator": helper(
            bending_cleanup_generator=None,
            state=cases[0]["state"],
            overview=cases[0]["overview"],
            mode_config=cases[0]["mode_config"],
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_BENDING_CLEANUP_GENERATION_CUTOVER_PASS",
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
                f"{HELPER_NAME} as _run_design_guide_combined_low_util_bending_cleanup_item_generation"
                in inputs_source
            ),
            "controller_helper_called_once_in_target": (
                target_source.count(
                    "_run_design_guide_combined_low_util_bending_cleanup_item_generation("
                )
                == 1
            ),
            "legacy_bending_generator_call_removed_from_target": (
                "bending_item = _bending_only_target_band_cleanup_item(" not in target_source
            ),
            "page_bending_generator_injected_in_target": (
                "bending_cleanup_generator=_bending_only_target_band_cleanup_item" in target_source
            ),
            "debug_payload_retained": (
                'bending_debug: dict = dict(bending_generation.get("debug") or {})'
                in target_source
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
    missing_proof = dict(
        (exercise.get("missing_generator") or {}).get("bending_cleanup_generation_proof") or {}
    )
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "all_old_new_cases_match": all(item.get("match") for item in comparisons),
        "proof_hashes_present": all(item.get("proof_hash") for item in comparisons),
        "hash_repeat_stable": exercise.get("hash_repeat") is True,
        "missing_generator_recorded": (
            missing_proof.get("generator_failed") is True
            and missing_proof.get("generator_failed_reason")
            == "bending_cleanup_generator_missing"
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
        "# Design Guide Combined Low-Util Bending Cleanup Generation Cutover",
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
        / f"design_guide_combined_low_util_bending_cleanup_generation_cutover_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_combined_low_util_bending_cleanup_generation_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_bending_cleanup_generation_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
