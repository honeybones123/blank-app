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
INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

FOCUSED_VERIFIERS = (
    "design_guide_apply_current_state_safety_snapshot.py",
    "design_guide_primary_apply_payload_projection_adapter_snapshot.py",
    "design_guide_primary_apply_payload_projection_cutover_snapshot.py",
    "design_guide_primary_button_apply_session_shell_boundary_snapshot.py",
    "design_guide_cta_apply_binding_bypass_readiness_snapshot.py",
    "design_guide_cta_apply_binding_bypass_implementation_snapshot.py",
    "design_guide_cta_apply_binding_bypass_live_impact_snapshot.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + len(marker))
    if end < 0:
        end = len(source)
    return source[start:end]


def _run(script_name: str, timeout: int = 300) -> dict[str, Any]:
    command = [sys.executable, f"tools/verification/{script_name}"]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "script": script_name,
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "UNREADABLE",
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "PARTIAL" in upper:
        status = "PARTIAL"
    elif "FAIL" in upper or "BLOCKED" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "path": str(path), "status": status, "payload": payload}


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Design Brain Shared Apply Payload Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock audits primary Apply payload source, projection, stale-state/current-state safety, and page-owned apply routing boundaries.",
        "",
        "## Ownership",
        "",
        "- payload projection assembly: `FinalDesignGuidePublication.primary_apply_payload_projection`",
        "- CTA/apply payload source hash guard: `FinalDesignGuidePublication.cta_hash + apply_payload_hash + state_fingerprint`",
        "- current-state safety preview guard: currently page-owned shell/evaluator boundary",
        "- actual apply commit/routing: `inputs_page.py`",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Focused Verifiers", ""])
    for key, result in snapshot["focused_verifiers"].items():
        lines.append(f"- `{key}`: `{result['passed']}`")
    lines.extend(["", "## Latest Apply Safety Artifact", ""])
    safety = snapshot["latest_apply_current_state_safety"]
    lines.append(f"- status: `{safety.get('status')}`")
    lines.append(f"- path: `{safety.get('path')}`")
    checks = dict((safety.get("payload") or {}).get("checks") or {})
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{value}`")
    if snapshot["failures"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {failure}" for failure in snapshot["failures"])
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Before this component can be LOCKED, prove or restore final apply-commit current-state guard coverage without changing CTA/apply semantics.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = _read(INPUTS)
    final_source = _read(FINAL_PUBLICATION)
    payload_builder = _function_body(inputs_source, "_build_design_guide_primary_apply_payload")
    apply_commit = _function_body(inputs_source, "_apply_resolved_candidate_payload")
    projection_adapter = _function_body(final_source, "build_final_design_guide_primary_apply_payload_projection")

    focused = {script: _run(script) for script in FOCUSED_VERIFIERS}
    latest_apply_safety = _latest("design_guide_apply_current_state_safety")
    safety_checks = dict((latest_apply_safety.get("payload") or {}).get("checks") or {})

    checks = {
        "focused_verifiers_all_pass": all(result["passed"] for result in focused.values()),
        "payload_builder_uses_current_state_guard": "_design_guide_apply_updates_current_state_guard(" in payload_builder,
        "payload_builder_refuses_failed_guard": (
            'if not bool(current_state_apply_guard.get("pass")):' in payload_builder and "return {}" in payload_builder
        ),
        "payload_builder_delegates_projection_to_final_publication": (
            "_build_final_design_guide_primary_apply_payload_projection(" in payload_builder
        ),
        "final_publication_projection_adapter_exists": bool(projection_adapter),
        "projection_adapter_has_no_page_runtime": all(
            token not in projection_adapter for token in ("inputs_page", "streamlit", "st.", "session_state")
        ),
        "apply_commit_uses_current_state_guard": safety_checks.get("apply_commit_uses_guard") is True,
        "apply_commit_guard_before_shared_update": safety_checks.get("apply_commit_guard_before_shared_update") is True,
        "apply_commit_blocks_failed_guard": safety_checks.get("apply_commit_blocks_failed_guard") is True,
        "apply_commit_clears_canonical_payload": safety_checks.get("apply_commit_clears_canonical_payload") is True,
        "apply_routing_remains_page_owned": bool(apply_commit) and "_set_shared_updates(" in apply_commit,
    }

    failures: list[str] = []
    for key, value in checks.items():
        if not value:
            failures.append("check_failed:" + key)
    for script, result in focused.items():
        if not result["passed"]:
            failures.append("focused_verifier_failed:" + script)

    status = "LOCKED" if not failures else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_shared_apply_payload_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_apply_payload_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_apply_payload_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "Apply payload",
        "focused_verifiers": focused,
        "latest_apply_current_state_safety": latest_apply_safety,
        "checks": checks,
        "failures": failures,
        "artifact": str(json_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_apply_payload_lock {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
