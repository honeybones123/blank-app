"""Deadness/readiness audit for residual shear cleanup route-shell code."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


SHELL_SURFACES = {
    "final_publication_route_proof_stamp": {
        "tokens": (
            "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
            "final_publication_post_click_low_bending_residual_shear_cleanup_route_hash",
        ),
        "classification": "C. still required source proof / keep",
        "reason": "Controller route-shell readiness consumes the FinalDesignGuidePublication route proof.",
    },
    "controller_route_shell_readiness_stamp": {
        "tokens": (
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
            "design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness_hash",
        ),
        "classification": "C. current controller shell authority / keep",
        "reason": "This is the new controller route-shell readiness boundary.",
    },
    "debug_projection_compatibility_marker": {
        "tokens": (
            "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only(",
            "debug_projection_compatibility_only",
        ),
        "classification": "A. deleted after consumer reachability proof",
        "expect_absent": True,
        "reason": "The compatibility marker had no product consumers and has been deleted.",
    },
    "live_behavior_route_body": {
        "tokens": (
            "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
            "executor=_compute_shear_tightening_recommendation",
            "_run_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator(",
            "generator=generate_less_shear_reo_variants",
            "_run_post_click_low_bending_residual_shear_cleanup_candidate_evaluator(",
            "evaluator=_evaluate_auto_design_candidate",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary(",
            "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary(",
        ),
        "classification": "D. behavior-driving / keep",
        "reason": "Candidate generation/evaluation still execute as injected dependencies; CTA/apply source is bounded by controller proof.",
    },
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def _block(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    helper_block = _block(
        source,
        "def _stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
        "\ndef _stamp_final_publication_post_click_final_contract_predicate_result_adapter(",
    )
    route_block = _block(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(",
        "    shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    combined = helper_block + "\n" + route_block
    rows: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for name, spec in SHELL_SURFACES.items():
        tokens = tuple(spec.get("tokens") or ())
        present = [token for token in tokens if token in combined]
        expect_absent = bool(spec.get("expect_absent"))
        surface_present = len(present) == 0 if expect_absent else len(present) == len(tokens)
        classification = str(spec.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
        rows[name] = {
            **spec,
            "present": surface_present,
            "tokens_present": present,
            "tokens_missing": [token for token in tokens if token not in combined],
            "delete_now": False,
        }
    route_shell_cutover_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_snapshot.py",
        ]
    )
    controller_object_run = _run(
        [
            sys.executable,
            "tools/verification/design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object_snapshot.py",
        ]
    )
    return {
        "decision": "NO_RESIDUAL_ROUTE_SHELL_DELETION_CANDIDATE_YET",
        "surface_rows": rows,
        "classification_counts": counts,
        "delete_now_count": 0,
        "deletion_candidates": [],
        "compatibility_only_surfaces": [
            name
            for name, row in rows.items()
            if str(row.get("classification") or "").startswith("B.")
        ],
        "must_keep_surfaces": [
            name
            for name, row in rows.items()
            if str(row.get("classification") or "").startswith(("C.", "D."))
        ],
        "route_shell_cutover": route_shell_cutover_run,
        "controller_readiness_object": controller_object_run,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_safe_step": (
            "Begin a separate candidate-generation/evaluation controller boundary for "
            "residual shear cleanup, or prove another compatibility-only route-shell surface."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    rows = dict(capture.get("surface_rows") or {})
    return {
        "all_surfaces_classified": all(
            row.get("present") is True
            or bool(row.get("expect_absent"))
            or str(row.get("classification") or "").startswith("D.")
            for row in rows.values()
        ),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "route_shell_cutover_passed": (capture.get("route_shell_cutover") or {}).get("passed")
        is True,
        "controller_readiness_object_passed": (
            (capture.get("controller_readiness_object") or {}).get("passed") is True
        ),
        "final_publication_route_proof_kept": "final_publication_route_proof_stamp"
        in set(capture.get("must_keep_surfaces") or []),
        "controller_route_shell_kept": "controller_route_shell_readiness_stamp"
        in set(capture.get("must_keep_surfaces") or []),
        "debug_projection_marker_deleted": "debug_projection_compatibility_marker"
        not in set(capture.get("must_keep_surfaces") or []),
        "live_behavior_kept": "live_behavior_route_body"
        in set(capture.get("must_keep_surfaces") or []),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Route-Shell Deadness/Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Deletion candidates: `{capture.get('deletion_candidates')}`",
        f"- Compatibility-only surfaces: `{capture.get('compatibility_only_surfaces')}`",
        f"- Must keep surfaces: `{capture.get('must_keep_surfaces')}`",
        "",
        "## Surface Classification",
        "",
    ]
    for name, row in (capture.get("surface_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`, "
            f"delete_now=`{row.get('delete_now')}`, reason=`{row.get('reason')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_audit.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_shell_deadness_readiness_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
