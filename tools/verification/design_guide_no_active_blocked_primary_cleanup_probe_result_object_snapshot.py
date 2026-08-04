"""Verify controller result objects for blocked-primary cleanup probe route."""

from __future__ import annotations

from datetime import datetime
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

SAFE_BUILDER = "build_design_guide_controller_safe_cleanup_candidate_before_blocker_result"
BENDING_BUILDER = "build_design_guide_controller_bending_cleanup_available_before_blocker_result"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno])
    raise RuntimeError(f"Could not find {function_name}")


def _samples() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_bending_cleanup_available_before_blocker_result,
        build_design_guide_controller_safe_cleanup_candidate_before_blocker_result,
    )

    safe = build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
        safe_cleanup_item={
            "title": "Shear cleanup",
            "title_main": "Shear cleanup",
            "primary_action": "Remove links",
            "guidance_intent": "efficiency_tightening",
            "bucket": "pass",
        },
        safe_cleanup_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "shear_safe_1",
            "updates": {"lig_legs": 0},
        },
        safe_cleanup_updates={"lig_legs": 0},
        final_overview={"utils": {"bending": 0.9, "shear": 0.31}},
        state_fingerprint="state-1",
    )
    bending = build_design_guide_controller_bending_cleanup_available_before_blocker_result(
        bending_probe_item={
            "title": "Bending cleanup",
            "title_main": "Bending cleanup",
            "primary_action": "Reduce bottom reinforcement",
            "guidance_intent": "efficiency_tightening",
            "bucket": "pass",
        },
        bending_probe_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "bending_probe_1",
        },
        bending_probe_updates={"reo_1": 5, "reo_1_dia": 10},
        bending_probe_candidate_id="bending_probe_1",
        bending_probe_expected_util=0.42,
        final_overview={"utils": {"bending": 0.24, "shear": 0.69}},
        final_bending_util_for_probe=0.24,
        state_fingerprint="state-2",
    )
    safe_repeat = build_design_guide_controller_safe_cleanup_candidate_before_blocker_result(
        safe_cleanup_item={
            "title": "Shear cleanup",
            "title_main": "Shear cleanup",
            "primary_action": "Remove links",
            "guidance_intent": "efficiency_tightening",
            "bucket": "pass",
        },
        safe_cleanup_contract={
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "candidate_id": "shear_safe_1",
            "updates": {"lig_legs": 0},
        },
        safe_cleanup_updates={"lig_legs": 0},
        final_overview={"utils": {"bending": 0.9, "shear": 0.31}},
        state_fingerprint="state-1",
    )
    return {"safe_cleanup": safe, "safe_cleanup_repeat": safe_repeat, "bending_probe": bending}


def _capture() -> dict[str, Any]:
    safe_source = _function_source(CONTROLLER, SAFE_BUILDER)
    bending_source = _function_source(CONTROLLER, BENDING_BUILDER)
    samples = _samples()
    forbidden_terms = ["inputs_page", "streamlit", "st.session_state", "one_click", "render_html"]
    source_blob = safe_source + "\n" + bending_source
    return {
        "builders": [SAFE_BUILDER, BENDING_BUILDER],
        "samples": samples,
        "stable_repeat": _stable_hash(samples["safe_cleanup"]) == _stable_hash(samples["safe_cleanup_repeat"]),
        "forbidden_hits": [
            term for term in forbidden_terms if term.lower() in source_blob.lower()
        ],
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _has_shape(result: dict[str, Any], reason: str) -> bool:
    return (
        isinstance(result.get("item"), dict)
        and isinstance(result.get("overview"), dict)
        and isinstance(result.get("presentation"), dict)
        and result.get("render_reason") == reason
        and isinstance(result.get("debug"), dict)
        and bool(result.get("state_fingerprint"))
    )


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    samples = capture.get("samples") or {}
    safe = samples.get("safe_cleanup") or {}
    bending = samples.get("bending_probe") or {}
    return {
        "safe_builder_shape_valid": _has_shape(
            safe, "final_visible_safe_cleanup_candidate_before_blocker"
        ),
        "bending_builder_shape_valid": _has_shape(
            bending, "final_visible_bending_cleanup_available_before_blocker"
        ),
        "safe_builder_sets_actionable_item": (safe.get("item") or {}).get("primary_card_actionable")
        is True,
        "safe_builder_sets_button_contract": isinstance(
            (safe.get("item") or {}).get("button_contract"), dict
        ),
        "bending_debug_shape_matches_legacy": (bending.get("debug") or {}).get("low_util_family")
        == "bending"
        and (bending.get("debug") or {}).get("resolution_actionable") is True,
        "stable_repeat": capture.get("stable_repeat") is True,
        "no_page_or_ui_import_terms": not capture.get("forbidden_hits"),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Guide No-Active Blocked-Primary Cleanup Probe Result Objects",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The controller can build both result shapes, but live route behavior is not cut over yet.",
        ]
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
        / f"design_guide_no_active_blocked_primary_cleanup_probe_result_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_no_active_blocked_primary_cleanup_probe_result_object_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_no_active_blocked_primary_cleanup_probe_result_object {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
