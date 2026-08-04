"""Print or run the canonical release-gate manifest.

Use this instead of hand-copying final verification command lists between
chats. By default it prints the commands only. Use ``--execute`` when ready to
run the full release sequence.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

try:
    from tools.verification.source_fingerprint import compute_source_fingerprint
except ModuleNotFoundError:
    from source_fingerprint import compute_source_fingerprint

try:
    from tools.verification.verification_run_manifest import MANIFEST_DIR
except ModuleNotFoundError:
    from verification_run_manifest import MANIFEST_DIR

try:
    from tools.verification.release_gate_plan import load_release_gate_manifest, validate_release_gate_manifest
except ModuleNotFoundError:
    from release_gate_plan import load_release_gate_manifest, validate_release_gate_manifest


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MANIFEST_PATH = VERIFICATION_DIR / "release_gate_manifest.json"
# The critical-workflow stability gate intentionally runs multiple browser
# workflows at ten repetitions each. Keep a bounded ceiling, but allow the
# full recipe to finish and emit its artifact instead of converting a valid
# long run into a missing-artifact failure at 30 minutes.
RELEASE_GATE_TIMEOUT_SECONDS = 45 * 60


def _verification_python() -> str:
    """Use the GIL-enabled interpreter for Playwright-compatible live gates."""
    executable = Path(sys.executable)
    if executable.name.lower().endswith("t.exe"):
        compatible = executable.with_name("python.exe")
        if compatible.exists():
            return str(compatible)
    return str(executable)


def _normalize_python_command(command: str) -> str:
    prefix = "python "
    if command.lower().startswith(prefix):
        return f'"{_verification_python()}" {command[len(prefix):]}'
    return command


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _commands(*, tier: str = "all") -> list[dict[str, str]]:
    manifest = _read_json(MANIFEST_PATH)
    rows: list[dict[str, str]] = []
    for gate in list(manifest.get("release_gates") or []):
        if not isinstance(gate, dict):
            continue
        gate_tier = str(gate.get("tier") or "fast").strip().lower()
        if tier != "all" and gate_tier != tier:
            continue
        rows.append(
            {
                "id": str(gate.get("id") or ""),
                "command": str(gate.get("command") or ""),
                "tier": gate_tier,
                "depends_on": list(gate.get("depends_on") or []),
            }
        )
    by_id = {row["id"]: row for row in rows}
    ordered: list[dict[str, str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(gate_id: str) -> None:
        if gate_id in visited:
            return
        if gate_id in visiting:
            raise RuntimeError(f"release gate dependency cycle at {gate_id}")
        row = by_id.get(gate_id)
        if row is None:
            raise RuntimeError(f"release gate dependency references unknown gate: {gate_id}")
        visiting.add(gate_id)
        for dependency in list(row.get("depends_on") or []):
            if dependency in by_id:
                visit(dependency)
        visiting.remove(gate_id)
        visited.add(gate_id)
        ordered.append(row)

    for row in rows:
        visit(row["id"])
    return ordered


def _run_command(command: str, *, tier: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["DESIGN_BRAIN_VERIFICATION_TIER"] = tier
    run_id = str(env.get("DESIGN_BRAIN_VERIFICATION_RUN_ID") or "").strip()
    run_manifest_payload: dict[str, Any] = {}
    run_manifest_path = str(env.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if run_manifest_path:
        run_manifest_payload = _read_json(Path(run_manifest_path))
    if run_id and not str(env.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip():
        env["DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"] = str(MANIFEST_DIR / f"{run_id}.json")
    source = compute_source_fingerprint(repo=ROOT)
    correctness = source.get("correctness_fingerprint") or {}
    source_code_hash = correctness.get("fingerprint") if isinstance(correctness, dict) else correctness
    recipe_hash = str(run_manifest_payload.get("recipe_hash") or "")
    command_to_run = _normalize_python_command(command)
    if run_id and os.name == "nt":
        command_to_run = (
            f'set "DESIGN_BRAIN_VERIFICATION_RUN_ID={run_id}" && '
            f'set "DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST={env["DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"]}" && '
            f"{command}"
        )
    if "check_release_gate_manifest.py" in command and env.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        command_to_run = (
            f'{command} --run-manifest "{env["DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"]}"'
        )
    command_started = time.time()
    try:
        completed = subprocess.run(
            command_to_run,
            cwd=str(ROOT),
            text=True,
            shell=True,
            capture_output=True,
            env=env,
            timeout=RELEASE_GATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "command": command,
            "returncode": None,
            "stdout": str(stdout)[-8000:],
            "stderr": str(stderr)[-8000:],
            "passed": False,
            "timed_out": True,
            "timeout_seconds": RELEASE_GATE_TIMEOUT_SECONDS,
            "failure_class": "release_gate_timeout",
            "run_artifacts": [],
        }
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "passed": completed.returncode == 0,
    }
    emitted: list[dict[str, Any]] = []
    for candidate in ARTIFACT_DIR.glob("*.json"):
        try:
            if candidate.stat().st_mtime < command_started:
                continue
            emitted.append(
                {
                    "artifact_path": str(candidate),
                    "artifact_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "verification_run_id": run_id or os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
                    "source_code_hash": source_code_hash,
                    "recipe_hash": recipe_hash,
                }
            )
        except OSError:
            continue
    result["run_artifacts"] = sorted(emitted, key=lambda item: item["artifact_path"])
    artifact_path = None
    for line in (completed.stdout or "").splitlines() + (completed.stderr or "").splitlines():
        text = line.strip()
        if text.startswith("json="):
            artifact_path = text[5:].strip()
        elif text.startswith("JSON:"):
            artifact_path = text[5:].strip()
    if artifact_path:
        path = Path(artifact_path)
        result["artifact_binding"] = {
            "artifact_path": str(path),
            "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
            "verification_run_id": run_id or os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"),
            "source_code_hash": source_code_hash,
            "recipe_hash": recipe_hash,
        }
    return result


def _record_current_run_result(result: dict[str, Any]) -> None:
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path:
        return
    path = Path(manifest_path)
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    rows = list(payload.get("release_gate_results") or [])
    rows.append(dict(result))
    payload["release_gate_results"] = rows
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _same_run_command_result(command: str) -> dict[str, Any] | None:
    """Avoid rerunning an expensive gate already executed by the canonical runner.

    The release manifest is itself a composed gate and runs inside the
    canonical run.  Replaying the universal live family gate here created a
    second browser/fuzz run in the same release.  Reuse is allowed only for a
    matching command with an explicit PASS result in the same run manifest.
    """
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path:
        return None
    payload = _read_json(Path(manifest_path))
    run_id = str(payload.get("run_id") or os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID") or "")
    source_hash = str(
        dict(payload.get("source_code_hash") or {}).get("fingerprint")
        or payload.get("source_code_hash")
        or ""
    )
    recipe_hash = str(payload.get("recipe_hash") or "")
    for result in list(payload.get("results") or []):
        if not isinstance(result, dict):
            continue
        if str(result.get("command") or "").strip() != str(command).strip():
            continue
        if result.get("passed") is not True:
            continue
        binding = dict(result.get("artifact_binding") or {})
        artifact = Path(str(binding.get("artifact_path") or ""))
        if not binding or not artifact.exists():
            continue
        if str(binding.get("verification_run_id") or "") != run_id:
            continue
        if source_hash and str(binding.get("source_code_hash") or "") != source_hash:
            continue
        if recipe_hash and str(binding.get("recipe_hash") or "") != recipe_hash:
            continue
        expected_sha = str(binding.get("artifact_sha256") or "")
        if not expected_sha or hashlib.sha256(artifact.read_bytes()).hexdigest() != expected_sha:
            continue
        return dict(result)
    return None


def _same_run_command_already_passed(command: str) -> bool:
    return _same_run_command_result(command) is not None


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Release Gate Manifest Runner",
        "",
        f"Status: `{payload['status']}`",
        f"Mode: `{payload['mode']}`",
        "",
        "## Canonical Commands",
        "",
        "```powershell",
    ]
    for row in list(payload["commands"]):
        lines.append(str(row["command"]))
    lines.extend(["```", ""])
    if payload["run_results"]:
        lines.extend(["## Run Results", ""])
        for row in list(payload["run_results"]):
            lines.append(f"- `{row['command']}` rc=`{row['returncode']}` passed=`{row['passed']}`")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the release gates in manifest order.")
    parser.add_argument(
        "--tier",
        choices=("all", "fast", "live"),
        default="all",
        help="Run or print one manifest tier. Full release certification requires --tier all.",
    )
    parser.add_argument("--stop-on-first-failure", action="store_true", default=True)
    args = parser.parse_args(argv)

    plan_problems = validate_release_gate_manifest(load_release_gate_manifest(MANIFEST_PATH))
    if plan_problems:
        raise SystemExit("invalid canonical release-gate plan: " + ", ".join(plan_problems))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    commands = _commands(tier=args.tier)
    run_results: list[dict[str, Any]] = []
    if args.execute:
        # The manifest checker validates the completed release evidence,
        # including the meta-lock and completion audit. Run it last so the
        # release sequence has no circular dependency on its prior artifact.
        deferred = [row for row in commands if row["id"] == "release_gate_manifest"]
        ordered = [row for row in commands if row["id"] != "release_gate_manifest"] + deferred
        for row in ordered:
            reused_result = _same_run_command_result(row["command"])
            if reused_result is not None:
                result = {
                    "command": row["command"],
                    "returncode": 0,
                    "stdout": "reused same-run canonical result",
                    "stderr": "",
                    "passed": True,
                    "skipped_same_run": True,
                    "failure_class": None,
                    "artifact_binding": dict(reused_result.get("artifact_binding") or {}),
                    "run_artifacts": list(reused_result.get("run_artifacts") or []),
                }
            else:
                result = _run_command(row["command"], tier=args.tier)
            run_results.append(result)
            _record_current_run_result(result)
            if args.stop_on_first_failure and not result["passed"]:
                break
    failed = [row for row in run_results if not row.get("passed")]
    if args.execute and not commands:
        failed.append({"failure_class": "empty_release_gate_plan"})
    if args.execute and not run_results:
        failed.append({"failure_class": "release_gate_execution_empty"})
    payload = {
        "schema": "design_brain.release_gate_manifest_runner.v1",
        "status": "PASS" if not failed else "FAIL",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "mode": "execute" if args.execute else "print",
        "tier": args.tier,
        "release_certification": args.tier == "all",
        "manifest_path": str(MANIFEST_PATH),
        "commands": commands,
        "run_results": run_results,
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"release_gate_manifest_runner_{stamp}.json"
    report_path = AUDIT_DIR / f"release_gate_manifest_runner_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"release_gate_manifest_runner {payload['status']}")
    print(f"mode={payload['mode']}")
    print("commands:")
    for row in commands:
        print(row["command"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
