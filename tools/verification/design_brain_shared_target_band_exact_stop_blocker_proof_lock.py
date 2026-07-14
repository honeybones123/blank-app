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


FOCUSED_COMMANDS: tuple[tuple[str, tuple[str, ...], int], ...] = (
    (
        "target_band_reached_contract_compliance",
        ("tools/verification/design_brain_family_contract_compliance_target_band_reached.py",),
        90,
    ),
    (
        "exact_stop_proven_contract_compliance",
        ("tools/verification/design_brain_family_contract_compliance_exact_stop_proven.py",),
        90,
    ),
    (
        "target_band_candidate_lane_coverage",
        ("tools/verification/families/target_band_candidate_lane_coverage_snapshot.py",),
        90,
    ),
    (
        "target_band_candidate_lane_detailed_audit",
        ("tools/verification/families/target_band_candidate_lane_detailed_audit.py",),
        180,
    ),
)


def _run(name: str, args: tuple[str, ...], timeout: int) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(["python", *args]),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-16:],
        "stderr_tail": proc.stderr.strip().splitlines()[-16:],
    }


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "payload": {}, "error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload}


def _append_if(value: Any, output: list[str], label: str) -> None:
    if value:
        output.append(f"{label}: {value}")


def _collect_blockers(command_results: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for result in command_results:
        if result.get("status") != "PASS":
            blockers.append(f"{result['name']} did not pass")

    coverage = _latest_payload("target_band_candidate_lane_coverage")
    coverage_payload = dict(coverage.get("payload") or {})
    review_needed = coverage_payload.get("review_needed_families") or []
    if review_needed:
        blockers.append(
            "target-band candidate lane coverage still has review-needed families: "
            + ", ".join(str(item) for item in review_needed)
        )

    detailed = _latest_payload("target_band_candidate_lane_detailed_audit")
    detailed_payload = dict(detailed.get("payload") or {})
    detailed_reviews = detailed_payload.get("review_needed_families") or []
    if detailed_reviews:
        blockers.append(
            "detailed target-band audit still has review-needed families: "
            + ", ".join(str(item) for item in detailed_reviews)
        )
    combined = dict(detailed_payload.get("combined_verification") or {})
    rescue = dict(combined.get("rescue_seed") or {})
    selection = dict(combined.get("target_band_selection") or {})
    if rescue.get("status") and rescue.get("status") != "PASS":
        stderr_tail = " ".join(str(line) for line in rescue.get("stderr_tail") or [])
        if "_rescue_mode_choose_tier_from_overview" in stderr_tail:
            blockers.append(
                "rescue seed proof verifier is stale: it still expects inputs_page._rescue_mode_choose_tier_from_overview"
            )
        else:
            blockers.append("combined rescue seed proof is not PASS")
    if selection.get("status") and selection.get("status") != "PASS":
        selection_payload = _latest_payload("design_guide_combined_fail_target_band_selection")
        checks = dict((selection_payload.get("payload") or {}).get("checks") or {})
        failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
        if failed_checks:
            blockers.append(
                "combined target-band selection proof has failing checks: "
                + ", ".join(failed_checks)
            )
        else:
            blockers.append("combined target-band selection proof is not PASS")
    return list(dict.fromkeys(blockers))


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# Shared Target-Band / Exact-Stop / Blocker Proof Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Ownership",
        "",
        "- Family runtimes own target-band, exact-stop, blocker, exhausted, and repair-blocked engineering proof.",
        "- Shared code may validate schemas, publish proof, and render proof, but must not invent family-specific proof.",
        "- Page/render code must not rewrite blocker or exact-stop outcomes after publication.",
        "",
        "## Focused Gates",
        "",
        "| Gate | Status | Command |",
        "| --- | --- | --- |",
    ]
    for result in snapshot.get("focused_results") or []:
        lines.append(f"| {result['name']} | `{result['status']}` | `{result['command']}` |")
    lines.extend(["", "## Blockers", ""])
    if snapshot.get("blockers"):
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Latest Artifacts",
            "",
        ]
    )
    for key, row in (snapshot.get("latest_artifacts") or {}).items():
        lines.append(f"- {key}: `{row.get('path')}`")
    lines.extend(["", f"JSON: `{snapshot['artifact']}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _run(
        "py_compile_shared_target_band_exact_stop_blocker_lock",
        ("-m", "py_compile", "tools/verification/design_brain_shared_target_band_exact_stop_blocker_proof_lock.py"),
        60,
    )
    focused_results = [compile_result]
    focused_results.extend(_run(name, args, timeout) for name, args, timeout in FOCUSED_COMMANDS)
    blockers = _collect_blockers(focused_results)
    lock_ready = not blockers and all(result.get("status") == "PASS" for result in focused_results)
    status = "LOCKED" if lock_ready else "DEFERRED_WITH_BLOCKER"
    latest_artifacts = {
        "target_band_reached_contract_compliance": _latest_payload("design_brain_family_contract_compliance_target_band_reached"),
        "exact_stop_proven_contract_compliance": _latest_payload("design_brain_family_contract_compliance_exact_stop_proven"),
        "target_band_candidate_lane_coverage": _latest_payload("target_band_candidate_lane_coverage"),
        "target_band_candidate_lane_detailed_audit": _latest_payload("target_band_candidate_lane_detailed_audit"),
        "combined_target_band_selection": _latest_payload("design_guide_combined_fail_target_band_selection"),
    }
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_target_band_exact_stop_blocker_proof_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_target_band_exact_stop_blocker_proof_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_target_band_exact_stop_blocker_proof_lock.v1",
        "status": status,
        "lock_ready": lock_ready,
        "focused_results": focused_results,
        "blockers": blockers,
        "latest_artifacts": latest_artifacts,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
