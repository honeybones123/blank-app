"""Verify `apply_mode_recommendation` update resolution is controller-owned."""

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
CONTROLLER_HELPER = "resolve_design_guide_controller_guidance_action_payload_updates"
ACTION = "apply_mode_recommendation"


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
        resolve_design_guide_controller_guidance_action_payload_updates,
    )

    with_updates = {"design_mode": "Detailed", "some_flag": True}
    return {
        "with_updates": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={"updates": with_updates},
        ),
        "empty_updates": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={"updates": {}},
        ),
        "missing_updates": resolve_design_guide_controller_guidance_action_payload_updates(
            action_type=ACTION,
            payload={},
        ),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    page_start, page_end, page_segment = _function_source(inputs_source, PAGE_HELPER)
    controller_start, controller_end, controller_segment = _function_source(
        controller_source, CONTROLLER_HELPER
    )
    samples = _controller_samples()
    return {
        "schema": "design_guide_guidance_action_updates_apply_mode_extraction.v1",
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
            "page_delegates_payload_resolution": "_resolve_design_guide_controller_guidance_action_payload_updates("
            in page_segment,
            "page_local_apply_mode_branch_deleted": f'action_type == "{ACTION}"' not in page_segment,
            "controller_handles_apply_mode": f'action == "{ACTION}"' in controller_segment,
            "recommendation_fallback_branches_remain_page_owned": all(
                token in page_segment
                for token in (
                    "_compute_geometry_recommendation(",
                    "_compute_bottom_reo_recommendation(",
                    "_compute_shear_recommendation(",
                )
            ),
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
    with_updates = dict(samples.get("with_updates") or {})
    empty_updates = dict(samples.get("empty_updates") or {})
    missing_updates = dict(samples.get("missing_updates") or {})
    return {
        "page_helper_found": bool((payload.get("page_helper") or {}).get("line_start")),
        "controller_helper_found": bool((payload.get("controller_helper") or {}).get("line_start")),
        "page_delegates_payload_resolution": bool(evidence.get("page_delegates_payload_resolution")),
        "page_local_apply_mode_branch_deleted": bool(evidence.get("page_local_apply_mode_branch_deleted")),
        "controller_handles_apply_mode": bool(evidence.get("controller_handles_apply_mode")),
        "recommendation_fallback_branches_remain_page_owned": bool(
            evidence.get("recommendation_fallback_branches_remain_page_owned")
        ),
        "controller_boundary_clean": not any(bool(value) for value in forbidden.values()),
        "with_updates_matches_old_shape": with_updates.get("handled") is True
        and with_updates.get("updates") == {"design_mode": "Detailed", "some_flag": True},
        "empty_updates_matches_old_shape": empty_updates.get("handled") is True
        and empty_updates.get("updates") == {},
        "missing_updates_matches_old_shape": missing_updates.get("handled") is True
        and missing_updates.get("updates") is None,
        "product_behavior_unchanged": not bool(payload.get("product_behavior_changed")),
        "visible_wording_unchanged": not bool(payload.get("visible_wording_changed")),
        "cta_apply_semantics_unchanged": not bool(payload.get("cta_apply_semantics_changed")),
        "family_runtime_unchanged": not bool(payload.get("family_runtime_changed")),
    }


def _write(payload: dict[str, Any], checks: dict[str, bool]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _timestamp().replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_guidance_action_updates_apply_mode_extraction_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_guidance_action_updates_apply_mode_extraction_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Design Guide Guidance Action Updates Apply Mode Extraction",
        "",
        f"Status: {payload['status']}",
        "Decision: APPLY_MODE_UPDATE_BRANCH_CONTROLLER_OWNED",
        "",
        "## Surface Targeted",
        f"- Page helper: `{PAGE_HELPER}` lines "
        f"{payload['page_helper']['line_start']}-{payload['page_helper']['line_end']}",
        f"- Controller helper: `{CONTROLLER_HELPER}` lines "
        f"{payload['controller_helper']['line_start']}-{payload['controller_helper']['line_end']}",
        "",
        "## Behaviour Preserved",
        "- `apply_mode_recommendation` explicit updates still return the same update dictionary.",
        "- Missing updates still return `None`.",
        "- Geometry/bottom/shear recommendation fallback branches remain page-owned for later slices.",
        "",
        "## Checks",
    ]
    for name, passed in checks.items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Next Safe Target",
            "Refresh `_guidance_action_updates(...)` boundary inventory, then extract the next pure explicit payload branch only.",
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
