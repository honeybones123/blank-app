"""Verifier retirement and deletion readiness workflow.

This verifier consumes the taxonomy map and proves which verifier files are
actually safe to delete. It deliberately treats helper modules as keep unless
there are no imports/callsites anywhere in the verification tree.

It does not delete files.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

try:
    from tools.verification.verification_run_manifest import current_run_artifact
except ModuleNotFoundError:
    from verification_run_manifest import current_run_artifact


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TAXONOMY_PREFIX = "verification_taxonomy_and_retirement_map"
RELEASE_MANIFEST = VERIFICATION_DIR / "release_gate_manifest.json"
PREREQUISITE_MANIFEST = RELEASE_MANIFEST


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return payload if isinstance(payload, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    # This is a composed release prerequisite.  Selecting the newest file
    # from the artifact directory would let an old taxonomy certify a new
    # deletion decision.  Outside a canonical run it is intentionally
    # non-authoritative.
    if not os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST"):
        return None, {}
    return current_run_artifact(prefix)


def _release_gate_scripts() -> set[str]:
    manifest = _read_json(RELEASE_MANIFEST)
    scripts: set[str] = set()
    for gate in list(manifest.get("prerequisite_gates") or []) + list(manifest.get("release_gates") or []):
        command = str(gate.get("command") or "").replace("\\", "/")
        for token in command.split():
            if token.startswith("tools/verification/") and token.endswith(".py"):
                scripts.add(token)
    return scripts


def _manifest_reference_rows(relative: str) -> list[dict[str, str]]:
    """Find live command/dependency references outside Python callsites.

    Historical run manifests are evidence, not active dependencies.  Including
    every old manifest here made a verifier impossible to retire after its
    final run, even when the current release plan no longer referenced it.
    The active release plan and the current canonical run manifest are the only
    manifest sources allowed to block deletion.
    """
    normalized = relative.replace("\\", "/")
    rows: list[dict[str, str]] = []
    manifest_paths = [RELEASE_MANIFEST]
    active_manifest = os.environ.get("DESIGN_BRAIN_VERIFICATION_RUN_MANIFEST")
    if active_manifest:
        active_path = Path(active_manifest)
        if not active_path.is_absolute():
            active_path = ROOT / active_path
        if active_path.exists():
            manifest_paths.append(active_path)
    for manifest_path in manifest_paths:
        text = _read_text(manifest_path).replace("\\", "/")
        if normalized in text:
            rows.append({"file": str(manifest_path.relative_to(ROOT)), "kind": "path_reference"})
        try:
            payload = json.loads(text)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for section in ("prerequisite_gates", "release_gates", "commands"):
            for gate in list(payload.get(section) or []):
                if not isinstance(gate, dict):
                    continue
                command = str(gate.get("command") or "").replace("\\", "/")
                if command and normalized in command:
                    rows.append({"file": str(manifest_path.relative_to(ROOT)), "kind": f"{section}_command"})
                dependencies = [str(value) for value in list(gate.get("depends_on") or [])]
                if Path(normalized).stem in dependencies or normalized in dependencies:
                    rows.append({"file": str(manifest_path.relative_to(ROOT)), "kind": f"{section}_dependency"})
    unique: dict[tuple[str, str], dict[str, str]] = {(row["file"], row["kind"]): row for row in rows}
    return list(unique.values())


def _verification_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in ROOT.rglob("*.py"):
        if any(part in {"__pycache__", ".git", "node_modules", ".venv", "venv"} for part in path.parts):
            continue
        sources[path.relative_to(ROOT).as_posix()] = _read_text(path)
    return sources


def _callsite_rows(relative: str, sources: dict[str, str]) -> list[dict[str, str]]:
    path = Path(relative)
    module = ".".join(path.with_suffix("").parts)
    stem = path.stem
    normalized = relative.replace("\\", "/")
    rows: list[dict[str, str]] = []
    for source_path, source in sources.items():
        if source_path == relative:
            continue
        exact_tokens: list[str] = []
        try:
            tree = ast.parse(source, filename=source_path)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in {module, stem}:
                            exact_tokens.append(f"import:{alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module in {module, stem}:
                    exact_tokens.append(f"from:{node.module}")
        if normalized in source.replace("\\", "/"):
            exact_tokens.append(f"path:{normalized}")
        if exact_tokens:
            rows.append({"file": source_path, "token": ", ".join(sorted(set(exact_tokens)))})
    return rows


def _row(candidate: dict[str, Any], release_gate_scripts: set[str], sources: dict[str, str]) -> dict[str, Any]:
    relative = str(candidate.get("path") or "")
    path = ROOT / relative
    source = sources.get(relative, "")
    callsites = _callsite_rows(relative, sources)
    manifest_references = _manifest_reference_rows(relative)
    # A function-only file is not automatically a library.  The old rule
    # blocked unreferenced recorder modules forever merely because they
    # contained ``def`` statements.  Directory/package ownership plus actual
    # callsite scanning are the deletion boundary.
    is_helper = "/helpers/" in relative or relative.endswith("/__init__.py")
    is_release_gate = relative in release_gate_scripts
    problems: list[str] = []
    if is_release_gate:
        problems.append("release_gate")
    if callsites:
        problems.append("referenced_by_verification_code")
    if manifest_references:
        problems.append("referenced_by_manifest_or_dependency")
    if is_helper and callsites:
        problems.append("helper_or_library_module")
    if not path.exists():
        problems.append("file_missing")
    safe_to_delete = not problems
    return {
        "path": relative,
        "taxonomy": candidate.get("taxonomy"),
        "taxonomy_reasons": candidate.get("reasons"),
        "exists": path.exists(),
        "has_entrypoint": candidate.get("has_entrypoint"),
        "is_helper_or_library_module": is_helper,
        "is_release_gate": is_release_gate,
        "callsite_count": len(callsites),
        "callsites": callsites[:30],
        "manifest_reference_count": len(manifest_references),
        "manifest_references": manifest_references,
        "safe_to_delete": safe_to_delete,
        "blocking_reasons": problems,
        "deletion_rule": (
            "delete only if safe_to_delete=true, then rerun release manifest, shared path lock, "
            "universal meta-lock, and completion audit"
        ),
    }


def _build() -> dict[str, Any]:
    taxonomy_path, taxonomy = _latest(TAXONOMY_PREFIX)
    if taxonomy_path is None:
        return {
            "schema": "design_brain.verifier_retirement_deletion_workflow.v1",
            "status": "NOT_AUTHORITATIVE",
            "timestamp": _stamp(),
            "product_behaviour_changed": False,
            "taxonomy_artifact": None,
            "candidate_count": 0,
            "safe_deletion_candidate_count": 0,
            "blocked_candidate_count": 1,
            "safe_deletion_candidates": [],
            "blocked_candidates": [{
                "path": "<taxonomy>",
                "blocking_reasons": ["no active canonical run manifest or same-run taxonomy artifact"],
            }],
            "deletion_authority": {
                "mode": "READINESS_ONLY",
                "automatic_deletion": False,
                "post_deletion_composed_lock": {
                    "status": "NOT_RUN",
                    "required": False,
                    "passed": None,
                    "evidence": None,
                },
                "rule": (
                    "Physical deletion requires zero live callsites, zero manifest/dependency "
                    "references, and composed locks PASS after deletion."
                ),
            },
            "mandatory_deletion_sequence": [],
        }
    release_gate_scripts = _release_gate_scripts()
    sources = _verification_sources()
    candidates = list(taxonomy.get("deletion_candidates") or []) + list(taxonomy.get("stale_or_replaced") or [])
    rows = [_row(candidate, release_gate_scripts, sources) for candidate in candidates if isinstance(candidate, dict)]
    safe_rows = [row for row in rows if row["safe_to_delete"]]
    blocked_rows = [row for row in rows if not row["safe_to_delete"]]
    # This verifier is a readiness gate, not an automatic deleter. A future
    # deletion must carry its own post-deletion composed-lock evidence.
    post_deletion_status = "NOT_REQUIRED" if not safe_rows else "NOT_RUN"
    return {
        "schema": "design_brain.verifier_retirement_deletion_workflow.v1",
        "status": "PASS",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "taxonomy_artifact": str(taxonomy_path) if taxonomy_path else None,
        "candidate_count": len(rows),
        "safe_deletion_candidate_count": len(safe_rows),
        "blocked_candidate_count": len(blocked_rows),
        "safe_deletion_candidates": safe_rows,
        "blocked_candidates": blocked_rows,
        "deletion_authority": {
            "mode": "READINESS_ONLY",
            "automatic_deletion": False,
            "post_deletion_composed_lock": {
                "status": post_deletion_status,
                "required": bool(safe_rows),
                "passed": None if not safe_rows else False,
                "evidence": None,
            },
            "rule": (
                "Physical deletion requires zero live callsites, zero manifest/dependency "
                "references, and composed locks PASS after deletion."
            ),
        },
        "mandatory_deletion_sequence": [
            "delete one small group only",
            "python -m py_compile tools/verification/check_release_gate_manifest.py",
            "python tools/verification/check_release_gate_manifest.py",
            "python tools/verification/design_brain_shared_path_release_lock.py",
            "python tools/verification/design_brain_universal_verification_meta_lock.py --enforce",
            "python tools/verification/app_stability_goal_completion_audit.py",
        ],
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Verifier Retirement Deletion Workflow",
        "",
        f"Status: `{payload['status']}`",
        f"Taxonomy artifact: `{payload['taxonomy_artifact']}`",
        f"Candidates inspected: `{payload['candidate_count']}`",
        f"Safe deletion candidates: `{payload['safe_deletion_candidate_count']}`",
        f"Blocked candidates: `{payload['blocked_candidate_count']}`",
        f"Deletion authority mode: `{payload['deletion_authority']['mode']}`",
        f"Post-deletion composed-lock proof: `"
        f"{payload['deletion_authority']['post_deletion_composed_lock']['status']}`",
        "",
        "## Safe Deletion Candidates",
        "",
    ]
    if payload["safe_deletion_candidates"]:
        for row in list(payload["safe_deletion_candidates"]):
            lines.append(f"- `{row['path']}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Blocked Candidates", ""])
    for row in list(payload["blocked_candidates"])[:100]:
        lines.append(
            f"- `{row['path']}` blocked=`{row['blocking_reasons']}` "
            f"callsites=`{row.get('callsite_count', 0)}` manifest_refs=`{row.get('manifest_reference_count', 0)}`"
        )
    if len(payload["blocked_candidates"]) > 100:
        lines.append(f"- ... {len(payload['blocked_candidates']) - 100} more")
    lines.extend(["", "## Mandatory Deletion Sequence", ""])
    for command in list(payload["mandatory_deletion_sequence"]):
        lines.append(f"- `{command}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"verifier_retirement_deletion_workflow_{stamp}.json"
    report_path = AUDIT_DIR / f"verifier_retirement_deletion_workflow_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"verifier_retirement_deletion_workflow {payload['status']}")
    print(f"safe_deletion_candidate_count={payload['safe_deletion_candidate_count']}")
    print(f"blocked_candidate_count={payload['blocked_candidate_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
