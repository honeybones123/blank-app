"""Policy gate for live Design Guide bug regressions.

Live/browser-observed Design Guide bugs must be recorded in
design_guide_live_bug_regression_registry.json and protected by a focused
verifier. This script makes that rule executable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "tools" / "verification" / "design_guide_live_bug_regression_registry.json"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

REQUIRED_FIELDS = (
    "bug_id",
    "description",
    "scope",
    "input_state",
    "expected_family",
    "expected_card_state",
    "expected_cta_state",
    "expected_target_or_blocker",
    "regression_verifier",
    "verification_commands",
    "status",
)


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def _load_registry() -> dict[str, Any]:
    if not REGISTRY.exists():
        raise AssertionError(f"Missing live bug regression registry: {_repo_rel(REGISTRY)}")
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _validate_entry(entry: dict[str, Any], seen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    bug_id = str(entry.get("bug_id") or "").strip()
    if bug_id in seen_ids:
        errors.append(f"duplicate bug_id: {bug_id}")
    seen_ids.add(bug_id)

    for field in REQUIRED_FIELDS:
        value = entry.get(field)
        if isinstance(value, list):
            if not value:
                errors.append(f"missing {field}")
        elif not str(value or "").strip():
            errors.append(f"missing {field}")

    verifier = ROOT / str(entry.get("regression_verifier") or "")
    if not verifier.exists():
        errors.append(f"missing regression verifier: {_repo_rel(verifier)}")
    elif verifier.suffix != ".py":
        errors.append(f"regression verifier is not a Python script: {_repo_rel(verifier)}")

    commands = entry.get("verification_commands")
    if not isinstance(commands, list) or not all(isinstance(item, str) and item.strip() for item in commands):
        errors.append("verification_commands must be a non-empty list of commands")

    status = str(entry.get("status") or "").strip()
    if status not in {"active", "retired", "blocked"}:
        errors.append("status must be one of: active, retired, blocked")

    return errors


def _run_entry_verifier(entry: dict[str, Any]) -> dict[str, Any]:
    verifier = ROOT / str(entry.get("regression_verifier") or "")
    if not verifier.exists() or str(entry.get("status")) != "active":
        return {
            "ran": False,
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
        }
    proc = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    return {
        "ran": True,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_live_bug_regression_policy_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_bug_regression_policy_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Guide Live Bug Regression Policy",
        "",
        f"Status: **{payload['status']}**",
        "",
        "Rule: a live/browser-observed Design Guide bug is not fixed unless it is registered here and protected by a passing focused verifier.",
        "",
        "## Registered Live Bugs",
        "",
        "| bug id | scope | verifier | verifier status | entry errors |",
        "|---|---|---|---|---|",
    ]
    for result in payload["entry_results"]:
        verifier_result = result.get("verifier_result") or {}
        verifier_status = "not run"
        if verifier_result.get("ran"):
            verifier_status = "PASS" if verifier_result.get("returncode") == 0 else "FAIL"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(result.get("bug_id") or ""),
                    str(result.get("scope") or ""),
                    f"`{result.get('regression_verifier') or ''}`",
                    verifier_status,
                    "; ".join(result.get("entry_errors") or []) or "none",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Required Workflow",
            "",
            "1. Add the live bug to `tools/verification/design_guide_live_bug_regression_registry.json`.",
            "2. Add or update the focused verifier named by `regression_verifier`.",
            "3. Run this policy gate before calling the live bug fixed.",
            "",
            f"JSON artifact: `{_repo_rel(json_path)}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    registry = _load_registry()
    entries = list(registry.get("entries") or [])
    seen_ids: set[str] = set()
    entry_results: list[dict[str, Any]] = []
    failures: list[str] = []

    for entry in entries:
        entry_errors = _validate_entry(entry, seen_ids)
        verifier_result = _run_entry_verifier(entry) if not entry_errors else {"ran": False}
        if entry_errors:
            failures.append(str(entry.get("bug_id") or "missing_bug_id"))
        if verifier_result.get("ran") and verifier_result.get("returncode") != 0:
            failures.append(str(entry.get("bug_id") or "missing_bug_id"))
        entry_results.append(
            {
                "bug_id": entry.get("bug_id"),
                "scope": entry.get("scope"),
                "family_id": entry.get("family_id"),
                "regression_verifier": entry.get("regression_verifier"),
                "entry_errors": entry_errors,
                "verifier_result": verifier_result,
            }
        )

    if not entries:
        failures.append("registry_has_no_entries")

    payload = {
        "schema": "design_guide_live_bug_regression_policy.v1",
        "status": "PASS" if not failures else "FAIL",
        "registry": _repo_rel(REGISTRY),
        "entry_count": len(entries),
        "failure_count": len(set(failures)),
        "failures": sorted(set(failures)),
        "entry_results": entry_results,
    }
    json_path, md_path = _write_artifacts(payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "entry_count": payload["entry_count"],
                "failure_count": payload["failure_count"],
                "artifact": _repo_rel(json_path),
                "report": _repo_rel(md_path),
            },
            indent=2,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
