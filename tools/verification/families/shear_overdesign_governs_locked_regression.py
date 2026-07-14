from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.shear_overdesign_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    family_identity,
    internal_ladder_hash,
    ranking_criteria,
    required_gates,
)


IDENTITY = family_identity()
FAMILY_ID = str(IDENTITY.get("family_id") or "")

PROOF_PACK: tuple[tuple[str, str], ...] = (
    ("contract_check", "tools/verification/families/shear_overdesign_governs_contract_check.py"),
    ("runtime_snapshot", "tools/verification/families/shear_overdesign_governs_runtime_snapshot.py"),
    ("lock_verifier", "tools/verification/families/shear_overdesign_governs_lock_verifier.py"),
)


def _run_script(name: str, script: str, *, timeout_s: int = 300) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    status_line = next(
        (
            line.strip()
            for line in stdout.splitlines()
            if line.strip().startswith(("PASS:", "FAIL:", "SHEAR_OVERDESIGN"))
        ),
        "",
    )
    return {
        "name": name,
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "duration_sec": round(time.time() - started, 3),
        "status_line": status_line,
        "stdout_tail": stdout.strip().splitlines()[-20:],
        "stderr_tail": stderr.strip().splitlines()[-20:],
    }


def _write_markdown_report(output: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# SHEAR_OVERDESIGN_GOVERNS Locked Regression",
        "",
        f"Status: {output.get('status')}",
        "",
        "## Lock Decision",
        "",
        f"- ready_to_mark_locked_next: `{output.get('ready_to_mark_locked_next')}`",
        f"- family_marked_locked_now: `{output.get('family_marked_locked_now')}`",
        "",
        "## Family",
        "",
        f"- family_id: `{output.get('family_id')}`",
        f"- internal_ladder_hash: `{output.get('internal_ladder_hash')}`",
        f"- ranking_criteria: `{output.get('ranking_criteria')}`",
        "",
        "## Proof Pack",
        "",
    ]
    for result in output.get("proof_pack_results") or []:
        icon = "PASS" if result.get("passed") else "FAIL"
        lines.append(f"- `{icon}` `{result.get('name')}`: `{result.get('script')}`")
        if result.get("status_line"):
            lines.append(f"  - {result.get('status_line')}")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- {failure}" for failure in output.get("failures") or []] or ["- none"])
    lines.extend(["", "## Output", "", f"- `{output.get('artifact')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")

    proof_results = [_run_script(name, script) for name, script in PROOF_PACK]
    failures: list[str] = []
    if FAMILY_ID != "SHEAR_OVERDESIGN_GOVERNS":
        failures.append(f"family_id_mismatch:{FAMILY_ID}")
    if not internal_ladder_hash():
        failures.append("missing_internal_ladder_hash")
    if not ranking_criteria():
        failures.append("missing_ranking_criteria")
    if not required_gates():
        failures.append("missing_required_gates")
    failures.extend(
        f"proof_failed:{result.get('name')}"
        for result in proof_results
        if not result.get("passed")
    )

    status = "PASS" if not failures else "FAIL"
    artifact_path = ARTIFACT_DIR / f"shear_overdesign_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_overdesign_governs_locked_regression_{stamp}.md"
    output = {
        "schema": "shear_overdesign_governs_locked_regression.v1",
        "status": status,
        "contract_path": str(CONTRACT_PATH),
        "family_id": FAMILY_ID,
        "internal_ladder_hash": internal_ladder_hash(),
        "ranking_criteria": list(ranking_criteria()),
        "required_gates": list(required_gates()),
        "proof_pack": [{"name": name, "script": script} for name, script in PROOF_PACK],
        "proof_pack_results": proof_results,
        "ready_to_mark_locked_next": status == "PASS",
        "family_marked_locked_now": False,
        "failures": failures,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_markdown_report(output, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
