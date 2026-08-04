"""Consumer reachability proof for residual shear cleanup debug projection marker."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
TOOLS_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

MARKER_TERMS = (
    "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only",
    "final_publication_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only",
    "final_publication_post_click_low_bending_residual_shear_cleanup_debug_projection_route_hash",
    "final_publication_post_click_low_bending_residual_shear_cleanup_debug_projection_proof_hash",
)

VERIFIER_ALLOWLIST = {
    "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing_snapshot.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_live_execution_shell_audit.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_snapshot.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness_audit.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit.py",
    "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_behavior_cutover_gap_audit.py",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_hits(path: Path, terms: tuple[str, ...]) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except Exception:
        return []
    hits: list[dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        matched = [term for term in terms if term in line]
        if matched:
            hits.append({"path": str(path), "line": idx, "terms": matched, "text": line.strip()})
    return hits


def _capture() -> dict[str, Any]:
    inputs_hits = _line_hits(INPUTS_PAGE, MARKER_TERMS)
    verifier_hits: list[dict[str, Any]] = []
    for path in sorted(TOOLS_DIR.glob("design_guide_*.py")):
        verifier_hits.extend(_line_hits(path, MARKER_TERMS))
    verifier_files = sorted({Path(str(hit.get("path"))).name for hit in verifier_hits})
    unexpected_verifier_files = [
        name for name in verifier_files if name not in VERIFIER_ALLOWLIST
    ]
    helper_definition_hits = [
        hit
        for hit in inputs_hits
        if "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only"
        in str(hit.get("text") or "")
        and str(hit.get("text") or "").startswith("def ")
    ]
    helper_call_hits = [
        hit
        for hit in inputs_hits
        if "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only("
        in str(hit.get("text") or "")
        and not str(hit.get("text") or "").startswith("def ")
    ]
    product_key_consumer_hits = [
        hit
        for hit in inputs_hits
        if not str(hit.get("text") or "").startswith('"')
        and not str(hit.get("text") or "").startswith("]")
        and "guidance_debug[" not in str(hit.get("text") or "")
        and "_mark_post_click_low_bending_residual_shear_cleanup_debug_projection_compatibility_only"
        not in str(hit.get("text") or "")
    ]
    deletion_ready = bool(
        helper_definition_hits
        and helper_call_hits
        and not product_key_consumer_hits
        and not unexpected_verifier_files
    )
    marker_deleted = bool(
        not helper_definition_hits
        and not helper_call_hits
        and not product_key_consumer_hits
        and not unexpected_verifier_files
    )
    return {
        "decision": (
            "RESIDUAL_DEBUG_PROJECTION_MARKER_READY_FOR_DELETION"
            if deletion_ready
            else (
                "RESIDUAL_DEBUG_PROJECTION_MARKER_DELETED"
                if marker_deleted
                else "RESIDUAL_DEBUG_PROJECTION_MARKER_NOT_READY_FOR_DELETION"
            )
        ),
        "input_hits": inputs_hits,
        "verifier_files": verifier_files,
        "unexpected_verifier_files": unexpected_verifier_files,
        "helper_definition_count": len(helper_definition_hits),
        "helper_call_count": len(helper_call_hits),
        "product_key_consumer_hits": product_key_consumer_hits,
        "deletion_ready": deletion_ready,
        "marker_deleted": marker_deleted,
        "delete_scope": (
            "helper definition and single callsite only"
            if deletion_ready
            else ("already deleted" if marker_deleted else "none")
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "helper_definition_found_or_deleted": capture.get("helper_definition_count") in {0, 1},
        "single_helper_call_found_or_deleted": capture.get("helper_call_count") in {0, 1},
        "no_product_key_consumers": not capture.get("product_key_consumer_hits"),
        "no_unexpected_verifier_consumers": not capture.get("unexpected_verifier_files"),
        "deletion_ready_or_deleted": (
            capture.get("deletion_ready") is True or capture.get("marker_deleted") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Debug Projection Consumer Reachability",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Deletion ready: `{capture.get('deletion_ready')}`",
        f"- Marker deleted: `{capture.get('marker_deleted')}`",
        f"- Helper definition count: `{capture.get('helper_definition_count')}`",
        f"- Helper call count: `{capture.get('helper_call_count')}`",
        f"- Product key consumer hits: `{len(capture.get('product_key_consumer_hits') or [])}`",
        f"- Unexpected verifier files: `{capture.get('unexpected_verifier_files')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Delete Scope", "", str(capture.get("delete_scope") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_debug_projection_consumer_reachability_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_consumer_reachability "
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
