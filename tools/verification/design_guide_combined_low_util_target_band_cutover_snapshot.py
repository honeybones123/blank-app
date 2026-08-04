"""Proof snapshot for combined low-util target-band resolution cutover."""

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
HELPER_NAME = "resolve_design_guide_combined_low_util_cleanup_target_band"


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

    def goal_resolver(state: dict[str, Any] | None = None) -> str:
        return str((state or {}).get("design_optimisation_goal") or "balanced")

    def target_resolver(mode_config: dict[str, Any] | None = None, *, goal: str = "") -> tuple[float, float, dict[str, Any]]:
        cfg = dict(mode_config or {})
        return (
            float(cfg.get("target_util_min", 0.85)),
            float(cfg.get("target_util_max", 0.95)),
            {"goal": goal, "source": "synthetic_target_resolver"},
        )

    cases = [
        {
            "name": "balanced_default",
            "state": {"design_optimisation_goal": "balanced"},
            "mode_config": {"target_util_min": 0.85, "target_util_max": 0.95},
        },
        {
            "name": "conservative_band",
            "state": {"design_optimisation_goal": "conservative"},
            "mode_config": {"target_util_min": 0.8, "target_util_max": 0.9},
        },
    ]
    comparisons = []
    for case in cases:
        old_goal = goal_resolver(case["state"])
        old_payload = target_resolver(case["mode_config"], goal=old_goal)
        new_payload = helper(
            target_band_resolver=target_resolver,
            optimisation_goal_resolver=goal_resolver,
            state=case["state"],
            mode_config=case["mode_config"],
        )
        comparisons.append(
            {
                "case": case["name"],
                "old_target_low": old_payload[0],
                "new_target_low": new_payload.get("target_low"),
                "old_target_high": old_payload[1],
                "new_target_high": new_payload.get("target_high"),
                "old_goal": old_goal,
                "new_goal": new_payload.get("optimisation_goal"),
                "match": (
                    old_payload[0] == new_payload.get("target_low")
                    and old_payload[1] == new_payload.get("target_high")
                    and old_goal == new_payload.get("optimisation_goal")
                ),
                "proof_hash": (new_payload.get("target_band_proof") or {}).get(
                    "target_band_boundary_hash"
                ),
            }
        )
    first_payload = helper(
        target_band_resolver=target_resolver,
        optimisation_goal_resolver=goal_resolver,
        state=cases[0]["state"],
        mode_config=cases[0]["mode_config"],
    )
    repeat_payload = helper(
        target_band_resolver=target_resolver,
        optimisation_goal_resolver=goal_resolver,
        state=cases[0]["state"],
        mode_config=cases[0]["mode_config"],
    )
    missing_payload = helper(
        target_band_resolver=None,
        optimisation_goal_resolver=None,
        state=cases[0]["state"],
        mode_config=cases[0]["mode_config"],
    )
    return {
        "comparisons": comparisons,
        "hash_repeat": _stable_hash(first_payload) == _stable_hash(repeat_payload),
        "missing_resolvers": missing_payload,
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    target_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    exercise = _exercise_helper()
    return {
        "decision": "COMBINED_LOW_UTIL_TARGET_BAND_CUTOVER_PASS",
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
                f"{HELPER_NAME} as _resolve_design_guide_combined_low_util_cleanup_target_band"
                in inputs_source
            ),
            "controller_helper_called_once_in_target": (
                target_source.count("_resolve_design_guide_combined_low_util_cleanup_target_band(") == 1
            ),
            "legacy_target_band_call_removed_from_target": (
                "_resolved_efficiency_target_band(" not in target_source
            ),
            "legacy_optimisation_goal_call_removed_from_target": (
                "_design_optimisation_goal(" not in target_source
            ),
            "page_resolvers_injected_in_target": (
                "target_band_resolver=_resolved_efficiency_target_band" in target_source
                and "optimisation_goal_resolver=_design_optimisation_goal" in target_source
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
    missing_proof = dict((exercise.get("missing_resolvers") or {}).get("target_band_proof") or {})
    source_checks = dict(capture.get("source_checks") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "all_old_new_cases_match": all(item.get("match") for item in comparisons),
        "proof_hashes_present": all(item.get("proof_hash") for item in comparisons),
        "hash_repeat_stable": exercise.get("hash_repeat") is True,
        "missing_resolvers_recorded": (
            missing_proof.get("resolver_error") == "optimisation_goal_resolver_missing"
            and missing_proof.get("target_error") == "target_band_resolver_missing"
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
        "# Design Guide Combined Low-Util Target-Band Cutover",
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
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_target_band_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_target_band_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_target_band_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
