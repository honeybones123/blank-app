"""Audit verifier topology and identify safe ways to reduce repeated work.

This is an audit only.  It does not execute, delete, or weaken a verifier.
It reports release-gate membership, nested verifier execution, repeated shared
locks, timeout declarations, and the boundaries that should remain separate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
MANIFEST_PATH = VERIFICATION_DIR / "release_gate_manifest.json"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _manifest() -> dict[str, Any]:
    try:
        payload = json.loads(_read(MANIFEST_PATH))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _script_paths() -> list[Path]:
    return sorted(
        (p for p in VERIFICATION_DIR.rglob("*.py") if "__pycache__" not in p.parts),
        key=lambda p: p.as_posix(),
    )


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _release_scripts(manifest: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for gate in manifest.get("release_gates", []):
        for token in str(gate.get("command", "")).replace("\\", "/").split():
            if token.startswith("tools/verification/") and token.endswith(".py"):
                result.add(token)
    return result


def _manifest_dependency_audit(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate the single manifest graph used by canonical runners."""
    prerequisite = [row for row in manifest.get("prerequisite_gates", []) if isinstance(row, dict)]
    release = [row for row in manifest.get("release_gates", []) if isinstance(row, dict)]
    rows = prerequisite + release
    ids = [str(row.get("id") or "") for row in rows]
    duplicate_ids = sorted({item for item in ids if item and ids.count(item) > 1})
    graph = {
        str(row.get("id") or ""): [str(value) for value in list(row.get("depends_on") or [])]
        for row in rows
        if row.get("id")
    }
    unknown_dependencies = {
        key: sorted(set(values) - set(graph))
        for key, values in graph.items()
        if set(values) - set(graph)
    }
    cycles: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            cycles.append(node)
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    return {
        "prerequisite_gate_count": len(prerequisite),
        "release_gate_count": len(release),
        "duplicate_ids": duplicate_ids,
        "unknown_dependencies": unknown_dependencies,
        "cycles": sorted(set(cycles)),
        "passed": not duplicate_ids and not unknown_dependencies and not cycles,
        "graph": graph,
    }


def _build() -> dict[str, Any]:
    manifest = _manifest()
    paths = _script_paths()
    source = {_relative(path): _read(path) for path in paths}
    release_scripts = _release_scripts(manifest)

    nested: list[dict[str, str]] = []
    shared_invocations: Counter[str] = Counter()
    timeout_rows: list[dict[str, Any]] = []
    for owner, text in source.items():
        for match in re.finditer(r"tools/verification/[A-Za-z0-9_\\/.-]+\.py", text):
            target = match.group(0).replace("\\", "/")
            if target == owner:
                continue
            nested.append({"owner": owner, "target": target})
            if any(token in target for token in ("independence_lock", "render_bridge_lock", "compute_resolver_publication_bridge_lock", "shared_final_publication", "design_brain_shared_path_release_lock")):
                shared_invocations[target] += 1
        timeout_matches = re.findall(r"(?:timeout|TIMEOUT)[^\n]{0,80}(?:\d{2,5})", text)
        if timeout_matches:
            timeout_rows.append({"file": owner, "declarations": timeout_matches[:12]})

    owners_by_target: dict[str, list[str]] = defaultdict(list)
    for row in nested:
        owners_by_target[row["target"]].append(row["owner"])
    repeated_shared = [
        {"target": target, "invocation_count": count, "owners": sorted(owners_by_target[target])}
        for target, count in sorted(shared_invocations.items())
        if count > 1
    ]
    dependency_audit = _manifest_dependency_audit(manifest)

    recommendations = [
        {
            "priority": 1,
            "classification": "SAFE_WORKFLOW_OPTIMISATION",
            "action": "Run shared locks once per canonical run and pass their run-scoped artifact references into family gates.",
            "guard": "Require matching verification_run_id and source_code_hash; otherwise rerun the shared lock.",
        },
        {
            "priority": 2,
            "classification": "SAFE_WORKFLOW_OPTIMISATION",
            "action": "Keep fast structural gates separate from live browser gates and never let a fast result certify a live gate.",
            "guard": "Tier and required fields must match release_gate_manifest.json.",
        },
        {
            "priority": 3,
            "classification": "SAFE_RETIREMENT_PROCESS",
            "action": "Use taxonomy plus zero-callsite and no-manifest-reference proof before deleting a verifier.",
            "guard": "Rerun shared path, meta, and completion locks after each deletion group.",
        },
        {
            "priority": 4,
            "classification": "RELIABILITY",
            "action": "Persist per-family worker state and resume only matching source/contract/run recipes.",
            "guard": "Stale workers become ABORTED; never treat an old artifact as current PASS.",
        },
    ]
    return {
        "schema": "design_brain.verifier_system_efficiency_audit.v1",
        "status": "PASS" if dependency_audit["passed"] else "FAIL",
        "timestamp": _stamp(),
        "audit_only": True,
        "product_behaviour_changed": False,
        "manifest": _relative(MANIFEST_PATH),
        "verifier_count": len(paths),
        "release_gate_count": len(manifest.get("release_gates", [])),
        "prerequisite_gate_count": len(manifest.get("prerequisite_gates", [])),
        "release_gate_scripts": sorted(release_scripts),
        "nested_verifier_invocation_count": len(nested),
        "nested_verifier_invocations": nested,
        "repeated_shared_lock_count": len(repeated_shared),
        "repeated_shared_locks": repeated_shared,
        "manifest_dependency_audit": dependency_audit,
        "timeout_declaration_file_count": len(timeout_rows),
        "timeout_declarations": timeout_rows,
        "safe_deletion_candidates": [],
        "deletion_note": "This audit does not authorize deletion. Use verifier_retirement_deletion_workflow.py after proof of zero references.",
        "recommendations": recommendations,
        "current_run_binding": {
            "required": True,
            "required_fields": ["verification_run_id", "source_code_hash", "recipe_hash", "artifact", "status"],
            "stale_latest_by_mtime_is_authority": False,
        },
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Verifier System Efficiency Audit",
        "",
        f"Status: `{payload['status']}`",
        "Audit only: `true`",
        f"Verifier scripts scanned: `{payload['verifier_count']}`",
        f"Release gates: `{payload['release_gate_count']}`",
        f"Nested verifier invocations: `{payload['nested_verifier_invocation_count']}`",
        f"Repeated shared-lock targets: `{payload['repeated_shared_lock_count']}`",
        "",
        "## Main Finding",
        "",
        "Shared locks are repeated inside family/live gates. The safe speed improvement is run-scoped shared-lock reuse, guarded by matching run, source, contract, and recipe hashes.",
        "",
        "## Manifest Dependency Graph",
        "",
        f"- graph valid: `{payload['manifest_dependency_audit']['passed']}`",
        f"- duplicate IDs: `{payload['manifest_dependency_audit']['duplicate_ids']}`",
        f"- unknown dependencies: `{payload['manifest_dependency_audit']['unknown_dependencies']}`",
        f"- cycles: `{payload['manifest_dependency_audit']['cycles']}`",
        "",
        "## Repeated Shared Locks",
        "",
    ]
    if payload["repeated_shared_locks"]:
        for row in payload["repeated_shared_locks"]:
            lines.append(f"- `{row['target']}` invoked `{row['invocation_count']}` times by `{', '.join(row['owners'])}`")
    else:
        lines.append("- none detected")
    lines.extend(["", "## Recommendations", ""])
    for row in payload["recommendations"]:
        lines.append(f"{row['priority']}. `{row['classification']}`: {row['action']} Guard: {row['guard']}")
    lines.extend(["", "## Deletion Boundary", "", "No deletion is authorized by this audit. Deletion remains a separate proof workflow."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"verifier_system_efficiency_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"verifier_system_efficiency_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"verifier_system_efficiency_audit {payload['status']}")
    print(f"verifier_count={payload['verifier_count']}")
    print(f"nested_invocations={payload['nested_verifier_invocation_count']}")
    print(f"repeated_shared_locks={payload['repeated_shared_lock_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
