from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


REGRESSION_GATES: tuple[tuple[str, str], ...] = (
    ("contract_check", "tools/verification/families/shear_fail_bending_overdesign_governs_contract_check.py"),
    ("source_priority", "tools/verification/families/shear_fail_bending_overdesign_governs_source_priority_snapshot.py"),
    ("runtime_snapshot", "tools/verification/families/shear_fail_bending_overdesign_governs_runtime_snapshot.py"),
    ("lock_verifier", "tools/verification/families/shear_fail_bending_overdesign_governs_lock_verifier.py"),
)


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
        "passed": proc.returncode == 0,
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"shear_fail_bending_overdesign_governs_locked_regression_{stamp}.json"
    report_path = AUDIT_DIR / f"shear_fail_bending_overdesign_governs_locked_regression_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS Locked Regression",
                "",
                f"Status: `{snapshot['status']}`",
                "",
                "## Gates",
                "",
                *[
                    f"- `{row['name']}`: `{'PASS' if row['passed'] else 'FAIL'}`"
                    for row in snapshot["gates"]
                ],
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, report_path


def main() -> int:
    gates = [{"name": name, **_run(script)} for name, script in REGRESSION_GATES]
    failures = [f"gate_failed:{row['name']}" for row in gates if not row["passed"]]
    snapshot = {
        "schema": "shear_fail_bending_overdesign_governs_locked_regression.v1",
        "family_id": "SHEAR_FAIL_BENDING_OVERDESIGN_GOVERNS",
        "status": "PASS" if not failures else "FAIL",
        "gates": gates,
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    print(f"{snapshot['status']}: {json_path}")
    print(f"Report: {report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
