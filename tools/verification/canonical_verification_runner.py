"""Run the canonical verification and cleanup certification sequence.

This runner is the single entry point for release verification. It composes
the existing manifest-driven gates, self-checks the verifier contract, and
reports cleanup candidates without deleting files automatically.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

try:
    from tools.verification.verification_run_manifest import (
        file_sha256,
        finish_manifest,
        new_run_manifest,
        reconcile_incomplete_manifests,
        write_manifest,
    )
except ModuleNotFoundError:  # direct ``python tools/verification/...`` execution
    from verification_run_manifest import (
        file_sha256,
        finish_manifest,
        new_run_manifest,
        reconcile_incomplete_manifests,
        write_manifest,
    )

try:
    from tools.verification.release_gate_plan import (
        load_release_gate_manifest,
        release_gate_rows,
        validate_release_gate_manifest,
    )
except ModuleNotFoundError:
    from release_gate_plan import (
        load_release_gate_manifest,
        release_gate_rows,
        validate_release_gate_manifest,
    )


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

RELEASE_COMMAND = "python tools/verification/run_release_gate_manifest.py --execute"


def _verification_python() -> str:
    """Use the GIL-enabled interpreter when the shell selected ``python3.13t``.

    Playwright's synchronous API depends on greenlet, which is not available
    for the free-threaded interpreter in the current verification environment.
    Keeping this selection inside the canonical runner makes the release gate
    independent of the caller's ``py`` alias.
    """
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


def _artifact_prefix_for_label(label: str) -> str | None:
    manifest = load_release_gate_manifest()
    for gate in release_gate_rows(manifest, section="prerequisite_gates") + release_gate_rows(manifest, section="release_gates"):
        if str(gate.get("id") or "") == label:
            return str(gate.get("artifact_prefix") or "") or None
    return None


def _preflight_commands(*, tier: str) -> tuple[dict[str, Any], ...]:
    """Load preflight membership from the canonical manifest."""
    manifest = load_release_gate_manifest()
    rows = {
        str(row.get("id") or ""): row
        for row in list(manifest.get("prerequisite_gates") or [])
        if isinstance(row, dict) and row.get("id") and row.get("command")
        and (tier == "all" or str(row.get("tier") or "fast").lower() == tier)
    }
    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(gate_id: str) -> None:
        if gate_id in visited:
            return
        if gate_id in visiting:
            raise RuntimeError(f"prerequisite dependency cycle at {gate_id}")
        row = rows.get(gate_id)
        if row is None:
            raise RuntimeError(f"prerequisite dependency references unavailable gate: {gate_id}")
        visiting.add(gate_id)
        for dependency in list(row.get("depends_on") or []):
            if dependency in rows:
                visit(dependency)
        visiting.remove(gate_id)
        visited.add(gate_id)
        ordered.append(row)

    for gate_id in rows:
        visit(gate_id)
    return tuple(
        {
            "id": str(row["id"]),
            "command": str(row["command"]),
            "timeout_s": int(row.get("timeout_seconds") or 1200),
            "depends_on": [str(value) for value in list(row.get("depends_on") or [])],
        }
        for row in ordered
    )


def _artifact_path_from_result(result: dict[str, Any], prefix: str) -> Path | None:
    for stream in (result.get("stdout") or "", result.get("stderr") or ""):
        for raw_line in str(stream).splitlines():
            line = raw_line.strip()
            candidate = ""
            if line.startswith("json="):
                candidate = line[5:].strip()
            elif line.startswith("JSON:"):
                candidate = line[5:].strip()
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists() and path.name.startswith(f"{prefix}_"):
                return path
    return None


def _referenced_current_json_artifacts(
    parent: Path | None,
    *,
    run_started_epoch: float | None,
) -> list[Path]:
    """Collect fresh JSON children explicitly referenced by a composed artifact.

    A composed verifier often writes one parent artifact containing paths to
    child snapshots.  Those children must be registered in the canonical run
    manifest as independently hash-bound artifacts; otherwise a child can be
    mistaken for current evidence merely because a fresh parent mentions it.
    Historical or non-JSON paths are deliberately excluded.
    """
    if parent is None or not parent.exists():
        return []
    try:
        payload = json.loads(parent.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    found: set[Path] = set()

    def visit(value: Any) -> None:
        if isinstance(value, str):
            candidate = Path(value)
            if (
                candidate.exists()
                and candidate.is_file()
                and candidate.suffix.lower() == ".json"
                and candidate != parent
                and ARTIFACT_DIR in candidate.parents
                and (ARTIFACT_DIR / "run_manifests") not in candidate.parents
                and (run_started_epoch is None or candidate.stat().st_mtime >= run_started_epoch)
            ):
                found.add(candidate)
            return
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return sorted(found, key=lambda item: item.as_posix())


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(label: str, command: str, *, timeout_s: int = 1200, run_id: str | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if run_id:
        env["DESIGN_BRAIN_VERIFICATION_RUN_ID"] = run_id
        env["DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"] = str(
            ROOT / "artifacts" / "verification" / "run_manifests" / f"{run_id}.json"
        )
    command_to_run = _normalize_python_command(command)
    process = subprocess.Popen(
        command_to_run,
        cwd=str(ROOT),
        text=True,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    def _kill_process_tree() -> None:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        returncode = process.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree()
        stdout, stderr = process.communicate(timeout=15)
        returncode = 124
        timed_out = True
    except KeyboardInterrupt:
        # A user-stopped canonical run must not leave browser or Streamlit
        # children alive to contaminate the next run.
        _kill_process_tree()
        try:
            process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        raise
    result = {
        "label": label,
        "command": command,
        "returncode": returncode,
        "passed": returncode == 0,
        "timed_out": timed_out,
        "failure_classification": "verification_runtime_timeout" if timed_out else None,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }
    if timed_out:
        checkpoint_dir = ROOT / "artifacts" / "verification"
        checkpoint_paths = []
        if run_id:
            checkpoint_paths = [
                str(path)
                for path in checkpoint_dir.glob(
                    f"app_stability_critical_workflows_checkpoint_{run_id}_*.json"
                )
                if path.is_file()
            ]
        result["diagnostic_checkpoint_paths"] = sorted(checkpoint_paths)
        result["root_cause_proof_required"] = True
    return result


def _bind_artifact(
    result: dict[str, Any],
    label: str,
    *,
    run_id: str | None = None,
    source_code_hash: str | None = None,
    recipe_hash: str | None = None,
    run_started_epoch: float | None = None,
) -> dict[str, Any]:
    prefix = _artifact_prefix_for_label(label)
    if not prefix:
        return result
    path = _artifact_path_from_result(result, prefix)
    sha256 = file_sha256(path)
    modified_at = path.stat().st_mtime if path and path.exists() else None
    result["artifact_binding"] = {
        "artifact_prefix": prefix,
        "artifact_path": path,
        "artifact_sha256": sha256,
        "artifact_modified_at": modified_at,
        "verification_run_id": run_id,
        "source_code_hash": source_code_hash,
        "recipe_hash": recipe_hash,
        "written_in_current_run": bool(
            modified_at is not None
            and run_started_epoch is not None
            and modified_at >= run_started_epoch
        ),
    }
    child_bindings: list[dict[str, Any]] = []
    for child in _referenced_current_json_artifacts(path, run_started_epoch=run_started_epoch):
        child_bindings.append(
            {
                "artifact_prefix": child.stem.rsplit("_20", 1)[0] if "_20" in child.stem else child.stem,
                "artifact_path": str(child),
                "artifact_sha256": file_sha256(child),
                "artifact_modified_at": child.stat().st_mtime,
                "verification_run_id": run_id,
                "source_code_hash": source_code_hash,
                "recipe_hash": recipe_hash,
                "written_in_current_run": True,
            }
        )
    if child_bindings:
        result["run_artifacts"] = child_bindings
    if path is None:
        result["passed"] = False
        result["failure_classification"] = "missing_current_run_artifact_path"
    elif run_started_epoch is not None and not result["artifact_binding"]["written_in_current_run"]:
        result["passed"] = False
        result["failure_classification"] = "stale_or_missing_current_run_artifact"
    return result


def _passed(payload: dict[str, Any], *, required_field: str | None = None, expected: str | None = None) -> bool:
    if required_field is not None and str(payload.get(required_field) or "") != str(expected):
        return False
    status = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("meta_lock_status")
        or payload.get("completion_status")
        or ""
    ).upper()
    return status in {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS", "COMPLETE"}


def _final_artifact_checks(
    *,
    tier: str = "all",
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expectations = {
        "release_manifest_check": ("release_gate_manifest_runner", None, None),
        "retirement_workflow": ("verifier_retirement_deletion_workflow", None, None),
    }
    if tier in {"all", "live"}:
        expectations["meta_lock"] = (
            "design_brain_universal_verification_meta_lock",
            "meta_lock_status",
            "LOCKED",
        )
    rows: dict[str, Any] = {}
    current_results = list((run_manifest or {}).get("results") or [])
    nested_results = list((run_manifest or {}).get("release_gate_results") or [])
    expected_source_hash = str(
        dict((run_manifest or {}).get("source_code_hash") or {}).get("fingerprint") or ""
    )
    expected_recipe_hash = str((run_manifest or {}).get("recipe_hash") or "")

    def _current_result(label: str, prefix: str) -> dict[str, Any]:
        matches = [
            dict(result)
            for result in current_results + nested_results
            if isinstance(result, dict)
            and (
                str(result.get("label") or "") == label
                or prefix in str(result.get("command") or "")
                or prefix in str(dict(result.get("artifact_binding") or {}).get("artifact_path") or "")
            )
        ]
        return matches[-1] if matches else {}

    for key, (prefix, field, expected) in expectations.items():
        result = _current_result(
            "verifier_retirement_deletion_workflow"
            if key == "retirement_workflow"
            else "release_gate_manifest",
            prefix,
        )
        binding = dict(result.get("artifact_binding") or {})
        path = Path(str(binding.get("artifact_path") or "")) if binding.get("artifact_path") else None
        payload = {}
        if path and path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                payload = loaded if isinstance(loaded, dict) else {}
            except Exception:
                payload = {}
        binding_matches_current_run = bool(
            binding
            and str(binding.get("verification_run_id") or "")
            == str((run_manifest or {}).get("run_id") or "")
            and str(binding.get("source_code_hash") or "") == expected_source_hash
            and str(binding.get("recipe_hash") or "") == expected_recipe_hash
            and binding.get("artifact_sha256")
            and path
            and file_sha256(path) == binding.get("artifact_sha256")
        )
        rows[key] = {
            "path": str(path) if path else None,
            "status": payload.get("status") or payload.get("meta_lock_status") or payload.get("completion_status"),
            "passed": bool(
                result.get("passed")
                and binding_matches_current_run
                and _passed(payload, required_field=field, expected=expected)
            ),
            "binding_matches_current_run": binding_matches_current_run,
        }
    return rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Canonical Verification Runner",
        "",
        f"Status: `{payload['status']}`",
        f"Mode: `{payload['mode']}`",
        "",
        "## Sequence",
        "",
    ]
    for row in list(payload["runs"]):
        lines.append(f"- `{row['label']}` rc=`{row['returncode']}` passed=`{row['passed']}`")
    lines.extend(["", "## Final Artifact Checks", ""])
    for key, row in dict(payload["final_artifact_checks"]).items():
        lines.append(f"- `{key}` status=`{row['status']}` passed=`{row['passed']}` artifact=`{row['path']}`")
    lines.extend(
        [
            "",
            "## Cleanup Rule",
            "",
            "- Historical evidence is retained.",
            "- The runner never deletes files automatically.",
            "- Deletion requires a current retirement workflow artifact with zero blocked references.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run the canonical sequence.")
    parser.add_argument("--tier", choices=("all", "fast", "live"), default="all")
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="Resume an incomplete run manifest, reusing only hash-validated passed gates.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Bounded workers for independent fast prerequisites; live gates remain serial.",
    )
    args = parser.parse_args(argv)

    plan_problems = validate_release_gate_manifest(load_release_gate_manifest())
    if plan_problems:
        raise SystemExit("invalid canonical release-gate plan: " + ", ".join(plan_problems))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    reconciled_runs = reconcile_incomplete_manifests(exclude_run_id=args.resume)
    release_command = RELEASE_COMMAND if args.tier == "all" else f"{RELEASE_COMMAND} --tier {args.tier}"
    preflight_commands = _preflight_commands(tier=args.tier)
    commands = [
        {
            "label": str(gate["id"]),
            "command": str(gate["command"]),
            "timeout_seconds": str(gate.get("timeout_s") or 1200),
            "depends_on": list(gate.get("depends_on") or []),
        }
        for gate in preflight_commands
    ]
    release_row = next(
        (
            row for row in release_gate_rows(load_release_gate_manifest(), section="release_gates")
            if str(row.get("id") or "") == "release_gate_manifest"
        ),
        {},
    )
    command_labels = {str(gate["id"]) for gate in preflight_commands}
    full_release_dependencies = [str(value) for value in list(release_row.get("depends_on") or [])]
    commands.append({
        "label": "release_gate_manifest",
        "command": release_command,
        "depends_on": [value for value in full_release_dependencies if value in command_labels],
        "external_depends_on": [value for value in full_release_dependencies if value not in command_labels],
    })
    runs: list[dict[str, Any]] = []
    if args.resume:
        resume_path = ROOT / "artifacts" / "verification" / "run_manifests" / f"{args.resume}.json"
        try:
            run_manifest = json.loads(resume_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"cannot resume run manifest {resume_path}: {exc}")
        if not isinstance(run_manifest, dict) or str(run_manifest.get("run_id") or "") != args.resume:
            raise SystemExit(f"invalid resume manifest: {resume_path}")
        if str(run_manifest.get("tier") or "") != args.tier:
            raise SystemExit(
                f"resume tier mismatch: manifest={run_manifest.get('tier')!r} requested={args.tier!r}"
            )
        current_recipe_manifest = new_run_manifest(
            commands=commands, mode="execute", tier=args.tier
        )
        expected_recipe = current_recipe_manifest["recipe_hash"]
        if str(run_manifest.get("recipe_hash") or "") != expected_recipe:
            raise SystemExit("resume recipe mismatch: manifest commands/tier no longer match current release plan")
        if str(run_manifest.get("status") or "") not in {"RUNNING", "ABORTED", "FAIL"}:
            raise SystemExit(
                "resume requires an incomplete RUNNING/ABORTED/FAIL manifest; "
                f"got {run_manifest.get('status')!r}"
            )
        for field in ("source_code_hash", "verifier_code_hash", "release_plan_hash"):
            if run_manifest.get(field) != current_recipe_manifest.get(field):
                raise SystemExit(
                    f"resume {field} mismatch: repository/verifier/release plan changed; "
                    "start a new canonical run"
                )
        run_manifest["status"] = "RUNNING"
        run_manifest["runner_pid"] = os.getpid()
        run_manifest["resumed_at"] = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        run_manifest["resume_count"] = int(run_manifest.get("resume_count") or 0) + 1
    else:
        run_manifest = new_run_manifest(
            commands=commands,
            mode="execute" if args.execute else "print",
            tier=args.tier,
        )

    def _persist_run_manifest() -> Path:
        """Merge nested release-gate rows before the parent writes its copy."""
        path = ROOT / "artifacts" / "verification" / "run_manifests" / f"{run_manifest['run_id']}.json"
        try:
            persisted = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            persisted = {}
        if isinstance(persisted, dict) and persisted.get("release_gate_results"):
            run_manifest["release_gate_results"] = list(persisted["release_gate_results"])
        return write_manifest(run_manifest)

    run_manifest_path = _persist_run_manifest()
    run_started = str(run_manifest.get("started_at") or "").replace("Z", "+00:00")
    run_started_epoch = datetime.fromisoformat(run_started).timestamp() if run_started else None
    if args.execute:
        existing_results = {
            str(row.get("label") or ""): row
            for row in list(run_manifest.get("results") or [])
            if isinstance(row, dict)
        }
        source_hash = str(dict(run_manifest.get("source_code_hash") or {}).get("fingerprint") or "")

        def _resume_result_is_valid(label: str) -> bool:
            result = existing_results.get(label)
            if not result or not result.get("passed"):
                return False
            binding = dict(result.get("artifact_binding") or {})
            artifact = Path(str(binding.get("artifact_path") or ""))
            return bool(
                str(binding.get("verification_run_id") or "") == str(run_manifest["run_id"])
                and str(binding.get("source_code_hash") or "") == source_hash
                and str(binding.get("recipe_hash") or "") == str(run_manifest.get("recipe_hash") or "")
                and binding.get("artifact_sha256")
                and artifact.exists()
                and file_sha256(artifact) == binding.get("artifact_sha256")
            )

        source_hash = str(dict(run_manifest.get("source_code_hash") or {}).get("fingerprint") or "")
        recipe_hash = str(run_manifest.get("recipe_hash") or "")

        def _execute_gate(gate: dict[str, Any]) -> dict[str, Any]:
            label = str(gate["id"])
            command = str(gate["command"])
            return _bind_artifact(
                _run(
                    label,
                    command,
                    timeout_s=int(gate.get("timeout_s") or 1200),
                    run_id=str(run_manifest["run_id"]),
                ),
                label,
                run_id=str(run_manifest["run_id"]),
                source_code_hash=source_hash,
                recipe_hash=recipe_hash,
                run_started_epoch=run_started_epoch,
            )

        pending = {str(gate["id"]): gate for gate in preflight_commands}
        completed: set[str] = set()
        failed_ids: set[str] = set()
        for gate in preflight_commands:
            label = str(gate["id"])
            if args.resume and _resume_result_is_valid(label):
                skipped = dict(existing_results[label])
                skipped.update(
                    {
                        "label": label,
                        "command": str(gate["command"]),
                        "skipped": True,
                        "resume_reused": True,
                    }
                )
                runs.append(skipped)
                completed.add(label)
                pending.pop(label, None)

        while pending:
            blocked = [
                gate
                for gate in pending.values()
                if any(dependency in failed_ids for dependency in list(gate.get("depends_on") or []))
            ]
            for gate in blocked:
                label = str(gate["id"])
                blocked_by = [
                    dependency
                    for dependency in list(gate.get("depends_on") or [])
                    if dependency in failed_ids
                ]
                result = {
                    "label": label,
                    "command": str(gate["command"]),
                    "returncode": None,
                    "passed": False,
                    "skipped": True,
                    "blocked_by_failed_dependencies": blocked_by,
                    "failure_classification": "dependency_failed",
                    "stdout": "",
                    "stderr": "",
                }
                runs.append(result)
                run_manifest["results"].append(result)
                pending.pop(label, None)
                failed_ids.add(label)
            ready = [
                gate
                for gate in pending.values()
                if all(
                    dependency in completed
                    for dependency in list(gate.get("depends_on") or [])
                )
            ]
            if not ready:
                if blocked:
                    _persist_run_manifest()
                    continue
                raise SystemExit("canonical prerequisite dependency graph cannot make progress")
            if args.tier == "fast" and args.max_workers > 1 and len(ready) > 1:
                workers = min(args.max_workers, len(ready))
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="canonical-fast") as pool:
                    future_by_id = {
                        str(gate["id"]): pool.submit(_execute_gate, gate)
                        for gate in ready
                    }
                    ready_results = {
                        label: future.result()
                        for label, future in future_by_id.items()
                    }
            else:
                ready_results = {
                    str(gate["id"]): _execute_gate(gate)
                    for gate in ready
                }
            for gate in ready:
                label = str(gate["id"])
                result = ready_results[label]
                result["parallel_group"] = [str(item["id"]) for item in ready]
                runs.append(result)
                run_manifest["results"].append(result)
                pending.pop(label, None)
            _persist_run_manifest()
            failed = [ready_results[str(gate["id"])] for gate in ready if not ready_results[str(gate["id"])] ["passed"]]
            failed_ids.update(str(row["label"]) for row in failed)
            completed.update(
                str(gate["id"])
                for gate in ready
                if ready_results[str(gate["id"])].get("passed") is True
            )
        if not runs or all(row["passed"] for row in runs):
            release_existing = _resume_result_is_valid("release_gate_manifest")
            if args.resume and release_existing:
                skipped = dict(existing_results["release_gate_manifest"])
                skipped.update({"label": "release_gate_manifest", "command": release_command, "skipped": True, "resume_reused": True})
                runs.append(skipped)
                run_manifest["release_gate_results"] = list(run_manifest.get("release_gate_results") or [])
            else:
                result = _bind_artifact(
                    _run(
                        "release_gate_manifest",
                        release_command,
                        timeout_s=7200 if args.tier in {"all", "live"} else 1200,
                        run_id=str(run_manifest["run_id"]),
                    ),
                    "release_gate_manifest",
                    run_id=str(run_manifest["run_id"]),
                    source_code_hash=str(
                        dict(run_manifest.get("source_code_hash") or {}).get("fingerprint") or ""
                    ),
                    recipe_hash=str(run_manifest.get("recipe_hash") or ""),
                    run_started_epoch=run_started_epoch,
                )
                runs.append(result)
                run_manifest["results"].append(result)
                _persist_run_manifest()

    # A plan print is not verification.  Keep it successful as a command, but
    # give it a non-certifying status so it cannot be mistaken for release
    # evidence by a caller or a future artifact scan.
    run_status = (
        "PLAN_ONLY"
        if not args.execute
        else "PASS" if all(row["passed"] for row in runs) else "FAIL"
    )
    if run_manifest_path.exists():
        try:
            persisted = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            if isinstance(persisted, dict) and persisted.get("release_gate_results"):
                run_manifest["release_gate_results"] = list(persisted["release_gate_results"])
        except Exception:
            pass
    run_manifest_path = finish_manifest(run_manifest, status=run_status)

    final_artifact_checks = _final_artifact_checks(tier=args.tier, run_manifest=run_manifest)
    status = (
        "PLAN_ONLY"
        if not args.execute
        else "PASS"
        if all(row["passed"] for row in runs)
        and all(row["passed"] for row in final_artifact_checks.values())
        else "FAIL"
    )
    payload = {
        "schema": "design_brain.canonical_verification_runner.v1",
        "status": status,
        "mode": "execute" if args.execute else "print",
        "tier": args.tier,
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "commands": commands,
        "runs": runs,
        "final_artifact_checks": final_artifact_checks,
        "automatic_deletion": False,
        "reconciled_abandoned_runs": reconciled_runs,
        "run_id": run_manifest["run_id"],
        "run_manifest": str(run_manifest_path),
    }
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"canonical_verification_runner_{stamp}.json"
    report_path = AUDIT_DIR / f"canonical_verification_runner_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"canonical_verification_runner {status}")
    print(f"mode={payload['mode']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status in {"PASS", "PLAN_ONLY"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
