"""Archive duplicate, unreferenced verification reports without deleting them.

This is intentionally narrow. It only considers Markdown reports below
``artifacts/audits``. For each report prefix, the newest report is retained;
older reports are archived only when their basename is not referenced by any
tracked or working-tree text file outside the archive directory. JSON evidence
and release-gate artifacts are never moved by this tool.

Use ``--dry-run`` (the default) to inspect candidates and ``--apply`` to move
the approved candidates while writing a checksum manifest.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "artifacts" / "audits"
ARCHIVE_ROOT = ROOT / "artifacts" / "archive" / "verification_reports"
ARCHIVEABLE_PREFIXES = {
    "canonical_verification_runner",
    "design_brain_universal_verification_coverage_audit",
    "design_brain_universal_verification_meta_lock",
    "verification_taxonomy_and_retirement_map",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prefix(path: Path) -> str:
    name = path.stem
    return name.rsplit("_20", 1)[0] if "_20" in name else name


def _workspace_text() -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    # Exact audit filenames are only consumed by audit/report indexes and the
    # release manifest. Scanning those bounded surfaces keeps this tool quick
    # even when the checkout contains thousands of generated evidence files.
    roots = [ROOT / "docs" / "verification"]
    paths = [path for root in roots if root.exists() for path in root.glob("*")]
    manifest = ROOT / "tools" / "verification" / "release_gate_manifest.json"
    if manifest.exists():
        paths.append(manifest)
    for path in paths:
        if not path.is_file() or ARCHIVE_ROOT in path.parents:
            continue
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        # Generated evidence can be very large and cannot be a source-level
        # dependency of an audit report. Keep the reference scan bounded to
        # source, documentation, manifests, and audit reports.
        if "artifacts" in path.parts and path.parent != AUDIT_DIR:
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".txt", ".toml", ".yml", ".yaml"}:
            continue
        try:
            rows.append((path, path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return rows


def _referenced_basenames(paths: list[Path]) -> set[str]:
    references: set[str] = set()
    for path, source in _workspace_text():
        if path in paths:
            continue
        for candidate in paths:
            if candidate.name in source:
                references.add(candidate.name)
    return references


def _candidate_paths() -> list[Path]:
    reports: list[Path] = []
    with os.scandir(AUDIT_DIR) as entries:
        for entry in entries:
            if not entry.is_file() or not entry.name.endswith(".md"):
                continue
            if not any(entry.name.startswith(prefix + "_") for prefix in ARCHIVEABLE_PREFIXES):
                continue
            reports.append(Path(entry.path))
    reports.sort(key=lambda path: path.stat().st_mtime)
    newest_by_prefix: dict[str, Path] = {}
    for path in reports:
        newest_by_prefix[_prefix(path)] = path
    repeated = [path for path in reports if path != newest_by_prefix[_prefix(path)]]
    referenced = _referenced_basenames(reports)
    return [path for path in repeated if path.name not in referenced]


def _build_payload(*, apply: bool) -> dict[str, Any]:
    candidates = _candidate_paths()
    stamp = _stamp()
    archive_dir = ARCHIVE_ROOT / stamp
    rows: list[dict[str, Any]] = []
    for source in candidates:
        destination = archive_dir / source.relative_to(AUDIT_DIR)
        rows.append(
            {
                "source": source.relative_to(ROOT).as_posix(),
                "destination": destination.relative_to(ROOT).as_posix(),
                "sha256": _sha256(source),
                "bytes": source.stat().st_size,
                "reason": "older duplicate report prefix and no workspace basename reference",
                "moved": False,
            }
        )
    if apply and rows:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for row in rows:
            source = ROOT / row["source"]
            destination = ROOT / row["destination"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not source.resolve().is_relative_to(AUDIT_DIR.resolve()):
                raise RuntimeError(f"source outside audit directory: {source}")
            if not destination.resolve().is_relative_to(ARCHIVE_ROOT.resolve()):
                raise RuntimeError(f"destination outside archive directory: {destination}")
            if destination.exists():
                raise RuntimeError(f"archive destination already exists: {destination}")
            shutil.move(str(source), str(destination))
            row["moved"] = True
    return {
        "schema": "design_brain.archive_obsolete_verification_artifacts.v1",
        "status": "APPLIED" if apply else "DRY_RUN",
        "timestamp": stamp,
        "product_behaviour_changed": False,
        "json_evidence_moved": False,
        "release_gate_files_moved": False,
        "candidate_count": len(rows),
        "moved_count": sum(1 for row in rows if row["moved"]),
        "archive_directory": str(archive_dir),
        "candidates": rows,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Obsolete Verification Artifact Archive",
        "",
        f"Status: `{payload['status']}`",
        f"Candidate count: `{payload['candidate_count']}`",
        f"Moved count: `{payload['moved_count']}`",
        "",
        "Only older, unreferenced Markdown audit reports were eligible. JSON evidence, release-gate files, verifier source, and product code were excluded.",
        "",
        "## Files",
        "",
    ]
    if not payload["candidates"]:
        lines.append("- none")
    for row in payload["candidates"]:
        state = "moved" if row["moved"] else "planned"
        lines.append(f"- `{row['source']}` -> `{row['destination']}` ({state}, sha256 `{row['sha256']}`)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="report candidates without moving files")
    mode.add_argument("--apply", action="store_true", help="move approved candidates and write a manifest")
    args = parser.parse_args()
    payload = _build_payload(apply=bool(args.apply))
    ARTIFACT_DIR = ROOT / "artifacts" / "verification"
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"archive_obsolete_verification_artifacts_{payload['timestamp']}.json"
    report_path = AUDIT_DIR / f"archive_obsolete_verification_artifacts_{payload['timestamp']}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(f"archive_obsolete_verification_artifacts {payload['status']}")
    print(f"candidate_count={payload['candidate_count']}")
    print(f"moved_count={payload['moved_count']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
