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
    ("render_fallback_shell_helper_deletion", "tools/verification/design_brain_render_fallback_shell_helper_deletion.py"),
    (
        "render_fallback_shell_callsite_classification",
        "tools/verification/design_brain_render_fallback_shell_callsite_classification.py",
    ),
    (
        "compatibility_fallback_deletion_readiness",
        "tools/verification/design_brain_compatibility_fallback_deletion_readiness_audit.py",
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


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


def _run(name: str, script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    return {
        "name": name,
        "script": script,
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


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


def _source_checks() -> dict[str, bool]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    controller_source = _read(CONTROLLER)
    return {
        "old_render_fallback_projection_helper_deleted": "build_final_design_guide_render_fallback_shell_projection" not in final_source
        and "build_final_design_guide_render_fallback_shell_projection" not in inputs_source,
        "direct_shell_projection_helper_exists": "FinalDesignGuideDirectShellCardProjection" in final_source
        and "build_final_design_guide_direct_shell_card_projection" in final_source,
        "inputs_shell_has_no_direct_shell_projection_calls": "_build_final_design_guide_direct_shell_card_projection(" not in inputs_source,
        "controller_compute_resolver_fallback_shell_exists": "build_design_guide_controller_compute_resolver_fallback_shell" in controller_source,
        "fallback_shells_marked_non_authoritative": '"non_authoritative": True' in final_source
        and '"product_driving": False' in final_source
        and '"render_driving": False' in final_source
        and "proof_only=True" in final_source,
        "fallback_shells_marked_fallback_only": '"fallback_only": True' in final_source,
        "compatibility_markers_remain_explicit": '"compatibility_only": True' in final_source
        and '"legacy_non_authoritative": True' in final_source
        and '"compatibility_only": True' in controller_source,
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Compatibility Bridges / Fallbacks Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers compatibility bridges and fallback shells. These paths may be retained only when explicitly non-authoritative, bounded, and covered by callsite/deadness proof.",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in snapshot.get("source_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Commands", ""])
    for row in snapshot.get("focused_commands") or []:
        lines.append(f"- `{row['name']}`: `{row['status']}`")
    lines.extend(["", "## Latest Callsite Classification", ""])
    classification = dict(snapshot.get("latest_callsite_classification") or {})
    lines.append(f"- status: `{classification.get('status')}`")
    lines.append(f"- path: `{classification.get('path')}`")
    summary = dict(classification.get("summary") or {})
    for key, value in summary.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Latest Deletion Readiness", ""])
    readiness = dict(snapshot.get("latest_deletion_readiness") or {})
    lines.append(f"- status: `{readiness.get('status')}`")
    lines.append(f"- path: `{readiness.get('path')}`")
    lines.append(f"- delete-now count: `{readiness.get('delete_now_count')}`")
    lines.append(f"- unknown count: `{readiness.get('unknown_count')}`")
    lines.append(f"- recommendation: {readiness.get('recommendation')}")
    if snapshot.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Resolve the three `needs_more_proof` direct-shell callsites by proving whether each is page-shell fallback plumbing, controller-owned fallback materialization, or dead. Do not delete until the callsite classifier reaches zero `needs_more_proof`.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    command_results = [_run(name, script) for name, script in FOCUSED_COMMANDS]
    helper_deletion = _latest_payload("design_brain_render_fallback_shell_helper_deletion")
    callsite_classification = _latest_payload("design_brain_render_fallback_shell_callsite_classification")
    deletion_readiness = _latest_payload("design_brain_compatibility_fallback_deletion_readiness_audit")
    zero_authority = _latest_payload("design_brain_inputs_page_zero_authority_inventory_lock")
    source_checks = _source_checks()

    blockers: list[str] = []
    for key, passed in source_checks.items():
        if not passed:
            blockers.append(f"source check failed: {key}")
    for result in command_results:
        if result.get("status") != "PASS":
            blockers.append(f"focused command failed: {result['name']}")
    if helper_deletion.get("status") != "PASS":
        blockers.append("render fallback shell helper deletion proof is not PASS")
    classification_payload = dict(callsite_classification.get("payload") or {})
    classification_summary = dict(classification_payload.get("summary") or {})
    if callsite_classification.get("status") != "PASS":
        blockers.append("render fallback shell callsite classification is not PASS")
    needs_more_proof = int(classification_summary.get("needs_more_proof") or 0)
    if needs_more_proof:
        blockers.append(f"render fallback shell callsites still need proof: {needs_more_proof}")
    deletion_payload = dict(deletion_readiness.get("payload") or {})
    if deletion_readiness.get("status") != "PASS":
        blockers.append("compatibility/fallback deletion-readiness audit is not PASS")
    if int(deletion_payload.get("unknown_count") or 0):
        blockers.append(
            "compatibility/fallback deletion-readiness audit has unknown surfaces: "
            + ", ".join(str(item) for item in deletion_payload.get("unknown_surfaces") or [])
        )
    if zero_authority.get("status") != "PASS":
        blockers.append("zero-authority inventory lock is not PASS")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_compatibility_bridge_fallback_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_compatibility_bridge_fallback_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_compatibility_bridge_fallback_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "compatibility bridges/fallbacks",
        "source_checks": source_checks,
        "focused_commands": command_results,
        "latest_helper_deletion": {
            "status": helper_deletion.get("status"),
            "path": helper_deletion.get("path"),
        },
        "latest_callsite_classification": {
            "status": callsite_classification.get("status"),
            "path": callsite_classification.get("path"),
            "summary": classification_summary,
            "failures": classification_payload.get("failures") or [],
        },
        "latest_deletion_readiness": {
            "status": deletion_readiness.get("status"),
            "path": deletion_readiness.get("path"),
            "delete_now_count": deletion_payload.get("delete_now_count"),
            "unknown_count": deletion_payload.get("unknown_count"),
            "recommendation": deletion_payload.get("recommendation"),
        },
        "latest_zero_authority": {
            "status": zero_authority.get("status"),
            "path": zero_authority.get("path"),
        },
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_compatibility_bridge_fallback_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
