"""Install V2 into a temporary environment and run the Runtime contract."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def _python_path(environment: Path) -> Path:
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    executable = "python.exe" if sys.platform == "win32" else "python"
    return environment / scripts / executable


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--v2-checkout",
        type=Path,
        help="Checkout containing the beamapp-inputs-v2 pyproject.toml",
    )
    source.add_argument(
        "--distribution",
        type=Path,
        help="Built Inputs V2 wheel installed by the deployment",
    )
    source.add_argument(
        "--runtime-vendored",
        action="store_true",
        help="Install the vendored wheel selected by Runtime requirements.txt",
    )
    args = parser.parse_args()
    if args.v2_checkout is not None:
        distribution = args.v2_checkout.expanduser().resolve()
        if not (distribution / "pyproject.toml").is_file():
            raise FileNotFoundError(
                f"V2 pyproject.toml not found under {distribution}"
            )
    elif args.distribution is not None:
        distribution = args.distribution.expanduser().resolve()
        if not distribution.is_file() or distribution.suffix != ".whl":
            raise FileNotFoundError(f"V2 wheel not found: {distribution}")
    else:
        runtime_root = Path(__file__).resolve().parents[2]
        wheel_lines = [
            line.strip().removeprefix("./")
            for line in (runtime_root / "requirements.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip().startswith("./vendor/beamapp_inputs_v2-")
            and line.strip().endswith(".whl")
        ]
        if len(wheel_lines) != 1:
            raise AssertionError(
                "Runtime requirements must select exactly one Inputs V2 wheel"
            )
        distribution = (runtime_root / wheel_lines[0]).resolve()
        if not distribution.is_file():
            raise FileNotFoundError(f"V2 wheel not found: {distribution}")

    runtime_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="beamapp-v2-contract-") as temp:
        environment = Path(temp) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _python_path(environment)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                str(distribution),
            ],
            check=True,
            cwd=runtime_root,
        )
        subprocess.run(
            [
                str(python),
                "-m",
                "tools.verification.inputs_v2_installed_package_contract",
            ],
            check=True,
            cwd=runtime_root,
        )
    print("run_inputs_v2_clean_install_contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
