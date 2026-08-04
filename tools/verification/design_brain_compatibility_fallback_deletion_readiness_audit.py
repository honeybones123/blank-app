from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


FOCUSED_COMMANDS: tuple[tuple[str, str], ...] = (
    (
        "render_fallback_shell_callsite_classification",
        "tools/verification/design_brain_render_fallback_shell_callsite_classification.py",
    ),
    (
        "compute_resolver_fallback_deadness",
        "tools/verification/design_guide_compute_resolver_fallback_deadness_snapshot.py",
    ),
    (
        "restamper_proof_stamp_deadness",
        "tools/verification/design_guide_restamper_proof_stamp_deadness_snapshot.py",
    ),
    (
        "legacy_truth_surface_audit",
        "tools/verification/design_guide_inputs_page_legacy_truth_surface_audit.py",
    ),
    (
        "trace_compatible_page_shell_wrapper_cleanup",
        "tools/verification/design_guide_trace_compatible_page_shell_wrapper_cleanup_audit.py",
    ),
)


DELETED_SURFACES: dict[str, tuple[Path, str]] = {
    "old_final_visible_resolver_function": (
        INPUTS_PAGE,
        "def resolve_final_visible_design_guide_item(",
    ),
    "old_final_visible_resolver_compute_call": (
        INPUTS_PAGE,
        "final_compute_resolution = resolve_final_visible_design_guide_item(",
    ),
    "old_final_visible_resolver_render_call": (
        INPUTS_PAGE,
        "_final_visible_resolution = resolve_final_visible_design_guide_item(",
    ),
    "old_final_visible_resolver_fallback_call": (
        INPUTS_PAGE,
        "_legacy_fallback_resolution = resolve_final_visible_design_guide_item(",
    ),
    "old_final_visible_restamper_function": (
        INPUTS_PAGE,
        "def _publish_final_visible_design_guide_contract_binding(",
    ),
    "old_render_fallback_projection_helper": (
        FINAL_PUBLICATION,
        "def build_final_design_guide_render_fallback_shell_projection(",
    ),
    "old_restamper_proof_stamp_helper": (
        INPUTS_PAGE,
        "def _stamp_final_visible_final_visible_output_bridge_proof(",
    ),
    "old_trace_compatible_page_shell_generic_caller": (
        INPUTS_PAGE,
        "def _run_trace_compatible_page_shell_helper(",
    ),
}


RETAINED_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "surface": "_canonicalize_legacy_design_guide_publication_session_storage",
        "token": "def _canonicalize_legacy_design_guide_publication_session_storage(",
        "path": INPUTS_PAGE,
        "classification": "KEEP_PAGE_SHELL",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "inputs_page.py session/debug shell",
        "reason": "writes legacy session metadata with compatibility_only and legacy_non_authoritative markers; it depends on Streamlit session state and is not publication authority",
        "delete_now": False,
    },
    {
        "surface": "final_publication_cta_fallback_only markers",
        "token": "final_publication_cta_fallback_only",
        "path": INPUTS_PAGE,
        "classification": "KEEP_NON_AUTHORITATIVE_SAFETY",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "FinalDesignGuidePublication.cta proof surface",
        "reason": "marks fallback CTA projections as fallback-only/non-authoritative; deletion would remove stale-state proof before a consumer reachability proof",
        "delete_now": False,
    },
    {
        "surface": "final_publication_display_fallback_only markers",
        "token": "final_publication_display_fallback_only",
        "path": INPUTS_PAGE,
        "classification": "KEEP_NON_AUTHORITATIVE_SAFETY",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "FinalDesignGuidePublication.display proof surface",
        "reason": "marks fallback display projections as fallback-only/non-authoritative; deletion needs consumer reachability proof",
        "delete_now": False,
    },
    {
        "surface": "collapsed_guidance_replacement legacy fallback",
        "token": "collapsed_guidance_replacement_authority\"] = \"legacy_fallback\"",
        "path": INPUTS_PAGE,
        "classification": "KEEP_NON_AUTHORITATIVE_SAFETY",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "DesignGuideController collapsed replacement adapter guard",
        "reason": "exception guard returns legacy_non_authoritative compatibility data if the controller adapter fails",
        "delete_now": False,
    },
    {
        "surface": "final_visible_resolution legacy fallback",
        "token": "final_visible_resolution_authority\": \"legacy_fallback\"",
        "path": INPUTS_PAGE,
        "classification": "KEEP_NON_AUTHORITATIVE_SAFETY",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "DesignGuideController final-visible publication adapter guard",
        "reason": "exception guard preserves a non-authoritative compatibility resolution if the controller adapter fails",
        "delete_now": False,
    },
    {
        "surface": "final-visible contract binding typed fallback payload",
        "token": "_build_final_visible_contract_binding_typed_fallback_payload(",
        "path": INPUTS_PAGE,
        "classification": "KEEP_PROOF_EXCEPTION_FALLBACK",
        "missing_classification": "DELETED_AND_LOCKED_ZERO",
        "owner": "FinalDesignGuidePublication proof/error projection",
        "reason": "used only in helper-exception paths for proof payloads marked proof-only/product_driving false; deletion needs a dedicated proof-consumer migration",
        "delete_now": False,
    },
    {
        "surface": "controller compute resolver fallback shell",
        "token": "def build_design_guide_controller_compute_resolver_fallback_shell(",
        "path": CONTROLLER,
        "classification": "KEEP_CONTROLLER_OWNED_SAFETY",
        "owner": "DesignGuideController",
        "reason": "old page fallback is deleted, but controller retains a non-authoritative error shell for adapter failure safety",
        "delete_now": False,
    },
    {
        "surface": "direct shell projection proof model",
        "token": "class FinalDesignGuideDirectShellCardProjection",
        "path": FINAL_PUBLICATION,
        "classification": "KEEP_PROOF_MODEL_NON_AUTHORITATIVE",
        "owner": "design_brain.final_publication",
        "reason": "projection object is retained as proof-only/non-authoritative model; latest callsite classifier proves no tracked shell callsites remain",
        "delete_now": False,
    },
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_numbers(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status", "zero_authority_lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper or "NOT_LOCKED" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": _status_from_payload(payload)}


def _run(name: str, script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )
    return {
        "name": name,
        "script": script,
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _build_deleted_rows(sources: dict[Path, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for surface, (path, token) in DELETED_SURFACES.items():
        source = sources[path]
        lines = _line_numbers(source, token)
        rows.append(
            {
                "surface": surface,
                "path": str(path),
                "token": token,
                "present": bool(lines),
                "line_numbers": lines,
                "classification": "DELETED_AND_LOCKED_ZERO" if not lines else "UNEXPECTED_PRESENT",
                "delete_now": False,
            }
        )
    return rows


def _build_retained_rows(sources: dict[Path, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in RETAINED_SURFACES:
        path = spec["path"]
        token = spec["token"]
        lines = _line_numbers(sources[path], token)
        classification = spec["classification"] if lines else spec.get(
            "missing_classification",
            "MISSING_RETAINED_SURFACE",
        )
        rows.append(
            {
                "surface": spec["surface"],
                "path": str(path),
                "token": token,
                "present": bool(lines),
                "line_numbers": lines,
                "classification": classification,
                "owner": spec["owner"],
                "reason": spec["reason"],
                "delete_now": bool(spec["delete_now"]) and bool(lines),
            }
        )
    return rows


def _latest_artifact_summary() -> dict[str, Any]:
    prefixes = {
        "render_fallback_shell_callsite_classification": "design_brain_render_fallback_shell_callsite_classification",
        "compute_resolver_fallback_deadness": "design_guide_compute_resolver_fallback_deadness",
        "restamper_proof_stamp_deadness": "design_guide_restamper_proof_stamp_deadness",
        "legacy_truth_surface_audit": "design_guide_inputs_page_legacy_truth_surface_audit",
        "trace_compatible_page_shell_wrapper_cleanup": "design_guide_trace_compatible_page_shell_wrapper_cleanup_audit",
        "zero_authority_inventory_lock": "design_brain_inputs_page_zero_authority_inventory_lock",
        "shared_compatibility_bridge_fallback_lock": "design_brain_shared_compatibility_bridge_fallback_lock",
        "independence_lock": "design_guide_independence_lock",
        "render_bridge_lock": "design_guide_render_bridge_lock",
        "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    }
    return {name: _latest_payload(prefix) for name, prefix in prefixes.items()}


def _snapshot(command_results: list[dict[str, Any]]) -> dict[str, Any]:
    sources = {
        INPUTS_PAGE: _read(INPUTS_PAGE),
        FINAL_PUBLICATION: _read(FINAL_PUBLICATION),
        CONTROLLER: _read(CONTROLLER),
    }
    deleted_rows = _build_deleted_rows(sources)
    retained_rows = _build_retained_rows(sources)
    latest = _latest_artifact_summary()

    blockers: list[str] = []
    for row in command_results:
        if row.get("status") != "PASS":
            blockers.append(f"focused command failed: {row['name']}")
    for row in deleted_rows:
        if row.get("present"):
            blockers.append(f"deleted surface unexpectedly present: {row['surface']}")
    for row in retained_rows:
        if (
            not row.get("present")
            and row.get("classification") != "DELETED_AND_LOCKED_ZERO"
        ):
            blockers.append(f"expected retained surface missing: {row['surface']}")

    render_summary = dict(
        (latest["render_fallback_shell_callsite_classification"].get("payload") or {}).get("summary") or {}
    )
    if int(render_summary.get("safe_delete_now") or 0) != 0:
        blockers.append("render fallback shell classifier reports safe_delete_now candidates; handle them before locking this audit")
    if int(render_summary.get("needs_more_proof") or 0) != 0:
        blockers.append("render fallback shell classifier reports needs_more_proof candidates")

    compute_payload = latest["compute_resolver_fallback_deadness"].get("payload") or {}
    compute_capture = dict(compute_payload.get("capture") or {})
    compute_checks = dict(compute_capture.get("checks") or {})
    if compute_checks.get("old_fallback_call_deleted") is not True:
        blockers.append("old compute resolver fallback call is not deleted")
    if (
        compute_capture.get("controller_shell_retained_non_authoritative") is not True
        and compute_capture.get("fallback_dead_now") is not True
    ):
        blockers.append("controller compute resolver fallback shell is neither retained/non-authoritative nor dead")

    restamper_payload = latest["restamper_proof_stamp_deadness"].get("payload") or {}
    if restamper_payload.get("proof_stamp_surface_locked_zero") is not True:
        blockers.append("restamper proof stamp surface is not locked zero")

    for required_name in (
        "zero_authority_inventory_lock",
        "independence_lock",
        "render_bridge_lock",
        "compute_bridge_lock",
    ):
        if latest[required_name].get("status") != "PASS":
            blockers.append(f"latest {required_name} is not PASS")

    delete_now_rows = [
        row
        for row in retained_rows
        if row.get("delete_now") or row.get("classification") == "DELETE_NOW"
    ]
    unknown_rows = [
        row
        for row in retained_rows
        if str(row.get("classification") or "").startswith("UNKNOWN")
        or row.get("classification") == "MISSING_RETAINED_SURFACE"
    ]
    if unknown_rows:
        blockers.append("unknown or missing retained surfaces remain")

    status = "PASS" if not blockers else "FAIL"
    recommendation = (
        "No historical compatibility/fallback surface is safe to delete now; remaining surfaces are bounded, non-authoritative safety/proof/session/render shells."
        if not delete_now_rows
        else "Delete the DELETE_NOW rows one at a time with focused deadness proof."
    )
    return {
        "schema": "design_brain_compatibility_fallback_deletion_readiness_audit.v1",
        "created_at": time.strftime("%Y-%m-%dT%H-%M-%S"),
        "status": status,
        "deleted_surfaces": deleted_rows,
        "retained_surfaces": retained_rows,
        "delete_now_count": len(delete_now_rows),
        "delete_now_surfaces": [row["surface"] for row in delete_now_rows],
        "unknown_count": len(unknown_rows),
        "unknown_surfaces": [row["surface"] for row in unknown_rows],
        "latest": {
            name: {"status": row.get("status"), "path": row.get("path")}
            for name, row in latest.items()
        },
        "latest_render_callsite_summary": render_summary,
        "latest_compute_fallback_decision": compute_capture.get("decision"),
        "latest_controller_shell_retained_non_authoritative": compute_capture.get(
            "controller_shell_retained_non_authoritative"
        ),
        "command_results": command_results,
        "blockers": blockers,
        "recommendation": recommendation,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Design Brain Compatibility / Fallback Deletion Readiness Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Delete-now candidates: `{payload['delete_now_count']}`",
        f"Unknown surfaces: `{payload['unknown_count']}`",
        "",
        "## Executive Summary",
        "",
        payload["recommendation"],
        "",
        "## Deleted / Locked-Zero Historical Surfaces",
        "",
        "| Surface | Present | Classification |",
        "|---|---:|---|",
    ]
    for row in payload.get("deleted_surfaces") or []:
        lines.append(f"| `{row['surface']}` | `{row['present']}` | `{row['classification']}` |")
    lines.extend(
        [
            "",
            "## Retained Compatibility / Fallback Surfaces",
            "",
            "| Surface | Classification | Owner | Delete Now | Reason |",
            "|---|---|---|---:|---|",
        ]
    )
    for row in payload.get("retained_surfaces") or []:
        lines.append(
            f"| `{row['surface']}` | `{row['classification']}` | `{row.get('owner')}` | "
            f"`{row['delete_now']}` | {row.get('reason')} |"
        )
    lines.extend(["", "## Latest Evidence", ""])
    for name, row in (payload.get("latest") or {}).items():
        lines.append(f"- `{name}`: `{row.get('status')}` ({row.get('path')})")
    lines.extend(["", "## Focused Commands", ""])
    for row in payload.get("command_results") or []:
        lines.append(f"- `{row['name']}`: `{row['status']}`")
    if payload.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    command_results = [_run(name, script) for name, script in FOCUSED_COMMANDS]
    payload = _snapshot(command_results)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_compatibility_fallback_deletion_readiness_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_compatibility_fallback_deletion_readiness_audit_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_brain_compatibility_fallback_deletion_readiness_audit {payload['status']}")
    print(f"delete_now_count={payload['delete_now_count']}")
    print(f"unknown_count={payload['unknown_count']}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if payload.get("blockers"):
        print("blockers=" + "; ".join(payload["blockers"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
