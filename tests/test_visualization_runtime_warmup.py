from __future__ import annotations

import subprocess
import sys


def test_visualization_runtime_warmup_is_one_shot_and_page_neutral() -> None:
    script = r'''
import sys
from application.visualization_runtime_warmup import (
    start_visualization_runtime_warmup,
    wait_for_visualization_runtime_warmup,
)
assert start_visualization_runtime_warmup() is True
assert start_visualization_runtime_warmup() is False
assert wait_for_visualization_runtime_warmup(timeout=5.0) is True
assert "matplotlib.pyplot" in sys.modules
assert "plotly.graph_objects" in sys.modules
assert "bending_page_runtime" not in sys.modules
assert "deflection_page_runtime" not in sys.modules
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
