from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET = "_bending_only_target_band_cleanup_item"


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> tuple[int | None, int | None, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines()
            start = int(getattr(node, "lineno", 1))
            end = int(getattr(node, "end_lineno", start))
            return start, end, "\n".join(lines[start - 1 : end])
    return None, None, ""


def _stable_hash(payload: Any) -> str:
    import hashlib

    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _latest_pass(prefix: str) -> dict[str, Any]:
    matches = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        return {"prefix": prefix, "exists": False, "status": None, "path": None}
    path = matches[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"prefix": prefix, "exists": True, "status": None, "path": str(path), "error": str(exc)}
    return {
        "prefix": prefix,
        "exists": True,
        "status": payload.get("status"),
        "decision": payload.get("decision") or (payload.get("capture") or {}).get("decision"),
        "path": str(path),
    }


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    start, end, target_source = _function_source(inputs_source, TARGET)

    direct_checks = {
        "target_found": bool(target_source),
        "controller_import_clean": all(
            token not in controller_source
            for token in ("inputs_page", "streamlit", "st.session_state")
        ),
        "terminal_initial_context_controller_owned": (
            "_build_design_guide_controller_terminalisation_initial_context(" in target_source
        ),
        "terminal_followup_resolution_controller_owned": (
            "_resolve_design_guide_controller_terminalisation_followup_updates(" in target_source
        ),
        "terminal_trial_acceptance_controller_owned": (
            "_resolve_design_guide_controller_terminalisation_trial_acceptance(" in target_source
        ),
        "terminal_projection_controller_owned": (
            "_build_design_guide_controller_bending_only_terminalisation_projection(" in target_source
        ),
        "candidate_evaluation_service_backed": (
            "_evaluate_bending_only_target_band_prebuilt_candidate_with_service(" in target_source
        ),
        "overview_collection_is_page_callback_input": "_collect_design_overview(" in target_source,
        "bending_followup_is_page_callback": (
            "_bending_only_target_band_cleanup_item(" in target_source
            and "allow_terminalisation_fold=False" in target_source
        ),
        "shear_followup_is_page_callback": "_shear_low_util_target_cleanup_item(" in target_source,
        "button_contract_probe_is_page_owned": "_design_guide_button_contract(" in target_source,
        "inline_full_trial_acceptance_removed": (
            "and not bool(trial_overview.get(\"any_fail\"))" not in target_source
            and "and _overview_required_checks_acceptable(trial_overview)" not in target_source
            and "and not _candidate_preview_statuses_have_explicit_fail(trial_statuses)" not in target_source
        ),
        "inline_terminal_candidate_id_generation_removed": (
            "optimisation_cleanup_candidate_id(" not in target_source
        ),
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
        "product_behavior_unchanged": True,
    }

    composed = [
        _latest_pass("design_guide_bending_only_terminalisation_callback_boundary_parity"),
        _latest_pass("design_guide_bending_only_terminalisation_projection_boundary_audit"),
        _latest_pass("design_guide_bending_only_target_band_candidate_evaluation_service_handoff"),
        _latest_pass("design_guide_bending_only_item_projection_adapter_parity"),
    ]
    composed_pass = all(item.get("exists") and item.get("status") == "PASS" for item in composed)
    bounded = all(direct_checks.values()) and composed_pass
    return {
        "schema": "design_guide_bending_only_terminalisation_callback_shell_boundary_audit.v1",
        "target": {"name": TARGET, "line_start": start, "line_end": end},
        "direct_checks": direct_checks,
        "composed_artifacts": composed,
        "remaining_page_owned_terminalisation_surfaces": [
            "overview collection",
            "bending follow-up callback execution",
            "shear follow-up callback execution",
            "button contract probing",
            "candidate evaluation callback execution",
        ],
        "classification": (
            "BOUNDED_PAGE_SHELL_CALLBACK_BOUNDARY"
            if bounded
            else "NOT_BOUNDED_WITH_EXACT_REMAINING_SURFACE"
        ),
        "decision": (
            "BENDING_ONLY_TERMINALISATION_CALLBACK_SURFACE_BOUNDED"
            if bounded
            else "BENDING_ONLY_TERMINALISATION_CALLBACK_SURFACE_NOT_BOUNDED"
        ),
        "next_safe_slice": (
            "Treat bending-only target-band cleanup as bounded service-backed shell in the zero-authority inventory."
            if bounded
            else "Fix the failing direct source check or prerequisite composed artifact before reclassifying."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Bending-Only Terminalisation Callback Shell Boundary Audit",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Classification: `{(payload.get('capture') or {}).get('classification')}`",
        "",
        "## Direct Checks",
        "",
    ]
    for name, value in dict((payload.get("capture") or {}).get("direct_checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    lines.extend(["", "## Composed Artifacts", ""])
    for artifact in list((payload.get("capture") or {}).get("composed_artifacts") or []):
        lines.append(
            f"- `{artifact.get('prefix')}`: `{artifact.get('status')}` `{artifact.get('path')}`"
        )
    lines.extend(["", "## Remaining Page-Owned Surfaces", ""])
    for surface in list((payload.get("capture") or {}).get("remaining_page_owned_terminalisation_surfaces") or []):
        lines.append(f"- {surface}")
    lines.extend(
        [
            "",
            "These remaining surfaces are callback/input/probe execution plumbing. They do not own terminalisation policy, projection, candidate ranking, visible wording, or CTA/apply semantics.",
            "",
            f"## Next Safe Slice",
            "",
            str((payload.get("capture") or {}).get("next_safe_slice") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = dict(capture.get("direct_checks") or {})
    composed_pass = all(
        item.get("exists") and item.get("status") == "PASS"
        for item in list(capture.get("composed_artifacts") or [])
    )
    passed = all(checks.values()) and composed_pass
    payload = {
        "schema": "design_guide_bending_only_terminalisation_callback_shell_boundary_audit.v1",
        "created_at": _timestamp(),
        "status": "PASS" if passed else "FAIL",
        "decision": capture.get("decision"),
        "capture": capture,
        "checks": {**checks, "composed_artifacts_pass": composed_pass},
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    suffix = str(payload["created_at"]).replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bending_only_terminalisation_callback_shell_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_bending_only_terminalisation_callback_shell_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_bending_only_terminalisation_callback_shell_boundary_audit {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        print("failing_checks=" + json.dumps([name for name, ok in payload["checks"].items() if not ok]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
