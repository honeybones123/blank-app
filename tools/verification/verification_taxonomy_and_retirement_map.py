"""Classify verification scripts by release relevance and deletion safety.

This is proof-only. It does not run verifiers or delete files. The goal is to
make the verification system legible: release gates, family locks, shared-path
locks, focused regressions, audit-only scripts, historical parity checks, and
possible deletion candidates should not all look equally authoritative.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

# Explicit replacement map. These are only promoted to retirement candidates
# after the current replacement has passed its composed lock and all callsite
# scans are clear.
REPLACED_VERIFIERS = {
    "tools/verification/" + "compute_cta_button_source_precedence_snapshot.py":
        "tools/verification/design_guide_cta_source_precedence_current_snapshot.py",
}
MANIFEST_PATH = VERIFICATION_DIR / "release_gate_manifest.json"


TAXONOMY_CLASSES = {
    "RELEASE_GATE",
    "REQUIRED_PREREQUISITE",
    "FAMILY_LOCK_GATE",
    "SHARED_PATH_LOCK",
    "FOCUSED_REGRESSION",
    "LIVE_BUG_REGRESSION",
    "AUDIT_ONLY",
    "HISTORICAL_PARITY",
    "DELETION_CANDIDATE",
    "STALE_OR_REPLACED",
}

CANONICAL_CATEGORIES = {
    "CANONICAL_RELEASE_GATE",
    "REQUIRED_PREREQUISITE",
    "AUDIT_ONLY",
    "DIAGNOSTIC_ONLY",
    "COMPATIBILITY_HISTORY",
    "OBSOLETE",
}


def _canonical_category(taxonomy: str) -> str:
    """Map detailed buckets to the six release-governance categories."""
    if taxonomy == "RELEASE_GATE":
        return "CANONICAL_RELEASE_GATE"
    if taxonomy in {"REQUIRED_PREREQUISITE", "FAMILY_LOCK_GATE", "SHARED_PATH_LOCK"}:
        return "REQUIRED_PREREQUISITE"
    if taxonomy == "AUDIT_ONLY":
        return "AUDIT_ONLY"
    if taxonomy in {"HISTORICAL_PARITY"}:
        return "COMPATIBILITY_HISTORY"
    if taxonomy in {"STALE_OR_REPLACED", "DELETION_CANDIDATE"}:
        return "OBSOLETE"
    return "DIAGNOSTIC_ONLY"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _release_gate_paths() -> set[str]:
    manifest = _read_json(MANIFEST_PATH)
    paths: set[str] = set()
    for gate in list(manifest.get("release_gates") or []):
        command = str(gate.get("command") or "")
        for token in command.replace("\\", "/").split():
            if token.startswith("tools/verification/") and token.endswith(".py"):
                paths.add(token)
    return paths


def _manifest_command_paths(section: str) -> set[str]:
    manifest = _read_json(MANIFEST_PATH)
    paths: set[str] = set()
    for gate in list(manifest.get(section) or []):
        if not isinstance(gate, dict):
            continue
        command = str(gate.get("command") or "")
        for token in command.replace("\\", "/").split():
            if token.startswith("tools/verification/") and token.endswith(".py"):
                paths.add(token)
    return paths


def _latest_artifact_index() -> dict[str, Path]:
    indexed: dict[str, Path] = {}
    for path in sorted(ARTIFACT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime):
        stem = path.stem
        prefix = stem.rsplit("_20", 1)[0] if "_20" in stem else stem
        indexed[prefix] = path
    return indexed


def _artifact_prefix_for(path: Path) -> str:
    return path.stem


def _referenced_verification_modules(paths: list[Path]) -> set[str]:
    """Return exact verifier modules imported or path-referenced by peers."""
    references: set[str] = set()
    import_pattern = re.compile(r"(?:from|import)\s+([A-Za-z0-9_.]+)")
    for source_path in paths:
        source = _read_text(source_path)
        for match in import_pattern.finditer(source):
            module = match.group(1).strip().rstrip(".")
            if module.startswith("tools.verification."):
                references.add(module)
            else:
                references.add(module.rsplit(".", 1)[-1])
        for match in re.finditer(r"(?:path|from):tools\.verification\.([A-Za-z0-9_.]+)", source):
            references.add(match.group(1).strip().rstrip(".").replace(".", "/"))
    return references


def _referenced_verification_paths(paths: list[Path]) -> set[str]:
    """Find literal verifier paths used by launchers and browser harnesses."""
    references: set[str] = set()
    pattern = re.compile(r"tools[\\/]verification[\\/]([A-Za-z0-9_./\\-]+\.py)")
    for source_path in paths:
        if source_path.name == "verification_taxonomy_and_retirement_map.py":
            continue
        source = _read_text(source_path)
        for match in pattern.finditer(source):
            references.add("tools/verification/" + match.group(1).replace("\\", "/"))
    return references


def _replacement_cleanup_rows() -> list[dict[str, Any]]:
    """Record explicit replacements without resurrecting deleted files.

    A replacement map can outlive the old file.  That is useful history, but
    it must be reported as completed cleanup rather than as a live verifier
    or a fresh deletion candidate.
    """
    rows: list[dict[str, Any]] = []
    for old_relative, replacement in sorted(REPLACED_VERIFIERS.items()):
        old_path = ROOT / old_relative
        replacement_path = ROOT / replacement
        rows.append(
            {
                "old_path": old_relative,
                "replacement_path": replacement,
                "old_exists": old_path.exists(),
                "replacement_exists": replacement_path.exists(),
                "status": (
                    "REPLACEMENT_CLEANUP_COMPLETE"
                    if not old_path.exists() and replacement_path.exists()
                    else "REPLACEMENT_REQUIRES_REVIEW"
                ),
            }
        )
    return rows


def _classify(
    path: Path,
    source: str,
    release_gate_paths: set[str],
    artifact_index: dict[str, Path],
    referenced_modules: set[str],
    referenced_paths: set[str],
) -> tuple[str, list[str]]:
    relative = path.relative_to(ROOT).as_posix()
    name = path.name.lower()
    reasons: list[str] = []

    # A manifest entry is authoritative even when the script also implements
    # governance. This keeps the taxonomy count identical to the canonical
    # release manifest.
    if relative in release_gate_paths:
        reasons.append("listed in release_gate_manifest")
        return "RELEASE_GATE", reasons

    if relative in REPLACED_VERIFIERS:
        replacement = REPLACED_VERIFIERS[relative]
        reasons.append(f"replaced_by:{replacement}")
        return "STALE_OR_REPLACED", reasons

    if relative in referenced_paths:
        reasons.append("literal verifier path referenced by verification code")
        return "REQUIRED_PREREQUISITE", reasons

    # These files define the canonical verification workflow itself. Their
    # policy vocabulary may mention stale/deletion candidates, but that text
    # is not evidence that the governance script is obsolete.
    canonical_governance = {
        "tools/verification/verification_taxonomy_and_retirement_map.py",
        "tools/verification/verifier_retirement_deletion_workflow.py",
        "tools/verification/verification_run_manifest.py",
        "tools/verification/verification_run_manifest_lock.py",
        "tools/verification/canonical_verification_runner.py",
    }
    if relative in canonical_governance:
        reasons.append("canonical verification governance implementation")
        return "REQUIRED_PREREQUISITE", reasons

    module_path = relative[:-3].replace("/", ".") if relative.endswith(".py") else relative.replace("/", ".")
    module_stem = path.stem
    if module_path in referenced_modules or module_stem in referenced_modules or relative[:-3] in referenced_modules:
        reasons.append("imported or path-referenced by verification code")
        return "REQUIRED_PREREQUISITE", reasons

    if path.parent.name == "families" and ("lock" in name or "contract" in name or "fuzz" in name):
        reasons.append("family verifier with lock/contract/fuzz naming")
        return "FAMILY_LOCK_GATE", reasons

    if "shared" in name and ("lock" in name or "release" in name):
        reasons.append("shared-path lock naming")
        return "SHARED_PATH_LOCK", reasons

    if "live_bug_regression_registry" in name or "live_bug" in name:
        reasons.append("live bug registry/regression naming")
        return "LIVE_BUG_REGRESSION", reasons

    # Archive location is authoritative. Check it before filename markers so
    # old snapshots/regressions cannot look active merely because of their name.
    if "archived" in path.parts and "old_or_duplicate_verifiers" in path.parts:
        reasons.append("explicitly archived under old_or_duplicate_verifiers")
        return "STALE_OR_REPLACED", reasons

    if "regression" in name or "previous_fixes" in name or "golden" in name:
        reasons.append("focused regression naming")
        return "FOCUSED_REGRESSION", reasons

    if "audit" in name or "readiness" in name or "snapshot" in name or "plan" in name:
        reasons.append("audit/readiness/snapshot/plan naming")
        return "AUDIT_ONLY", reasons

    if "parity" in name or "legacy" in name or "compatibility" in name:
        reasons.append("parity/legacy/compatibility naming")
        return "HISTORICAL_PARITY", reasons

    if "TODO_REMOVE" in source or "stale verifier" in source.lower():
        reasons.append("source indicates stale/removal")
        return "STALE_OR_REPLACED", reasons

    latest_path = artifact_index.get(_artifact_prefix_for(path))
    if latest_path is None and "if __name__" not in source:
        reasons.append("no latest artifact and no command entrypoint")
        return "DELETION_CANDIDATE", reasons

    reasons.append("default focused proof bucket")
    return "FOCUSED_REGRESSION", reasons


def _build() -> dict[str, Any]:
    release_gate_paths = _release_gate_paths()
    prerequisite_paths = _manifest_command_paths("prerequisite_gates")
    artifact_index = _latest_artifact_index()
    paths = [
        path
        for path in VERIFICATION_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    referenced_modules = _referenced_verification_modules(paths)
    referenced_paths = _referenced_verification_paths(paths)
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        source = _read_text(path)
        taxonomy, reasons = _classify(
            path,
            source,
            release_gate_paths,
            artifact_index,
            referenced_modules,
            referenced_paths,
        )
        latest_path = artifact_index.get(_artifact_prefix_for(path))
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "taxonomy": taxonomy,
                "canonical_category": _canonical_category(taxonomy),
                "reasons": reasons,
                "has_entrypoint": "if __name__" in source,
                "latest_artifact": str(latest_path) if latest_path else None,
                "latest_artifact_status": "PRESENT" if latest_path else None,
            }
        )
    counts = {key: sum(1 for row in rows if row["taxonomy"] == key) for key in sorted(TAXONOMY_CLASSES)}
    canonical_counts = {
        key: sum(1 for row in rows if row["canonical_category"] == key)
        for key in sorted(CANONICAL_CATEGORIES)
    }
    canonical_paths = release_gate_paths | prerequisite_paths
    canonical_rows = [row for row in rows if row["path"] in canonical_paths]
    non_authoritative_rows = [row for row in rows if row["path"] not in canonical_paths]
    replacement_cleanup = _replacement_cleanup_rows()
    return {
        "schema": "design_brain.verification_taxonomy_and_retirement_map.v1",
        "status": "PASS",
        "timestamp": _stamp(),
        "product_behaviour_changed": False,
        "release_gate_manifest": str(MANIFEST_PATH),
        "canonical_active_surface": {
            "release_gate_count": len(release_gate_paths),
            "prerequisite_count": len(prerequisite_paths),
            "listed_script_count": len(canonical_paths),
            "non_authoritative_inventory_count": len(non_authoritative_rows),
            "rule": "Only manifest-listed gates and prerequisites define release readiness; all other scripts are inventory, focused proof, or historical support until explicitly promoted.",
            "paths": sorted(canonical_paths),
        },
        "counts": counts,
        "canonical_category_counts": canonical_counts,
        "rows": rows,
        "deletion_candidates": [row for row in rows if row["taxonomy"] == "DELETION_CANDIDATE"],
        "stale_or_replaced": [row for row in rows if row["taxonomy"] == "STALE_OR_REPLACED"],
        "replacement_cleanup": replacement_cleanup,
        "non_authoritative_inventory": [row["path"] for row in non_authoritative_rows],
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Verification Taxonomy And Retirement Map",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Counts",
        "",
    ]
    for key, count in dict(payload["counts"]).items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Canonical Categories", ""])
    for key, count in dict(payload.get("canonical_category_counts") or {}).items():
        lines.append(f"- `{key}`: `{count}`")
    active = dict(payload.get("canonical_active_surface") or {})
    lines.extend([
        "",
        "## Canonical Active Surface",
        "",
        f"- Manifest-listed release gates: `{active.get('release_gate_count', 0)}`",
        f"- Manifest-listed prerequisites: `{active.get('prerequisite_count', 0)}`",
        f"- Listed script count: `{active.get('listed_script_count', 0)}`",
        f"- Non-authoritative inventory count: `{active.get('non_authoritative_inventory_count', 0)}`",
        "- Only manifest-listed gates and prerequisites define release readiness.",
    ])
    lines.extend(["", "## Release Gates", ""])
    for row in list(payload["rows"]):
        if row["taxonomy"] == "RELEASE_GATE":
            lines.append(f"- `{row['path']}` latest=`{row['latest_artifact_status']}`")
    lines.extend(["", "## Deletion Candidates", ""])
    candidates = list(payload["deletion_candidates"])
    if not candidates:
        lines.append("- none")
    else:
        for row in candidates[:100]:
            lines.append(f"- `{row['path']}` reasons=`{row['reasons']}`")
    if len(candidates) > 100:
        lines.append(f"- ... {len(candidates) - 100} more")
    lines.extend(["", "## Replacement Cleanup", ""])
    cleanup_rows = list(payload.get("replacement_cleanup") or [])
    if cleanup_rows:
        for row in cleanup_rows:
            lines.append(
                f"- `{row['old_path']}` -> `{row['replacement_path']}` "
                f"status=`{row['status']}` old_exists=`{row['old_exists']}` "
                f"replacement_exists=`{row['replacement_exists']}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Rule", "", "Do not delete from this report alone. Delete only after no release/focused gate imports the file and composed locks still pass."])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build()
    stamp = payload["timestamp"]
    json_path = ARTIFACT_DIR / f"verification_taxonomy_and_retirement_map_{stamp}.json"
    report_path = AUDIT_DIR / f"verification_taxonomy_and_retirement_map_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"verification_taxonomy_and_retirement_map {payload['status']}")
    print(f"verifier_count={len(payload['rows'])}")
    print(f"release_gate_count={payload['counts'].get('RELEASE_GATE', 0)}")
    print(f"deletion_candidate_count={len(payload['deletion_candidates'])}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
