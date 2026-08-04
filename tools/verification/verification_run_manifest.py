"""Run-scoped manifest support for the canonical verification workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid
from typing import Any

try:
    from tools.verification.source_fingerprint import compute_source_fingerprint
except ModuleNotFoundError:  # direct ``python tools/verification/...`` execution
    from source_fingerprint import compute_source_fingerprint


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = ROOT / "artifacts" / "verification" / "run_manifests"
MAX_ACTIVE_RUN_AGE_SECONDS = 6 * 60 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _release_plan_provenance() -> tuple[str | None, dict[str, list[str]]]:
    path = ROOT / "tools" / "verification" / "release_gate_manifest.json"
    plan_hash = file_sha256(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return plan_hash, {}
    graph: dict[str, list[str]] = {}
    for section in ("prerequisite_gates", "release_gates"):
        for row in list(payload.get(section) or []):
            if isinstance(row, dict) and row.get("id"):
                graph[str(row["id"])] = [str(value) for value in list(row.get("depends_on") or [])]
    return plan_hash, graph


def new_run_manifest(*, commands: list[dict[str, str]], mode: str, tier: str = "all") -> dict[str, Any]:
    source = compute_source_fingerprint(repo=ROOT)
    run_id = f"verification-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:10]}"
    recipe_hash = hashlib.sha256(
        json.dumps({"mode": mode, "commands": commands}, sort_keys=True).encode()
    ).hexdigest()
    release_plan_hash, release_plan_dependencies = _release_plan_provenance()
    return {
        "schema": "design_brain.verification_run_manifest.v1",
        "verifier_version": "canonical-verification-v2",
        "run_id": run_id,
        "mode": mode,
        "tier": tier,
        "recipe_hash": recipe_hash,
        "started_at": utc_now(),
        "finished_at": None,
        "runner_pid": os.getpid(),
        "source_fingerprint": source,
        "source_code_hash": source.get("correctness_fingerprint"),
        "verifier_code_hash": source.get("verifier_runtime_fingerprint"),
        "release_plan_path": str(ROOT / "tools" / "verification" / "release_gate_manifest.json"),
        "release_plan_hash": release_plan_hash,
        "release_plan_dependencies": release_plan_dependencies,
        "commands": commands,
        "dependencies": {
            str(row.get("label") or ""): list(row.get("depends_on") or [])
            for row in commands
        },
        "external_dependencies": {
            str(row.get("label") or ""): list(row.get("external_depends_on") or [])
            for row in commands
            if row.get("external_depends_on")
        },
        "artifact_paths": {},
        "results": [],
        "status": "RUNNING",
    }


def manifest_path(run_id: str) -> Path:
    return MANIFEST_DIR / f"{run_id}.json"


def file_sha256(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_run_artifact(
    prefix: str,
    *,
    command_contains: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """Return a hash-checked artifact bound to the active run only.

    Release-authoritative verifiers must use this helper instead of selecting
    an artifact by filename and modification time. A missing active manifest,
    missing binding, run-id mismatch, or hash mismatch is a hard miss.
    """
    active = manifest
    if active is None:
        manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
        if not manifest_path:
            return None, {}
        try:
            active = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except Exception:
            return None, {}
    if not isinstance(active, dict):
        return None, {}
    run_id = str(active.get("run_id") or "")
    expected_source = str(dict(active.get("source_code_hash") or {}).get("fingerprint") or "")
    expected_recipe = str(active.get("recipe_hash") or "")
    candidates = list(active.get("results") or []) + list(active.get("release_gate_results") or [])
    started_epoch = None
    started = str(active.get("started_at") or "").replace("Z", "+00:00")
    try:
        started_epoch = datetime.fromisoformat(started).timestamp()
    except ValueError:
        pass

    def _referenced_paths(value: Any):
        if isinstance(value, str):
            candidate = Path(value)
            if candidate.exists() and candidate.is_file():
                yield candidate
        elif isinstance(value, dict):
            for child in value.values():
                yield from _referenced_paths(child)
        elif isinstance(value, list):
            for child in value:
                yield from _referenced_paths(child)

    def _declared_nested_bindings(value: Any) -> dict[str, dict[str, Any]]:
        """Collect child bindings recorded inside a bound parent artifact.

        Composed verifiers can launch children directly, before the canonical
        runner has a chance to add a manifest-level ``run_artifacts`` entry.
        The parent artifact is already hash-checked here, so its explicit
        child binding is safe to use when the child itself predates provenance
        fields in older verifier writers.
        """
        found: dict[str, dict[str, Any]] = {}

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                binding = node.get("nested_artifact_binding")
                if isinstance(binding, dict) and binding.get("artifact_path"):
                    path_value = str(binding["artifact_path"])
                    try:
                        key = str(Path(path_value).resolve())
                    except OSError:
                        key = path_value
                    found[key] = binding
                for binding in list(node.get("nested_artifact_bindings") or []):
                    if not isinstance(binding, dict) or not binding.get("artifact_path"):
                        continue
                    path_value = str(binding["artifact_path"])
                    try:
                        key = str(Path(path_value).resolve())
                    except OSError:
                        key = path_value
                    found[key] = binding
                for child in node.values():
                    visit(child)
            elif isinstance(node, list):
                for child in node:
                    visit(child)

        visit(value)
        return found

    def _load(path: Path) -> dict[str, Any]:
        return _read_json_file(path)

    for result in reversed(candidates):
        if not isinstance(result, dict):
            continue
        if command_contains and command_contains not in str(result.get("command") or ""):
            continue
        binding = result.get("artifact_binding")
        if not isinstance(binding, dict):
            continue
        path_value = str(binding.get("artifact_path") or "")
        path = Path(path_value) if path_value else None
        if not path or not path.exists() or not path.name.startswith(f"{prefix}_"):
            continue
        if str(binding.get("verification_run_id") or "") != run_id:
            continue
        if expected_source and str(binding.get("source_code_hash") or "") != expected_source:
            continue
        if expected_recipe and str(binding.get("recipe_hash") or "") != expected_recipe:
            continue
        expected_hash = str(binding.get("artifact_sha256") or "")
        if not expected_hash or file_sha256(path) != expected_hash:
            continue
        return path, _read_json_file(path)
    # A composed gate may emit several child artifacts without printing each
    # child path. The release runner binds those files to the command result
    # in ``run_artifacts``; accept only those hash-checked files from the
    # active run.
    for result in reversed(candidates):
        if not isinstance(result, dict):
            continue
        for binding in reversed(list(result.get("run_artifacts") or [])):
            if not isinstance(binding, dict):
                continue
            path = Path(str(binding.get("artifact_path") or ""))
            if not path.exists() or not path.name.startswith(f"{prefix}_"):
                continue
            if file_sha256(path) != binding.get("artifact_sha256"):
                continue
            if str(binding.get("verification_run_id") or "") != run_id:
                continue
            if str(binding.get("recipe_hash") or "") != str(active.get("recipe_hash") or ""):
                continue
            if expected_source and str(binding.get("source_code_hash") or "") != expected_source:
                continue
            return path, _read_json_file(path)
    # Some gates run a bounded child suite and publish the child artifact
    # paths inside their own current-run artifact. Accept those children only
    # when the parent is itself bound to this run and the child was written
    # after the run began. Never scan the artifact directory by filename.
    for result in reversed(candidates):
        if not isinstance(result, dict):
            continue
        parent_binding = result.get("artifact_binding")
        if not isinstance(parent_binding, dict):
            continue
        parent_path = Path(str(parent_binding.get("artifact_path") or ""))
        if not parent_path.exists() or file_sha256(parent_path) != parent_binding.get("artifact_sha256"):
            continue
        parent_payload = _load(parent_path)
        nested_bindings = _declared_nested_bindings(parent_payload)
        for child_path in _referenced_paths(parent_payload):
            if not child_path.name.startswith(f"{prefix}_"):
                continue
            if started_epoch is not None and child_path.stat().st_mtime < started_epoch:
                continue
            child = _load(child_path)
            child_run_id = str(child.get("verification_run_id") or "")
            child_source = str(
                dict(child.get("source_code_hash") or {}).get("fingerprint")
                or child.get("source_code_hash")
                or ""
            )
            child_recipe = str(child.get("recipe_hash") or "")
            # Nested artifacts are authoritative only when they carry the
            # complete current-run provenance themselves. A bound parent is
            # insufficient unless it explicitly recorded the child path and
            # hash immediately after executing it. This preserves stale
            # artifact rejection while supporting composed child writers that
            # do not embed manifest fields in their own JSON.
            try:
                child_key = str(child_path.resolve())
            except OSError:
                child_key = str(child_path)
            declared = nested_bindings.get(child_key)
            self_provenance_ok = (
                child_run_id == run_id
                and child_source == expected_source
                and child_recipe == expected_recipe
            )
            declared_provenance_ok = bool(
                isinstance(declared, dict)
                and str(declared.get("verification_run_id") or "") == run_id
                and str(declared.get("source_code_hash") or "") == expected_source
                and str(declared.get("recipe_hash") or "") == expected_recipe
                and bool(declared.get("written_in_current_run"))
                and str(declared.get("artifact_sha256") or "") == file_sha256(child_path)
            )
            if not (self_provenance_ok or declared_provenance_ok):
                continue
            return child_path, child
    return None, {}


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_manifest(manifest: dict[str, Any]) -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    path = manifest_path(str(manifest["run_id"]))
    payload = dict(manifest)
    artifact_paths: dict[str, str] = {}
    for result in list(payload.get("results") or []) + list(payload.get("release_gate_results") or []):
        if not isinstance(result, dict):
            continue
        binding = result.get("artifact_binding")
        if isinstance(binding, dict) and binding.get("artifact_path"):
            artifact_paths[str(result.get("label") or result.get("command") or "unknown")] = str(binding["artifact_path"])
        for binding in list(result.get("run_artifacts") or []):
            if isinstance(binding, dict) and binding.get("artifact_path"):
                artifact_paths.setdefault(
                    Path(str(binding["artifact_path"])).stem,
                    str(binding["artifact_path"]),
                )
    payload["artifact_paths"] = artifact_paths
    payload["manifest_hash"] = hashlib.sha256(
        json.dumps({key: value for key, value in payload.items() if key != "manifest_hash"}, sort_keys=True, default=str).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def finish_manifest(manifest: dict[str, Any], *, status: str) -> Path:
    manifest["finished_at"] = utc_now()
    manifest["status"] = status
    return write_manifest(manifest)


def _process_exists(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError):
        return False
    return True


def _manifest_age_seconds(payload: dict[str, Any]) -> float | None:
    started = str(payload.get("started_at") or "").strip()
    if not started:
        return None
    try:
        value = datetime.fromisoformat(started.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - value).total_seconds())


def reconcile_incomplete_manifests(*, exclude_run_id: str | None = None) -> list[str]:
    """Mark abandoned RUNNING manifests so they cannot look authoritative."""
    changed: list[str] = []
    for path in MANIFEST_DIR.glob("verification-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict) or payload.get("status") != "RUNNING":
            continue
        run_id = str(payload.get("run_id") or "")
        if exclude_run_id and run_id == exclude_run_id:
            continue
        try:
            pid = int(payload.get("runner_pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        age_seconds = _manifest_age_seconds(payload)
        if _process_exists(pid) and (
            age_seconds is None or age_seconds <= MAX_ACTIVE_RUN_AGE_SECONDS
        ):
            continue
        payload["status"] = "ABORTED"
        payload["finished_at"] = utc_now()
        payload["termination_reason"] = (
            "runner_process_stale_or_pid_reused"
            if age_seconds is not None and age_seconds > MAX_ACTIVE_RUN_AGE_SECONDS
            else "runner_process_missing_or_legacy_manifest"
        )
        write_manifest(payload)
        changed.append(run_id or path.name)
    return changed
