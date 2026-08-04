"""Contract gate for live/browser-observed Design Guide bugs.

This verifier makes the live-bug registry enforceable.  A bug listed as
``active`` in ``design_guide_live_bug_regression_registry.json`` is not treated
as protected unless it has:

- a concrete verifier file,
- a command that runs that verifier,
- required expected behaviour fields,
- and a passing artifact emitted by that verifier during this run.

The script does not mutate product code.  It is intended to be run before the
universal verification meta-lock can call the app fully verified.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REGISTRY_PATH = ROOT / "tools" / "verification" / "design_guide_live_bug_regression_registry.json"

REQUIRED_ENTRY_FIELDS: tuple[str, ...] = (
    "bug_id",
    "description",
    "scope",
    "family_id",
    "input_state",
    "expected_family",
    "expected_card_state",
    "expected_cta_state",
    "expected_target_or_blocker",
    "regression_verifier",
    "verification_commands",
    "status",
)

PASS_STATUSES = {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS"}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _artifact_from_output(stdout: str, stderr: str, command: str) -> Path | None:
    command_parts = command.replace("\\", "/").split()
    verifier_stem = Path(command_parts[1]).stem if len(command_parts) > 1 else ""
    accepted_stems = {verifier_stem}
    if verifier_stem.endswith("_snapshot"):
        accepted_stems.add(verifier_stem[:-len("_snapshot")])
    for raw_line in (stdout or "").splitlines() + (stderr or "").splitlines():
        line = raw_line.strip()
        candidate = ""
        if line.startswith("json="):
            candidate = line[5:].strip()
        elif line.startswith("JSON:"):
            candidate = line[5:].strip()
        elif line.startswith("artifact:"):
            candidate = line[9:].strip()
        if candidate:
            path = Path(candidate)
            if (
                path.exists()
                and path.is_file()
                and any(path.name.startswith(f"{stem}_") for stem in accepted_stems if stem)
            ):
                return path
    # A few focused verifiers print their result object as JSON rather than a
    # dedicated path line. Accept only the object-level artifact field and
    # apply the same verifier-prefix check.
    for stream in (stdout or "", stderr or ""):
        try:
            payload = json.loads(stream)
        except Exception:
            continue
        candidate = payload.get("artifact") if isinstance(payload, dict) else None
        if candidate:
            path = Path(str(candidate))
            if (
                path.exists()
                and path.is_file()
                and any(path.name.startswith(f"{stem}_") for stem in accepted_stems if stem)
            ):
                return path
    return None


def _run_registry_dependencies(commands: list[str]) -> dict[str, dict[str, Any]]:
    """Run each distinct active regression and bind only its emitted artifact."""
    run_id = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID") or "").strip()
    started_epoch = datetime.now().timestamp()
    rows: dict[str, dict[str, Any]] = {}
    for command in dict.fromkeys(commands):
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                text=True,
                shell=True,
                capture_output=True,
                timeout=900,
                env=os.environ.copy(),
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            returncode = int(completed.returncode)
        except subprocess.TimeoutExpired as exc:
            stdout = str(exc.stdout or "")
            stderr = str(exc.stderr or "")
            returncode = 124
            timed_out = True
        path = _artifact_from_output(stdout, stderr, command)
        payload = _read_json(path) if path else {}
        current = bool(path and path.stat().st_mtime >= started_epoch)
        row = {
            "command": command,
            "returncode": returncode,
            "passed": bool(not timed_out and returncode == 0 and _payload_passed(payload) and current),
            "timed_out": timed_out,
            "artifact_path": str(path) if path else None,
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path else None,
            "artifact_modified_at": path.stat().st_mtime if path else None,
            "written_in_current_run": current,
            "verification_run_id": run_id or None,
            "status": _payload_status(payload),
            "failure": None,
            "stdout": stdout[-2000:],
            "stderr": stderr[-2000:],
        }
        if not path:
            row["failure"] = "verifier_did_not_emit_artifact_path"
        elif not current:
            row["failure"] = "missing_or_stale_current_run_artifact"
        elif not row["passed"]:
            row["failure"] = "current_run_dependency_not_pass"
        rows[command] = row
    return rows


def _payload_status(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("audit_status")
        or "MISSING"
    ).strip()


def _payload_passed(payload: dict[str, Any]) -> bool:
    return _payload_status(payload).upper() in PASS_STATUSES


def _normalise_command(command: str) -> str:
    return command.replace("\\", "/").strip()


def _entry_row(entry: dict[str, Any], dependency_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    verifier = str(entry.get("regression_verifier") or "").strip()
    verifier_path = ROOT / verifier if verifier else ROOT / "__missing_live_bug_verifier__"
    commands = [str(command) for command in list(entry.get("verification_commands") or [])]
    missing_fields = [
        field
        for field in REQUIRED_ENTRY_FIELDS
        if entry.get(field) in (None, "", [])
    ]
    command_mentions_verifier = bool(
        verifier
        and any(verifier.replace("\\", "/") in _normalise_command(command) for command in commands)
    )
    active = str(entry.get("status") or "").strip().lower() == "active"
    dependency = next(
        (dependency_rows[command] for command in commands if command in dependency_rows),
        {},
    )
    problems: list[str] = []
    if active:
        if missing_fields:
            problems.append("missing_required_fields")
        if not verifier:
            problems.append("missing_regression_verifier")
        elif not verifier_path.exists():
            problems.append("regression_verifier_file_missing")
        if not commands:
            problems.append("missing_verification_commands")
        elif not command_mentions_verifier:
            problems.append("verification_commands_do_not_run_regression_verifier")
        if not dependency:
            problems.append("current_run_dependency_not_executed")
        elif not dependency.get("passed"):
            problems.append(str(dependency.get("failure") or "current_run_dependency_not_pass"))

    return {
        "bug_id": entry.get("bug_id"),
        "status": entry.get("status"),
        "family_id": entry.get("family_id"),
        "scope": entry.get("scope"),
        "regression_verifier": verifier,
        "verifier_exists": bool(verifier and verifier_path.exists()),
        "verification_commands": commands,
        "command_mentions_verifier": command_mentions_verifier,
        "missing_required_fields": missing_fields,
        "current_run_dependency": dependency,
        "expected_family": entry.get("expected_family"),
        "expected_card_state": entry.get("expected_card_state"),
        "expected_cta_state": entry.get("expected_cta_state"),
        "expected_target_or_blocker": entry.get("expected_target_or_blocker"),
        "problems": problems,
        "enforced": active and not problems,
    }


def _build() -> dict[str, Any]:
    registry = _read_json(REGISTRY_PATH)
    entries = [entry for entry in list(registry.get("entries") or []) if isinstance(entry, dict)]
    active_commands = [
        str(command)
        for entry in entries
        if str(entry.get("status") or "").strip().lower() == "active"
        for command in list(entry.get("verification_commands") or [])
    ]
    dependency_rows = _run_registry_dependencies(active_commands)
    rows = [_entry_row(entry, dependency_rows) for entry in entries]
    active_rows = [row for row in rows if str(row.get("status") or "").lower() == "active"]
    failed_rows = [row for row in active_rows if row["problems"]]
    return {
        "schema": "design_guide.live_bug_registry_contract.v1",
        "status": "PASS" if not failed_rows else "FAIL",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "registry_path": str(REGISTRY_PATH),
        "active_bug_count": len(active_rows),
        "enforced_active_bug_count": sum(1 for row in active_rows if row["enforced"]),
        "failed_active_bug_count": len(failed_rows),
        "active_bug_rows": active_rows,
        "failed_active_bug_rows": failed_rows,
        "current_run_dependencies": dependency_rows,
        "contract_rule": (
            "Every active live/browser-observed bug must have an executable focused "
            "verifier whose distinct command emits a current-run PASS artifact."
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Live Bug Registry Contract",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"Active bugs: `{payload['active_bug_count']}`",
        f"Enforced active bugs: `{payload['enforced_active_bug_count']}`",
        f"Failed active bugs: `{payload['failed_active_bug_count']}`",
        "",
        "## Contract Rule",
        "",
        str(payload["contract_rule"]),
        "",
        "## Active Bug Rows",
        "",
        "| Bug | Family | Verifier exists | Current-run artifact | Status | Enforced | Problems |",
        "| --- | --- | ---: | --- | --- | ---: | --- |",
    ]
    for row in list(payload["active_bug_rows"]):
        dependency = dict(row.get("current_run_dependency") or {})
        lines.append(
            f"| `{row.get('bug_id')}` | `{row.get('family_id')}` | `{row.get('verifier_exists')}` | "
            f"`{dependency.get('artifact_path')}` | `{dependency.get('status')}` | "
            f"`{row.get('enforced')}` | `{row.get('problems')}` |"
        )
    if payload["failed_active_bug_rows"]:
        lines.extend(["", "## Blocking Rows", ""])
        for row in list(payload["failed_active_bug_rows"]):
            lines.append(f"- `{row.get('bug_id')}`: `{row.get('problems')}`")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"design_guide_live_bug_registry_contract_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_live_bug_registry_contract_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"design_guide_live_bug_registry_contract {payload['status']}")
    print(f"active_bug_count={payload['active_bug_count']}")
    print(f"enforced_active_bug_count={payload['enforced_active_bug_count']}")
    print(f"failed_active_bug_count={payload['failed_active_bug_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
