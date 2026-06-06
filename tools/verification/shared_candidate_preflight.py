from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_CONTRACT = Path("artifacts/contracts/shared_candidate_contract.json")
DEFAULT_ALIAS_MAP = Path("artifacts/contracts/shared_candidate_alias_map.json")
STRUCTURE_CHECK = Path("tools/verification/shared_candidate_contract_structure_check.py")
ALIAS_COVERAGE_PROBE = Path("tools/verification/shared_candidate_alias_coverage_probe.py")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path, label: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{label} missing: {path}"
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
    except Exception as exc:
        return False, f"{label} JSON parse failed: {path}: {exc}"
    return True, f"{label} JSON parses: {path}"


def _run_command(command: list[str], *, cwd: Path) -> tuple[int, str, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _extract_report_path(stdout: str) -> str | None:
    for line in stdout.splitlines():
        prefix = "Wrote JSON report:"
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lightweight shared candidate preflight. Fails on structural contract "
            "problems only; optional alias coverage remains warning-only."
        )
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--alias-map", type=Path, default=DEFAULT_ALIAS_MAP)
    parser.add_argument(
        "--with-warning-coverage",
        action="store_true",
        help="Also run the alias coverage probe as warning-only reporting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(argv or sys.argv[1:]))
    root = _repo_root()
    structural_errors: list[str] = []

    print("Shared candidate preflight")
    print("==========================")
    print("Mode: structural checks fail; alias coverage is warning-only.")
    print("")

    contract_ok, contract_message = _load_json(root / args.contract, "contract")
    alias_ok, alias_message = _load_json(root / args.alias_map, "alias map")
    print(contract_message)
    print(alias_message)
    if not contract_ok:
        structural_errors.append(contract_message)
    if not alias_ok:
        structural_errors.append(alias_message)

    if not structural_errors:
        command = [
            sys.executable,
            str(STRUCTURE_CHECK),
            "--contract",
            str(args.contract),
            "--alias-map",
            str(args.alias_map),
        ]
        code, stdout, stderr = _run_command(command, cwd=root)
        print("")
        print("Structural checker output:")
        if stdout.strip():
            print(stdout.rstrip())
        if stderr.strip():
            print(stderr.rstrip(), file=sys.stderr)
        if code != 0:
            structural_errors.append(f"structural checker failed with exit code {code}")

    alias_report_path: str | None = None
    if args.with_warning_coverage:
        command = [
            sys.executable,
            str(ALIAS_COVERAGE_PROBE),
            "--contract",
            str(args.contract),
            "--alias-map",
            str(args.alias_map),
        ]
        code, stdout, stderr = _run_command(command, cwd=root)
        alias_report_path = _extract_report_path(stdout)
        print("")
        print("Warning-only alias coverage output:")
        if stdout.strip():
            print(stdout.rstrip())
        if stderr.strip():
            print(stderr.rstrip(), file=sys.stderr)
        if code != 0:
            print(
                f"Warning-only alias coverage probe exited {code}; preflight exit is unchanged.",
                file=sys.stderr,
            )
    else:
        print("")
        print("Warning-only alias coverage probe not run.")
        print("Run with --with-warning-coverage to emit coverage reports without failing on gaps.")

    print("")
    print("Summary:")
    if structural_errors:
        print("Structural preflight: FAIL")
        for error in structural_errors:
            print(f"- {error}")
    else:
        print("Structural preflight: PASS")
    print("Alias coverage warnings: non-failing")
    if alias_report_path:
        print(f"Latest alias coverage report: {alias_report_path}")
    print("Browser/live UI checks: not run")

    return 1 if structural_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
