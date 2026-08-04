"""Validate the canonical release-gate manifest.

This checker is intentionally small and strict.  It verifies the release gate
list itself, not the whole product.  Product readiness still comes from running
the listed release gates and then the meta/completion locks.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

try:
    from tools.verification.release_gate_plan import (
        load_release_gate_manifest,
        validate_release_gate_manifest,
    )
except ModuleNotFoundError:
    from release_gate_plan import load_release_gate_manifest, validate_release_gate_manifest


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
MANIFEST_PATH = VERIFICATION_DIR / "release_gate_manifest.json"

PASS_STATUSES = {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS"}
AUDIT_ONLY_NAME_MARKERS = ("audit", "readiness", "snapshot", "plan", "parity")
GATE_TIERS = {"fast", "live"}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _payload_status(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("completion_status")
        or payload.get("meta_lock_status")
        or "MISSING"
    ).strip()


def _status_passes(payload: dict[str, Any], required_status: str) -> bool:
    status = _payload_status(payload).upper()
    if required_status.upper() in PASS_STATUSES:
        return status in PASS_STATUSES
    return status == required_status.upper()


def _current_run_start() -> float | None:
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path:
        return None
    try:
        manifest = _read_json(Path(manifest_path))
        started = str(manifest.get("started_at") or "").replace("Z", "+00:00")
        return datetime.fromisoformat(started).timestamp()
    except Exception:
        return None


def _current_run_bindings() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST") or "").strip()
    if not manifest_path:
        return {}, []
    payload = _read_json(Path(manifest_path))
    rows = list(payload.get("results") or []) + list(payload.get("release_gate_results") or [])
    return payload, [row for row in rows if isinstance(row, dict)]


def _script_from_command(command: str) -> str | None:
    for token in command.replace("\\", "/").split():
        if token.startswith("tools/verification/") and token.endswith(".py"):
            return token
    return None


def _row(gate: dict[str, Any], current_manifest: dict[str, Any], current_bindings: list[dict[str, Any]]) -> dict[str, Any]:
    command = str(gate.get("command") or "").strip()
    script = _script_from_command(command)
    script_path = ROOT / script if script else None
    prefix = str(gate.get("artifact_prefix") or "").strip()
    artifact_path: Path | None = None
    payload: dict[str, Any] = {}
    required_field = gate.get("required_field")
    required_field_value = gate.get("required_field_value")
    problems: list[str] = []
    run_start = _current_run_start()
    current_run_id = str(current_manifest.get("run_id") or "")
    current_source = dict(current_manifest.get("source_code_hash") or {})
    matching_binding = next(
        (
            row.get("artifact_binding")
            for row in current_bindings
            if str(row.get("command") or "").split(" --", 1)[0] == command.split(" --", 1)[0]
            or str((row.get("artifact_binding") or {}).get("artifact_path") or "").endswith(Path(prefix).name)
        ),
        None,
    )
    if isinstance(matching_binding, dict):
        bound_path = Path(str(matching_binding.get("artifact_path") or ""))
        if bound_path.exists():
            artifact_path = bound_path
            payload = _read_json(bound_path)
    artifact_written_in_current_run = bool(
        artifact_path
        and run_start is not None
        and Path(artifact_path).exists()
        and Path(artifact_path).stat().st_mtime >= run_start
    )

    if not gate.get("id"):
        problems.append("missing_id")
    if run_start is None:
        problems.append("canonical_run_manifest_required")
    if str(gate.get("tier") or "").strip().lower() not in GATE_TIERS:
        problems.append("missing_or_invalid_tier")
    if not command:
        problems.append("missing_command")
    if gate.get("id") == "universal_live_family_lock" and "--resume" in command.split():
        problems.append("canonical_universal_lock_must_not_use_resume")
    if not script:
        problems.append("command_has_no_verification_script")
    elif not script_path or not script_path.exists():
        problems.append("verification_script_missing")
    if not prefix:
        problems.append("missing_artifact_prefix")
    if script and any(marker in Path(script).stem.lower() for marker in AUDIT_ONLY_NAME_MARKERS):
        if gate.get("id") not in {"app_stability_completion"}:
            problems.append("audit_or_snapshot_named_script_in_release_manifest")
    if gate.get("id") == "release_gate_manifest":
        # The checker creates its own artifact at the end of this run, so a
        # missing previous artifact must not make the first run impossible.
        pass
    elif artifact_path and payload:
        if not _status_passes(payload, str(gate.get("required_status") or "PASS")):
            problems.append("latest_artifact_status_not_release_pass")
        if required_field and str(payload.get(str(required_field)) or "") != str(required_field_value):
            problems.append("latest_artifact_required_field_mismatch")
    else:
        problems.append("latest_artifact_missing")
    if run_start is not None and gate.get("id") != "release_gate_manifest" and not artifact_written_in_current_run:
        problems.append("artifact_not_written_in_current_run")
    if run_start is not None and gate.get("id") != "release_gate_manifest":
        if not isinstance(matching_binding, dict):
            problems.append("current_run_artifact_binding_missing")
        else:
            bound_path = Path(str(matching_binding.get("artifact_path") or ""))
            bound_hash = matching_binding.get("artifact_sha256")
            actual_hash = __import__("hashlib").sha256(bound_path.read_bytes()).hexdigest() if bound_path.exists() else None
            bound_source = str(matching_binding.get("source_code_hash") or "")
            expected_source = str(current_source.get("fingerprint") or "")
            if str(matching_binding.get("verification_run_id") or "") != current_run_id:
                problems.append("current_run_artifact_run_id_mismatch")
            if not bound_path.exists() or bound_hash != actual_hash:
                problems.append("current_run_artifact_hash_mismatch")
            if expected_source and bound_source != expected_source:
                problems.append("current_run_artifact_source_hash_mismatch")

    return {
        "id": gate.get("id"),
        "command": command,
        "script": script,
        "script_exists": bool(script_path and script_path.exists()),
        "artifact_prefix": prefix,
        "latest_artifact": str(artifact_path) if artifact_path else None,
        "latest_artifact_status": _payload_status(payload),
        "required_status": gate.get("required_status"),
        "required_field": required_field,
        "required_field_value": required_field_value,
        "tier": str(gate.get("tier") or "fast"),
        "observed_required_field_value": payload.get(str(required_field)) if required_field else None,
        "problems": problems,
        "manifest_entry_valid": not problems,
        "current_run_binding": {
            "required": run_start is not None,
            "run_started_epoch": run_start,
            "artifact_written_in_current_run": artifact_written_in_current_run,
        },
    }


def _build() -> dict[str, Any]:
    manifest = load_release_gate_manifest(MANIFEST_PATH)
    structural_problems = validate_release_gate_manifest(manifest)
    requested_tier = str(os.environ.get("DESIGN_BRAIN_VERIFICATION_TIER") or "all").strip().lower()
    gates = [
        gate for gate in list(manifest.get("prerequisite_gates") or []) + list(manifest.get("release_gates") or [])
        if isinstance(gate, dict)
        and (requested_tier == "all" or str(gate.get("tier") or "fast").lower() == requested_tier)
    ]
    current_manifest, current_bindings = _current_run_bindings()
    rows = [_row(gate, current_manifest, current_bindings) for gate in gates]
    failures = [row for row in rows if row["problems"]]
    if structural_problems:
        failures.append({"id": "manifest_structure", "problems": structural_problems})
    ids = [str(row.get("id") or "") for row in rows]
    duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
    if duplicate_ids:
        failures.append({"id": "manifest", "problems": ["duplicate_release_gate_ids"], "duplicate_ids": duplicate_ids})
    return {
        "schema": "design_brain.release_gate_manifest_check.v1",
        "status": "PASS" if not failures else "FAIL",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "manifest_path": str(MANIFEST_PATH),
        "tier": requested_tier,
        "release_gate_count": len(rows),
        "tier_counts": {
            tier: sum(1 for row in rows if row.get("tier") == tier)
            for tier in ("fast", "live")
        },
        "valid_release_gate_count": sum(1 for row in rows if row["manifest_entry_valid"]),
        "rows": rows,
        "failures": failures,
        "manifest_structure_problems": structural_problems,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Release Gate Manifest Check",
        "",
        f"Status: `{payload['status']}`",
        f"Release gates: `{payload['release_gate_count']}`",
        f"Valid gates: `{payload['valid_release_gate_count']}`",
        "",
        "| Gate | Script exists | Latest status | Required field | Problems |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in list(payload["rows"]):
        field = ""
        if row.get("required_field"):
            field = f"{row.get('required_field')}={row.get('observed_required_field_value')} expected {row.get('required_field_value')}"
        lines.append(
            f"| `{row.get('id')}` | `{row.get('script_exists')}` | `{row.get('latest_artifact_status')}` | "
            f"`{field}` | `{row.get('problems')}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", help="Explicit canonical run manifest path.")
    parser.add_argument(
        "--tier",
        choices=("all", "fast", "live"),
        default=None,
        help="Check one manifest tier. Omit to use DESIGN_BRAIN_VERIFICATION_TIER or all.",
    )
    args = parser.parse_args(argv)
    if args.run_manifest:
        os.environ["DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"] = str(args.run_manifest)
    if args.tier is not None:
        os.environ["DESIGN_BRAIN_VERIFICATION_TIER"] = args.tier
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"release_gate_manifest_check_{stamp}.json"
    report_path = AUDIT_DIR / f"release_gate_manifest_check_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"release_gate_manifest_check {payload['status']}")
    print(f"release_gate_count={payload['release_gate_count']}")
    print(f"valid_release_gate_count={payload['valid_release_gate_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
