from __future__ import annotations

from pathlib import Path


def verification_latest_dir(repo_root: Path) -> Path:
    path = repo_root / "artifacts" / "verification" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def verification_history_dir(repo_root: Path) -> Path:
    path = repo_root / "artifacts" / "verification" / "history"
    path.mkdir(parents=True, exist_ok=True)
    return path
