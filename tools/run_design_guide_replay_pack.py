from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = "tools/replay_cases/design_guide_contract/manifest.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_path(raw_path: str, *, repo_root: Path, manifest_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path

    repo_relative = repo_root / path
    if repo_relative.exists():
        return repo_relative

    manifest_relative = manifest_dir / path
    if manifest_relative.exists():
        return manifest_relative

    return repo_relative


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except Exception as exc:  # pragma: no cover - kept simple for CLI errors
        raise RuntimeError(f"Could not read manifest {path}: {exc}") from exc

    if not isinstance(manifest, dict):
        raise RuntimeError("Manifest root must be a JSON object.")
    if not isinstance(manifest.get("cases", []), list):
        raise RuntimeError("Manifest field 'cases' must be a list.")
    if not isinstance(manifest.get("missing", []), list):
        raise RuntimeError("Manifest field 'missing' must be a list when present.")
    return manifest


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return next((group for group in match.groups() if group), match.group(0)).strip()
    return None


def _extract_classification(output: str) -> str:
    patterns = [
        r'"failure_classification"\s*:\s*"([^"]+)"',
        r"'failure_classification'\s*:\s*'([^']+)'",
        r'"classification"\s*:\s*"([^"]+)"',
        r"'classification'\s*:\s*'([^']+)'",
        r'"failure_reason"\s*:\s*"([^"]+)"',
        r"'failure_reason'\s*:\s*'([^']+)'",
        r'"reason"\s*:\s*"([^"]+)"',
        r"'reason'\s*:\s*'([^']+)'",
        r"\bFAIL:\s*([^\r\n]+)",
        r"\bfailed:\s*([^\r\n]+)",
    ]
    return _first_match(patterns, output) or "unknown"


def _extract_artifact_path(output: str) -> str:
    patterns = [
        r'"artifact_dir"\s*:\s*"([^"]+)"',
        r"'artifact_dir'\s*:\s*'([^']+)'",
        r"\bArtifact:\s*([^\r\n]+)",
        r"\bartifact:\s*([^\r\n]+)",
        r"([A-Za-z]:\\[^\r\n\"']*artifacts\\[^\r\n\"']+)",
        r"([^\s\"']*artifacts/[^\s\"']+)",
    ]
    found = _first_match(patterns, output)
    if not found:
        return "-"
    return found.strip().rstrip(".,")


def _short_path(path: str) -> str:
    if not path or path == "-":
        return "-"
    marker = "artifacts"
    normalised = path.replace("\\", "/")
    index = normalised.lower().find(marker)
    if index >= 0:
        return normalised[index:]
    return path


def _print_table(rows: list[dict[str, str]]) -> None:
    headers = ["Case", "File", "Result", "Classification", "Artifact"]
    table = [
        [
            row["case"],
            row["file"],
            row["result"],
            row["classification"],
            row["artifact"],
        ]
        for row in rows
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table)) if table else len(headers[index])
        for index in range(len(headers))
    ]

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"

    print(fmt(headers))
    print("|" + "|".join("-" * (width + 2) for width in widths) + "|")
    for row in table:
        print(fmt(row))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the stable Design Guide replay regression pack.")
    parser.add_argument("--port", default=9301, type=int, help="Port passed to the live fuzz verifier.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Replay pack manifest path.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    manifest_path = _resolve_path(args.manifest, repo_root=repo_root, manifest_dir=repo_root)

    try:
        manifest = _load_manifest(manifest_path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    manifest_dir = manifest_path.parent
    verifier = repo_root / "tools" / "browser_live_design_guide_fuzz_verifier.py"
    rows: list[dict[str, str]] = []
    failures = 0
    executed = 0
    missing_from_manifest = list(manifest.get("missing", []))
    missing_case_files: list[dict[str, str]] = []

    print("Design Guide replay regression pack")
    print(f"Manifest: {manifest_path.relative_to(repo_root) if manifest_path.is_relative_to(repo_root) else manifest_path}")
    print(f"Port: {args.port}")
    print()

    for entry in manifest.get("cases", []):
        if not isinstance(entry, dict):
            missing_case_files.append({"name": "<invalid-entry>", "reason": "Manifest case entry is not an object."})
            continue
        name = str(entry.get("name") or "<unnamed>")
        raw_case_file = str(entry.get("case_file") or "")
        if not raw_case_file:
            missing_case_files.append({"name": name, "reason": "No case_file field."})
            continue
        case_path = _resolve_path(raw_case_file, repo_root=repo_root, manifest_dir=manifest_dir)
        if not case_path.exists():
            missing_case_files.append({"name": name, "reason": f"Missing case file: {raw_case_file}"})
            rows.append(
                {
                    "case": name,
                    "file": Path(raw_case_file).name,
                    "result": "SKIP",
                    "classification": "missing_case_file",
                    "artifact": "-",
                }
            )
            continue

        executed += 1
        command = [
            sys.executable,
            str(verifier),
            "--replay-case",
            str(case_path),
            "--port",
            str(args.port),
        ]
        completed = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        passed = completed.returncode == 0
        if not passed:
            failures += 1
        rows.append(
            {
                "case": name,
                "file": case_path.name,
                "result": "PASS" if passed else "FAIL",
                "classification": "-" if passed else _extract_classification(output),
                "artifact": _short_path(_extract_artifact_path(output)),
            }
        )

    _print_table(rows)
    print()
    print(f"Added cases count: {len(manifest.get('cases', []))}")
    print(f"Missing cases count: {len(missing_from_manifest) + len(missing_case_files)}")

    if missing_from_manifest or missing_case_files:
        print("Missing cases:")
        for item in missing_from_manifest:
            if isinstance(item, dict):
                print(f"- {item.get('name', '<unnamed>')}: {item.get('reason', 'No reason provided.')}")
            else:
                print(f"- {item}")
        for item in missing_case_files:
            print(f"- {item['name']}: {item['reason']}")
    else:
        print("Missing cases: none")

    if executed == 0:
        print("Final status: WARN - no cases were executed")
        return 3
    if failures:
        print("Final status: FAIL")
        return 1
    print("Final status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
