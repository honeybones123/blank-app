from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
ARCHIVE_ROOT = REPO / "artifacts" / "archive" / "verification_outputs"

ROOT_FILE_FAMILIES: dict[str, list[str]] = {
    "super_verification": ["super_verification_*.json"],
    "compact_review": ["compact_review_*.md", "compact_review_*.json"],
    "recommendation_contract": ["recommendation_contract_ladder_*.json"],
    "real_user_design_guide": ["real_user_design_guide_ladder_*.json"],
    "local_cleanup_apply_effectiveness": ["local_cleanup_apply_effectiveness_ladder_*.json"],
    "optimisation_expectation": ["optimisation_expectation_ladder_*.json"],
    "summary_truth": ["summary_truth_ladder_*.json"],
    "shear_overdesign": ["shear_overdesign_debug_ladder_*.json"],
    "golden_ladder": ["full_golden_ladder_rerun_*.json"],
    "design_guide_tracer": ["design_guide_tracer*.jsonl"],
    "streamlit_logs": ["streamlit_*.log", "streamlit_*.err.log"],
    "speed_profile": ["speed_profile_*.json"],
    "debug_json": ["debug_*.json"],
}

ARTIFACT_FILE_FAMILIES: dict[str, list[str]] = {
    "real_user_design_guide_screenshots": ["artifacts/real_user_design_guide/*"],
    "browser_artifacts": ["artifacts/browser_*", "artifacts/browser_*/*"],
    "playwright_temp": [
        "artifacts/**/*.webm",
        "artifacts/**/*.zip",
        "artifacts/**/*.trace",
        "artifacts/**/*.trace.zip",
    ],
}

PROTECTED_DIR_PARTS = {
    ".git",
    "artifacts/archive/verification_outputs",
    "artifacts/super_verification_runs",
}

PROTECTED_SUFFIXES = {
    ".py",
    ".md",
    ".rst",
    ".txt",
    ".toml",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class CleanupItem:
    path: Path
    family: str
    reason: str
    keep: bool = False

    @property
    def size(self) -> int:
        return _path_size(self.path)


def _relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(REPO.resolve())
    except ValueError:
        return path


def _rel_posix(path: Path) -> str:
    return _relative(path).as_posix()


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def _is_protected(path: Path) -> bool:
    rel = _rel_posix(path)
    rel_lower = rel.lower()
    if not path.exists():
        return True
    if any(rel_lower == part or rel_lower.startswith(part + "/") for part in PROTECTED_DIR_PARTS):
        return True
    if path.is_file() and path.suffix.lower() in PROTECTED_SUFFIXES:
        # Markdown compact reviews are explicitly eligible via root patterns.
        if path.name.startswith("compact_review_") and path.suffix.lower() in {".md", ".json"}:
            return False
        return True
    return False


def _unique(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _family_candidates(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(REPO.glob(pattern))
    return [p for p in _unique(paths) if p.exists() and not _is_protected(p)]


def collect_items(keep_latest: int) -> tuple[list[CleanupItem], list[CleanupItem]]:
    kept: list[CleanupItem] = []
    removable: list[CleanupItem] = []

    for family, patterns in {**ROOT_FILE_FAMILIES, **ARTIFACT_FILE_FAMILIES}.items():
        candidates = _family_candidates(patterns)
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        family_keep_latest = keep_latest
        if family.endswith("_screenshots"):
            family_keep_latest = max(keep_latest, 24)
        elif family in {"browser_artifacts", "playwright_temp"}:
            family_keep_latest = max(keep_latest, 10)
        for index, path in enumerate(candidates):
            item = CleanupItem(
                path=path,
                family=family,
                reason=f"latest {family_keep_latest} kept for family" if index < family_keep_latest else "stale verification output",
                keep=index < family_keep_latest,
            )
            (kept if item.keep else removable).append(item)

    cache_dirs = [
        p
        for p in REPO.rglob("*")
        if p.is_dir()
        and p.name in {"__pycache__", ".pytest_cache"}
        and not _is_protected(p)
    ]
    for path in _unique(cache_dirs):
        removable.append(CleanupItem(path=path, family=path.name, reason="rebuildable cache directory"))

    removable = _dedupe_items(removable)
    kept = _dedupe_items(kept)
    kept_paths = {item.path.resolve() for item in kept}
    removable = [item for item in removable if item.path.resolve() not in kept_paths]
    return kept, removable


def _dedupe_items(items: list[CleanupItem]) -> list[CleanupItem]:
    seen: set[Path] = set()
    out: list[CleanupItem] = []
    for item in items:
        key = item.path.resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _archive_item(item: CleanupItem, archive_dir: Path) -> Path:
    rel = _relative(item.path)
    destination = archive_dir / rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        suffix = datetime.now().strftime("%H%M%S")
        destination = destination.with_name(f"{destination.stem}_{suffix}{destination.suffix}")
    shutil.move(str(item.path), str(destination))
    return destination


def _delete_item(item: CleanupItem) -> None:
    if item.path.is_dir():
        shutil.rmtree(item.path)
    else:
        item.path.unlink()


def _format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num_bytes} B"


def print_summary(kept: list[CleanupItem], removable: list[CleanupItem], action: str) -> None:
    total_size = sum(item.size for item in removable)
    print("Verification output cleanup")
    print(f"Mode: {action}")
    print(f"Files/directories found: {len(kept) + len(removable)}")
    print(f"Kept latest artifacts: {len(kept)}")
    print(f"Will {action}: {len(removable)}")
    print(f"Estimated size recoverable: {_format_size(total_size)}")
    print("")
    print("Kept latest artifacts:")
    for item in kept[:80]:
        print(f"  KEEP [{item.family}] {_rel_posix(item.path)}")
    if len(kept) > 80:
        print(f"  ... {len(kept) - 80} more kept")
    print("")
    print(f"Items to {action}:")
    for item in removable:
        print(f"  {action.upper()} [{item.family}] {_rel_posix(item.path)} ({_format_size(item.size)})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean stale verification output artifacts safely.")
    parser.add_argument("--dry-run", action="store_true", help="Only print what would happen. This is the default.")
    parser.add_argument("--archive", action="store_true", help="Move stale outputs into artifacts/archive/verification_outputs.")
    parser.add_argument("--delete", action="store_true", help="Delete stale outputs. Requires --delete-confirm YES.")
    parser.add_argument("--delete-confirm", default="", help="Required as YES for delete mode.")
    parser.add_argument("--keep-latest", type=int, default=2, help="Latest artifacts to keep per family.")
    args = parser.parse_args(argv)

    modes = [bool(args.archive), bool(args.delete)]
    if sum(modes) > 1:
        parser.error("Choose only one of --archive or --delete.")
    if args.keep_latest < 1:
        parser.error("--keep-latest must be at least 1.")
    if args.delete and args.delete_confirm != "YES":
        parser.error("--delete requires --delete-confirm YES.")

    action = "archive" if args.archive else "delete" if args.delete else "dry-run"
    kept, removable = collect_items(args.keep_latest)
    print_summary(kept, removable, action)

    if action == "dry-run":
        return 0
    if not removable:
        print("\nNothing to do.")
        return 0

    if action == "archive":
        archive_dir = ARCHIVE_ROOT / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        for item in removable:
            if _is_protected(item.path):
                continue
            _archive_item(item, archive_dir)
        print(f"\nArchived stale outputs to {_rel_posix(archive_dir)}")
        return 0

    for item in removable:
        if _is_protected(item.path):
            continue
        _delete_item(item)
    print("\nDeleted stale outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
