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
    parser.add_argument(
        "--v2-checkout",
        type=Path,
        required=True,
        help="Checkout containing the beamapp-inputs-v2 pyproject.toml",
    )
    args = parser.parse_args()
    checkout = args.v2_checkout.expanduser().resolve()
    if not (checkout / "pyproject.toml").is_file():
        raise FileNotFoundError(f"V2 pyproject.toml not found under {checkout}")

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
                str(checkout),
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
