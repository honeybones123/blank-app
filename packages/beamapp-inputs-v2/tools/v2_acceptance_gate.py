"""Offline acceptance gate for the isolated Inputs V2 Design Brain lab."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def main() -> int:
    v1_root = Path(os.environ.get("BEAMAPP_V1_RUNTIME", r"C:\Users\jonathon\OneDrive\Documents\GitHub\complete-app - Runtime"))
    v1_before: str | None = None
    if (v1_root / ".git").exists():
        before = subprocess.run(
            ["git", "-c", f"safe.directory={v1_root}", "status", "--porcelain"],
            cwd=v1_root,
            capture_output=True,
            text=True,
        )
        if before.returncode:
            print("FAIL: unable to establish protected V1 Runtime baseline")
            return before.returncode
        v1_before = before.stdout
    python_files = list(SRC.rglob("*.py"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in python_files)
    forbidden = ("complete-app - Runtime", "import streamlit", "from streamlit")
    violations = [token for token in forbidden if token in text and token != "import streamlit"]
    # Streamlit is permitted only at the presentation entry point.
    for path in python_files:
        if path.name == "app.py":
            continue
        if "import streamlit" in path.read_text(encoding="utf-8") or "from streamlit" in path.read_text(encoding="utf-8"):
            violations.append(f"streamlit import in {path.relative_to(ROOT)}")
    if violations:
        print("FAIL: " + "; ".join(violations))
        return 1
    output_root = ROOT / ".test-output"
    output_root.mkdir(exist_ok=True)
    basetemp = tempfile.mkdtemp(prefix="acceptance-pytest-", dir=output_root)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={basetemp}",
        ],
        cwd=ROOT,
    )
    if result.returncode:
        return result.returncode
    architecture = subprocess.run([sys.executable, "tools/architecture_check.py"], cwd=ROOT)
    if architecture.returncode:
        return architecture.returncode
    parity = subprocess.run([sys.executable, "tools/shadow_parity_report.py"], cwd=ROOT)
    if parity.returncode:
        return parity.returncode
    family_audit = subprocess.run(
        [sys.executable, "tools/design_brain_completion_audit.py"], cwd=ROOT
    )
    if family_audit.returncode:
        return family_audit.returncode
    if v1_before is not None:
        after = subprocess.run(
            ["git", "-c", f"safe.directory={v1_root}", "status", "--porcelain"],
            cwd=v1_root,
            capture_output=True,
            text=True,
        )
        if after.returncode or after.stdout != v1_before:
            print("FAIL: protected V1 Runtime changed during the V2 acceptance run")
            return 1
    print("V2 acceptance gate passed: isolation, tests, architecture, parity and family recovery audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
