"""Validate the canonical verification run manifest and its artifact bindings.

This is a fast integrity check. It does not certify product behaviour and it
does not select the newest artifact as authority. When invoked by the
canonical runner it validates the exact manifest named by the run environment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

try:
    from tools.verification.verification_run_manifest import MANIFEST_DIR, current_run_artifact, file_sha256
except ModuleNotFoundError:  # direct ``python tools/verification/...`` execution
    from verification_run_manifest import MANIFEST_DIR, current_run_artifact, file_sha256

try:
    from tools.verification.release_gate_plan import (
        load_release_gate_manifest,
        validate_release_gate_manifest,
    )
except ModuleNotFoundError:
    from release_gate_plan import load_release_gate_manifest, validate_release_gate_manifest


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def _load_manifest() -> tuple[Path | None, dict[str, Any], list[str]]:
    problems: list[str] = []
    requested = os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST")
    if requested:
        path = Path(requested)
    else:
        paths = sorted(MANIFEST_DIR.glob("verification-*.json"), key=lambda item: item.stat().st_mtime)
        path = paths[-1] if paths else None
    if path is None or not path.exists():
        return path, {}, ["no run manifest found"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return path, {}, [f"manifest unreadable: {exc}"]
    if not isinstance(payload, dict):
        return path, {}, ["manifest root is not an object"]
    return path, payload, problems


def _check_manifest(path: Path | None, payload: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    required = (
        "schema",
        "verifier_version",
        "run_id",
        "mode",
        "tier",
        "recipe_hash",
        "source_code_hash",
        "verifier_code_hash",
        "release_plan_path",
        "release_plan_hash",
        "release_plan_dependencies",
        "artifact_paths",
        "manifest_hash",
        "commands",
        "dependencies",
        "results",
        "status",
    )
    for field in required:
        if field not in payload or payload.get(field) is None:
            problems.append(f"missing manifest field: {field}")
    plan_path = Path(str(payload.get("release_plan_path") or ""))
    current_plan = load_release_gate_manifest()
    current_plan_problems = validate_release_gate_manifest(current_plan)
    if current_plan_problems:
        problems.extend(f"current release plan: {value}" for value in current_plan_problems)
    if not plan_path.exists() or not plan_path.is_file():
        problems.append("release plan path is missing")
    else:
        actual_plan_hash = file_sha256(plan_path)
        if actual_plan_hash != payload.get("release_plan_hash"):
            problems.append("release plan hash does not match current plan")
    current_dependencies = {
        str(row["id"]): [str(value) for value in list(row.get("depends_on") or [])]
        for section in ("prerequisite_gates", "release_gates")
        for row in list(current_plan.get(section) or [])
        if isinstance(row, dict) and row.get("id")
    }
    if payload.get("release_plan_dependencies") != current_dependencies:
        problems.append("release_plan_dependencies do not match current plan")
    if not isinstance(payload.get("release_plan_dependencies"), dict):
        problems.append("release_plan_dependencies must be an object")
    if not isinstance(payload.get("artifact_paths"), dict):
        problems.append("artifact_paths must be an object")
    stored_manifest_hash = payload.get("manifest_hash")
    if not stored_manifest_hash:
        problems.append("manifest_hash is missing")
    else:
        unhashed_payload = {
            key: value for key, value in payload.items() if key != "manifest_hash"
        }
        actual_manifest_hash = hashlib.sha256(
            json.dumps(unhashed_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        if stored_manifest_hash != actual_manifest_hash:
            problems.append("manifest_hash does not match manifest contents")
    if payload.get("schema") != "design_brain.verification_run_manifest.v1":
        problems.append("unexpected manifest schema")
    if payload.get("verifier_version") != "canonical-verification-v2":
        problems.append("unexpected verifier version")
    status = str(payload.get("status") or "")
    if status not in {"RUNNING", "PASS", "FAIL", "ABORTED"}:
        problems.append("invalid manifest status")
    if status == "RUNNING" and not os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID"):
        problems.append("incomplete RUNNING manifest cannot certify outside an active canonical run")
    if payload.get("mode") not in {"print", "execute"}:
        problems.append("invalid manifest mode")
    if payload.get("tier") not in {"all", "fast", "live"}:
        problems.append("invalid manifest tier")
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        problems.append("commands must be a non-empty list")
        commands = []
    command_keys = [(str(row.get("label")), str(row.get("command"))) for row in commands if isinstance(row, dict)]
    if len(command_keys) != len(set(command_keys)):
        problems.append("duplicate manifest commands")
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, dict):
        problems.append("dependencies must be an object")
    elif set(dependencies) != {label for label, _ in command_keys}:
        problems.append("dependencies do not cover manifest commands exactly")
    else:
        labels = {label for label, _ in command_keys}
        external_dependencies = payload.get("external_dependencies") or {}
        if not isinstance(external_dependencies, dict):
            problems.append("external_dependencies must be an object")
            external_dependencies = {}
        elif set(external_dependencies) - labels:
            problems.append("external_dependencies contain unknown command labels")
        known_plan_ids = {
            str(row.get("id") or "")
            for section in ("prerequisite_gates", "release_gates")
            for row in list(load_release_gate_manifest().get(section) or [])
            if isinstance(row, dict)
        }
        graph = {
            str(label): [str(dep) for dep in list(value or [])]
            for label, value in dependencies.items()
        }
        for label, deps in graph.items():
            if label in deps:
                problems.append(f"dependency self-cycle: {label}")
            allowed_external = {
                str(dep) for dep in list(external_dependencies.get(label) or [])
            }
            unknown = sorted(set(deps) - labels)
            if unknown:
                problems.append(f"unknown dependencies for {label}: {unknown}")
            undeclared_external = sorted(allowed_external - known_plan_ids)
            if undeclared_external:
                problems.append(f"external dependencies not in release plan for {label}: {undeclared_external}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(label: str) -> None:
            if label in visited:
                return
            if label in visiting:
                problems.append(f"dependency cycle at {label}")
                return
            visiting.add(label)
            for dependency in graph.get(label, []):
                if dependency in graph:
                    visit(dependency)
            visiting.remove(label)
            visited.add(label)

        for label in graph:
            visit(label)
    expected_recipe = hashlib.sha256(
        json.dumps({"mode": payload.get("mode"), "commands": commands}, sort_keys=True).encode()
    ).hexdigest()
    if payload.get("recipe_hash") != expected_recipe:
        problems.append("recipe_hash does not match mode and commands")

    results = payload.get("results")
    if not isinstance(results, list):
        problems.append("results must be a list")
        results = []
    bound_artifacts = 0
    expected_artifact_paths: dict[str, str] = {}
    expected_run_id = str(payload.get("run_id") or "")
    expected_source = str(dict(payload.get("source_code_hash") or {}).get("fingerprint") or "")
    expected_recipe = str(payload.get("recipe_hash") or "")
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            problems.append(f"result {index} is not an object")
            continue
        if not result.get("label") or not result.get("command"):
            problems.append(f"result {index} has no label/command")
        binding = result.get("artifact_binding")
        if not isinstance(binding, dict):
            problems.append(f"result {index} has no artifact binding")
            continue
        bound_artifacts += 1
        artifact_path = Path(str(binding.get("artifact_path") or ""))
        expected_artifact_paths[str(result.get("label") or result.get("command") or "unknown")] = str(artifact_path)
        expected_sha = binding.get("artifact_sha256")
        actual_sha = file_sha256(artifact_path)
        if actual_sha is None:
            problems.append(f"result {index} artifact is missing: {artifact_path}")
        elif expected_sha != actual_sha:
            problems.append(f"result {index} artifact hash mismatch: {artifact_path}")
        if str(binding.get("verification_run_id") or "") != expected_run_id:
            problems.append(f"result {index} run_id mismatch")
        if expected_source and str(binding.get("source_code_hash") or "") != expected_source:
            problems.append(f"result {index} source_code_hash mismatch")
        if str(binding.get("recipe_hash") or "") != expected_recipe:
            problems.append(f"result {index} recipe_hash mismatch")
        for emitted in list(result.get("run_artifacts") or []):
            if not isinstance(emitted, dict):
                problems.append(f"result {index} has invalid run_artifacts entry")
                continue
            emitted_path = Path(str(emitted.get("artifact_path") or ""))
            expected_artifact_paths.setdefault(emitted_path.stem, str(emitted_path))
            emitted_hash = file_sha256(emitted_path)
            if emitted_hash is None or emitted_hash != emitted.get("artifact_sha256"):
                problems.append(f"result {index} emitted artifact hash mismatch: {emitted_path}")
            if str(emitted.get("verification_run_id") or "") != expected_run_id:
                problems.append(f"result {index} emitted artifact run_id mismatch")
            if expected_source and str(emitted.get("source_code_hash") or "") != expected_source:
                problems.append(f"result {index} emitted artifact source_code_hash mismatch")
            if str(emitted.get("recipe_hash") or "") != expected_recipe:
                problems.append(f"result {index} emitted artifact recipe_hash mismatch")
    release_results = payload.get("release_gate_results")
    if release_results is not None:
        if not isinstance(release_results, list):
            problems.append("release_gate_results must be a list")
            release_results = []
        for index, result in enumerate(release_results):
            if not isinstance(result, dict):
                problems.append(f"release gate result {index} is not an object")
                continue
            binding = result.get("artifact_binding")
            if not isinstance(binding, dict):
                problems.append(f"release gate result {index} has no artifact binding")
                continue
            artifact_path = Path(str(binding.get("artifact_path") or ""))
            expected_artifact_paths[str(result.get("label") or result.get("command") or "unknown")] = str(artifact_path)
            actual_sha = file_sha256(artifact_path)
            if actual_sha is None or actual_sha != binding.get("artifact_sha256"):
                problems.append(f"release gate result {index} artifact hash mismatch: {artifact_path}")
            if str(binding.get("verification_run_id") or "") != expected_run_id:
                problems.append(f"release gate result {index} run_id mismatch")
            if expected_source and str(binding.get("source_code_hash") or "") != str(expected_source):
                problems.append(f"release gate result {index} source_code_hash mismatch")
            if str(binding.get("recipe_hash") or "") != expected_recipe:
                problems.append(f"release gate result {index} recipe_hash mismatch")
            for emitted in list(result.get("run_artifacts") or []):
                if not isinstance(emitted, dict):
                    problems.append(f"release gate result {index} has invalid run_artifacts entry")
                    continue
                emitted_path = Path(str(emitted.get("artifact_path") or ""))
                expected_artifact_paths.setdefault(emitted_path.stem, str(emitted_path))
                emitted_hash = file_sha256(emitted_path)
                if emitted_hash is None or emitted_hash != emitted.get("artifact_sha256"):
                    problems.append(f"release gate result {index} emitted artifact hash mismatch: {emitted_path}")
                if str(emitted.get("verification_run_id") or "") != expected_run_id:
                    problems.append(f"release gate result {index} emitted artifact run_id mismatch")
                if expected_source and str(emitted.get("source_code_hash") or "") != expected_source:
                    problems.append(f"release gate result {index} emitted artifact source_code_hash mismatch")
                if str(emitted.get("recipe_hash") or "") != expected_recipe:
                    problems.append(f"release gate result {index} emitted artifact recipe_hash mismatch")
    if isinstance(payload.get("artifact_paths"), dict):
        if payload.get("artifact_paths") != expected_artifact_paths:
            problems.append("artifact_paths do not match bound result artifacts")
    env_run_id = os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_ID")
    if env_run_id and payload.get("run_id") != env_run_id:
        problems.append("manifest run_id does not match execution environment")
    return {
        "manifest_path": str(path) if path else None,
        "run_id": payload.get("run_id"),
        "mode": payload.get("mode"),
        "status": payload.get("status"),
        "command_count": len(commands),
        "result_count": len(results),
        "artifact_binding_count": bound_artifacts,
        "problems": problems,
    }


def _provenance_canary() -> dict[str, Any]:
    """Exercise direct and nested lookup against incomplete/stale provenance."""
    with tempfile.TemporaryDirectory(prefix="verification-manifest-canary-") as directory:
        artifact = Path(directory) / "canary_child_2026-01-01.json"
        artifact.write_text('{"status": "PASS"}\n', encoding="utf-8")
        digest = file_sha256(artifact)
        manifest: dict[str, Any] = {
            "run_id": "canary-run",
            "recipe_hash": "canary-recipe",
            "source_code_hash": {"fingerprint": "current-source"},
            "results": [],
            "release_gate_results": [
                {
                    "artifact_binding": {
                        "artifact_path": str(artifact),
                        "artifact_sha256": digest,
                        "verification_run_id": "canary-run",
                        "source_code_hash": "stale-source",
                        "recipe_hash": "canary-recipe",
                    }
                }
            ],
        }
        rejected = current_run_artifact("canary_child", manifest=manifest)[0] is None
        manifest["release_gate_results"][0]["artifact_binding"]["source_code_hash"] = "current-source"
        accepted = current_run_artifact("canary_child", manifest=manifest)[0] == artifact
        parent = Path(directory) / "canary_parent_2026-01-01.json"
        parent.write_text(json.dumps({"child_artifact": str(artifact)}) + "\n", encoding="utf-8")
        parent_binding = {
            "artifact_path": str(parent),
            "artifact_sha256": file_sha256(parent),
            "verification_run_id": "canary-run",
            "source_code_hash": "current-source",
            "recipe_hash": "canary-recipe",
        }
        manifest["release_gate_results"] = [{"artifact_binding": parent_binding}]
        missing_nested_provenance_rejected = current_run_artifact(
            "canary_child", manifest=manifest
        )[0] is None
        artifact.write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "verification_run_id": "canary-run",
                    "source_code_hash": {"fingerprint": "current-source"},
                    "recipe_hash": "canary-recipe",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        nested_provenance_accepted = current_run_artifact(
            "canary_child", manifest=manifest
        )[0] == artifact
    return {
        "stale_source_binding_rejected": rejected,
        "matching_source_binding_accepted": accepted,
        "missing_nested_provenance_rejected": missing_nested_provenance_rejected,
        "complete_nested_provenance_accepted": nested_provenance_accepted,
        "passed": (
            rejected
            and accepted
            and missing_nested_provenance_rejected
            and nested_provenance_accepted
        ),
    }


def main() -> int:
    path, payload, problems = _load_manifest()
    summary = _check_manifest(path, payload, problems)
    canary = _provenance_canary()
    if not canary["passed"]:
        problems.append("shared current_run_artifact provenance canary failed")
    summary["provenance_canary"] = canary
    status = "PASS" if not problems else "FAIL"
    summary.update(
        {
            "schema": "design_brain.verification_run_manifest_lock.v1",
            "status": status,
            "product_behaviour_changed": False,
        }
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"verification_run_manifest_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"verification_run_manifest_lock_{stamp}.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# Verification Run Manifest Lock\n\n"
        f"Status: `{status}`\n\n"
        f"Manifest: `{summary['manifest_path']}`\n\n"
        "## Checks\n\n"
        f"- commands: `{summary['command_count']}`\n"
        f"- results: `{summary['result_count']}`\n"
        f"- artifact bindings checked: `{summary['artifact_binding_count']}`\n"
        f"- problems: `{'; '.join(problems) if problems else 'none'}`\n",
        encoding="utf-8",
    )
    print(f"verification run manifest lock {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
