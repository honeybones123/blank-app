import subprocess
import sys


def test_route_isolation_verifier_passes():
    result = subprocess.run(
        [sys.executable, "tools/verification/batch_design_route_isolation.py"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"status": "PASS"' in result.stdout
