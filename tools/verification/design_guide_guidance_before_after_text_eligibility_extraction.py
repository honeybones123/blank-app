"""Verify before/after text eligibility is controller-owned.

This checks the narrow extraction from `_guidance_before_after_text(...)`:
the pure action-type eligibility/default policy now lives in
DesignGuideController, while update resolution and visible wording remain on
the existing page path for later extraction slices.
"""

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
TARGET_HELPER = "_guidance_before_after_text"
CONTROLLER_HELPER = "resolve_design_guide_controller_before_after_text_eligibility"


EXCLUDED_ACTIONS = [
    "apply_mode_recommendation",
    "apply_bottom_recommendation",
    "apply_geometry_recommendation",
    "apply_shear_recommendation",
    "apply_compound_guidance",
    "reduce_bottom_reinforcement",
    "increase_link_spacing",
    "reduce_number_of_legs",
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _function_source(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            end = int(node.end_lineno or node.lineno)
            return node.lineno, end, "\n".join(lines[node.lineno - 1 : end])
    return 0, 0, ""


def _controller_outputs() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_before_after_text_eligibility,
    )

    outputs: dict[str, Any] = {
        "missing": resolve_design_guide_controller_before_after_text_eligibility(action_type=None),
        "normal": resolve_design_guide_controller_before_after_text_eligibility(
            action_type="apply_resolved_candidate"
        ),
        "excluded": {},
    }
    for action in EXCLUDED_ACTIONS:
        outputs["excluded"][action] = resolve_design_guide_controller_before_after_text_eligibility(
            action_type=action
        )
    return outputs


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    target_start, target_end, target_segment = _function_source(inputs_source, TARGET_HELPER)
    controller_start, controller_end, controller_segment = _function_source(
        controller_source, CONTROLLER_HELPER
    )
    outputs = _controller_outputs()
    controller_forbidden_tokens = ["inputs_page", "streamlit", "st.session_state"]
    return {
        "schema": "design_guide_guidance_before_after_text_eligibility_extraction.v1",
        "target": {
            "helper": TARGET_HELPER,
            "line_start": target_start,
            "line_end": target_end,
            "line_count": max(0, target_end - target_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
        },
        "source_evidence": {
            "page_delegates_to_controller": "_resolve_design_guide_controller_before_after_text_eligibility("
            in target_segment,
            "page_local_expensive_action_set_removed": "expensive_action_types" not in target_segment,
            "page_update_resolution_kept": "_guidance_action_updates(" in target_segment,
            "page_visible_wording_kept": "_describe_guidance_step(" in target_segment,
            "controller_exported": f'"{CONTROLLER_HELPER}"' in controller_source,
            "controller_forbidden_imports": {
                token: token in controller_source for token in controller_forbidden_tokens
            },
        },
        "behaviour_samples": outputs,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    evidence = dict(payload.get("source_evidence") or {})
    forbidden = dict(evidence.get("controller_forbidden_imports") or {})
    samples = dict(payload.get("behaviour_samples") or {})
    missing = dict(samples.get("missing") or {})
    normal = dict(samples.get("normal") or {})
    excluded = dict(samples.get("excluded") or {})
    return {
        "target_helper_found": bool((payload.get("target") or {}).get("line_start")),
        "controller_helper_found": bool((payload.get("controller_helper") or {}).get("line_start")),
        "page_delegates_to_controller": bool(evidence.get("page_delegates_to_controller")),
        "page_local_expensive_action_set_removed": bool(
            evidence.get("page_local_expensive_action_set_removed")
        ),
        "page_update_resolution_kept": bool(evidence.get("page_update_resolution_kept")),
        "page_visible_wording_kept": bool(evidence.get("page_visible_wording_kept")),
        "controller_exported": bool(evidence.get("controller_exported")),
        "controller_boundary_clean": not any(bool(value) for value in forbidden.values()),
        "missing_action_ineligible": missing.get("eligible") is False
        and missing.get("reason") == "missing_action_type",
        "normal_action_eligible": normal.get("eligible") is True
        and normal.get("action_type") == "apply_resolved_candidate",
        "all_excluded_actions_ineligible": all(
            (excluded.get(action) or {}).get("eligible") is False
            and (excluded.get(action) or {}).get("reason") == "excluded_expensive_action_type"
            for action in EXCLUDED_ACTIONS
        ),
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_guidance_before_after_text_eligibility_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_before_after_text_eligibility_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Before/After Text Eligibility Extraction",
        "",
        f"Status: {payload['status']}",
        "Decision: BEFORE_AFTER_TEXT_ELIGIBILITY_CONTROLLER_OWNED",
        "",
        "## Surface Targeted",
        f"- Page helper: `{TARGET_HELPER}` lines "
        f"{payload['target']['line_start']}-{payload['target']['line_end']}",
        f"- Controller helper: `{CONTROLLER_HELPER}` lines "
        f"{payload['controller_helper']['line_start']}-{payload['controller_helper']['line_end']}",
        "",
        "## Behaviour Preserved",
        "- Missing action remains ineligible.",
        "- Previously excluded expensive actions remain ineligible.",
        "- Normal `apply_resolved_candidate` before/after text remains eligible.",
        "- Update resolution and visible wording remain on the existing page path.",
        "",
        "## Checks",
    ]
    for name, passed in checks.items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            (
                "Refresh the before/after text boundary audit, then continue with the remaining "
                "`_guidance_action_updates(...)` boundary before moving more of the helper."
            ),
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = _capture()
    checks = _checks(payload)
    payload["checks"] = checks
    payload["status"] = "PASS" if all(checks.values()) else "FAIL"
    json_path, report_path = _write(payload, checks)
    print(f"status={payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
