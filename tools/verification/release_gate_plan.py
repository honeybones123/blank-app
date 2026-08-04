"""Canonical parser and structural validator for the release-gate plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "tools" / "verification" / "release_gate_manifest.json"
VALID_TIERS = {"fast", "live"}


def load_release_gate_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": str(exc)}
    return payload if isinstance(payload, dict) else {"_load_error": "manifest root is not an object"}


def validate_release_gate_manifest(payload: dict[str, Any]) -> list[str]:
    """Return structural defects; this function has no artifact/runtime inputs."""
    problems: list[str] = []
    if payload.get("schema") != "design_brain.release_gate_manifest.v1":
        problems.append("invalid_schema")
    if payload.get("_load_error"):
        problems.append("manifest_unreadable")
        return problems

    rows: list[tuple[str, dict[str, Any]]] = []
    for section in ("prerequisite_gates", "release_gates"):
        value = payload.get(section)
        if not isinstance(value, list) or not value:
            problems.append(f"{section}_missing_or_empty")
            continue
        for index, row in enumerate(value):
            if not isinstance(row, dict):
                problems.append(f"{section}[{index}]_not_object")
                continue
            rows.append((section, row))

    ids: dict[str, str] = {}
    commands: dict[str, str] = {}
    prefixes: dict[str, str] = {}
    known_ids: set[str] = set()
    for section, row in rows:
        gate_id = str(row.get("id") or "").strip()
        command = str(row.get("command") or "").strip()
        prefix = str(row.get("artifact_prefix") or "").strip()
        tier = str(row.get("tier") or "").strip().lower()
        required_status = str(row.get("required_status") or "").strip()
        if not gate_id:
            problems.append(f"{section}_missing_id")
        elif gate_id in ids:
            problems.append(f"duplicate_gate_id:{gate_id}")
        else:
            ids[gate_id] = section
            known_ids.add(gate_id)
        if not command:
            problems.append(f"missing_command:{gate_id or section}")
        elif command in commands:
            problems.append(f"duplicate_command:{gate_id or section}:{commands[command]}")
        else:
            commands[command] = gate_id or section
        if not prefix:
            problems.append(f"missing_artifact_prefix:{gate_id or section}")
        elif prefix in prefixes:
            problems.append(f"duplicate_artifact_prefix:{gate_id or section}:{prefixes[prefix]}")
        else:
            prefixes[prefix] = gate_id or section
        if tier not in VALID_TIERS:
            problems.append(f"invalid_tier:{gate_id or section}:{tier}")
        if not required_status:
            problems.append(f"missing_required_status:{gate_id or section}")
        required_field = str(row.get("required_field") or "").strip()
        required_value_present = "required_field_value" in row
        if required_field and not required_value_present:
            problems.append(f"required_field_value_missing:{gate_id}")
        if required_value_present and not required_field:
            problems.append(f"required_field_missing:{gate_id}")

    adjacency: dict[str, list[str]] = {}
    for section, row in rows:
        gate_id = str(row.get("id") or "").strip() or section
        dependencies = row.get("depends_on") or []
        if not isinstance(dependencies, list):
            problems.append(f"depends_on_not_list:{gate_id}")
            dependencies = []
        adjacency.setdefault(gate_id, [])
        for dependency in dependencies:
            dependency_id = str(dependency or "").strip()
            if not dependency_id:
                problems.append(f"empty_dependency:{gate_id}")
            elif dependency_id not in known_ids:
                problems.append(f"unknown_dependency:{gate_id}:{dependency_id}")
            else:
                adjacency[gate_id].append(dependency_id)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(gate_id: str) -> None:
        if gate_id in visited:
            return
        if gate_id in visiting:
            problems.append(f"dependency_cycle:{gate_id}")
            return
        visiting.add(gate_id)
        for dependency in adjacency.get(gate_id, []):
            visit(dependency)
        visiting.remove(gate_id)
        visited.add(gate_id)

    for gate_id in adjacency:
        visit(gate_id)
    return sorted(set(problems))


def release_gate_rows(payload: dict[str, Any], *, section: str) -> list[dict[str, Any]]:
    value = payload.get(section) or []
    return [row for row in value if isinstance(row, dict) and row.get("id") and row.get("command")]

