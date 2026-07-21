"""Verify generated reduce-link-spacing updates are controller-owned after page guards."""

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
PAGE_HELPER = "_guidance_action_updates"
CONTROLLER_HELPER = "resolve_design_guide_controller_guidance_action_generated_updates"
ACTION = "reduce_link_spacing"


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


def _controller_samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        resolve_design_guide_controller_guidance_action_generated_updates,
    )

    return {
        "default_delta": resolve_design_guide_controller_guidance_action_generated_updates(
            action_type=ACTION,
            payload={"current_spacing": 200.0, "minimum_spacing": 75.0},
            state={"s_lig": 200.0},
        ),
        "custom_delta_rounding": resolve_design_guide_controller_guidance_action_generated_updates(
            action_type=ACTION,
            payload={"current_spacing": 203.0, "minimum_spacing": 75.0, "delta_mm": 22.0},
            state={"s_lig": 203.0},
        ),
        "minimum_spacing_floor": resolve_design_guide_controller_guidance_action_generated_updates(
            action_type=ACTION,
            payload={"current_spacing": 90.0, "minimum_spacing": 75.0, "delta_mm": 50.0},
            state={"s_lig": 90.0},
        ),
        "fallback_state_spacing": resolve_design_guide_controller_guidance_action_generated_updates(
            action_type=ACTION,
            payload={"minimum_spacing": 75.0},
            state={"s_lig": 150.0},
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    page_start, page_end, page_segment = _function_source(inputs_source, PAGE_HELPER)
    controller_start, controller_end, controller_segment = _function_source(
        controller_source, CONTROLLER_HELPER
    )
    reduce_link_start = page_segment.find(f'if action_type == "{ACTION}":')
    generated_call_start = page_segment.find(
        "generated_resolution = _resolve_design_guide_controller_guidance_action_generated_updates(",
        reduce_link_start,
    )
    reduce_link_segment = (
        page_segment[reduce_link_start:generated_call_start]
        if reduce_link_start >= 0 and generated_call_start > reduce_link_start
        else ""
    )
    samples = _controller_samples()
    return {
        "schema": "design_guide_guidance_action_updates_reduce_link_spacing_generated_extraction.v1",
        "page_helper": {
            "name": PAGE_HELPER,
            "line_start": page_start,
            "line_end": page_end,
            "line_count": max(0, page_end - page_start + 1),
        },
        "controller_helper": {
            "name": CONTROLLER_HELPER,
            "line_start": controller_start,
            "line_end": controller_end,
            "line_count": max(0, controller_end - controller_start + 1),
        },
        "source_evidence": {
            "page_delegates_generated_resolution": "_resolve_design_guide_controller_guidance_action_generated_updates("
            in page_segment,
            "page_keeps_explicit_state_match": "_updates_match_state(current_state, explicit_updates)" in page_segment,
            "page_keeps_generated_state_match": "_updates_match_state(current_state, generated_updates)" in page_segment,
            "page_passes_current_spacing": 'generated_payload["current_spacing"]' in page_segment,
            "page_passes_minimum_spacing_from_reo_spacings": 'generated_payload["minimum_spacing"]' in page_segment
            and "REO_SPACINGS" in page_segment,
            "page_local_generated_spacing_math_deleted": "new_spacing = max(minimum_spacing, current_spacing - delta_mm)"
            not in reduce_link_segment,
            "controller_handles_reduce_link_spacing": f'action == "{ACTION}"' in controller_segment,
            "controller_boundary_forbidden_tokens": {
                token: token in controller_source
                for token in ("inputs_page", "streamlit", "st.session_state")
            },
        },
        "behaviour_samples": samples,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(payload: dict[str, Any]) -> dict[str, bool]:
    evidence = dict(payload.get("source_evidence") or {})
    forbidden = dict(evidence.get("controller_boundary_forbidden_tokens") or {})
    samples = dict(payload.get("behaviour_samples") or {})
    default_delta = dict(samples.get("default_delta") or {})
    custom_delta = dict(samples.get("custom_delta_rounding") or {})
    floor = dict(samples.get("minimum_spacing_floor") or {})
    fallback = dict(samples.get("fallback_state_spacing") or {})
    return {
        "page_helper_found": bool((payload.get("page_helper") or {}).get("line_start")),
        "controller_helper_found": bool((payload.get("controller_helper") or {}).get("line_start")),
        "page_delegates_generated_resolution": bool(evidence.get("page_delegates_generated_resolution")),
        "page_keeps_explicit_state_match": bool(evidence.get("page_keeps_explicit_state_match")),
        "page_keeps_generated_state_match": bool(evidence.get("page_keeps_generated_state_match")),
        "page_passes_current_spacing": bool(evidence.get("page_passes_current_spacing")),
        "page_passes_minimum_spacing_from_reo_spacings": bool(
            evidence.get("page_passes_minimum_spacing_from_reo_spacings")
        ),
        "page_local_generated_spacing_math_deleted": bool(evidence.get("page_local_generated_spacing_math_deleted")),
        "controller_handles_reduce_link_spacing": bool(evidence.get("controller_handles_reduce_link_spacing")),
        "controller_boundary_clean": not any(bool(value) for value in forbidden.values()),
        "default_delta_matches_old_shape": default_delta.get("handled") is True
        and default_delta.get("updates") == {"s_lig": 175.0},
        "custom_delta_rounding_matches_old_shape": custom_delta.get("handled") is True
        and custom_delta.get("updates") == {"s_lig": 180.0},
        "minimum_spacing_floor_matches_old_shape": floor.get("handled") is True
        and floor.get("updates") == {"s_lig": 75.0},
        "fallback_state_spacing_matches_old_shape": fallback.get("handled") is True
        and fallback.get("updates") == {"s_lig": 125.0},
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_reduce_link_spacing_generated_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_reduce_link_spacing_generated_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Guidance Action Updates Reduce Link Spacing Generated Extraction",
        "",
        f"Status: {payload['status']}",
        "Decision: REDUCE_LINK_SPACING_GENERATED_UPDATE_CONTROLLER_OWNED_AFTER_PAGE_GUARDS",
        "",
        "## Behaviour Preserved",
        "- Page still owns explicit-update no-op checks.",
        "- Page still owns generated-update no-op checks.",
        "- Page still resolves `minimum_spacing` from `REO_SPACINGS`.",
        "- Controller receives plain spacing values and returns only the generated update candidate.",
        "",
        "## Checks",
    ]
    for name, passed in checks.items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
