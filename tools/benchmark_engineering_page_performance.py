"""Repeatable shell-import and beam-solver performance evidence."""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHELL_IMPORT_BASELINE_MS = {
    "sfd_bmd_page": 509.83929994981736,
    "bending_page": 471.0464000236243,
    "shear_page": 467.3141000093892,
    "crack_page": 456.86359994579107,
    "deflection": 455.8162000030279,
}

from beam_diagram_runtime import (
    compute_diagram_arrays,
    diagram_solver_cache_clear,
    diagram_solver_cache_info,
)


def _timed_solver(case: str, span: float, params: dict, repeats: int = 40) -> dict:
    diagram_solver_cache_clear()
    started = time.perf_counter()
    compute_diagram_arrays(case, span, params)
    cold_ms = (time.perf_counter() - started) * 1000.0
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        compute_diagram_arrays(case, span, params)
        samples.append((time.perf_counter() - started) * 1000.0)
    hot_median_ms = statistics.median(samples)
    return {
        "cold_ms": cold_ms,
        "hot_median_ms": hot_median_ms,
        "hot_mean_ms": statistics.mean(samples),
        "speedup_x": cold_ms / max(hot_median_ms, 1e-12),
        "cache": diagram_solver_cache_info()._asdict(),
    }


def _cold_shell_import(module: str, repeats: int = 5) -> dict:
    samples = []
    command = (
        "import time;"
        "started=time.perf_counter();"
        f"import {module};"
        "print((time.perf_counter()-started)*1000)"
    )
    for _ in range(repeats):
        output = subprocess.check_output(
            [sys.executable, "-c", command],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        samples.append(float(output.strip().splitlines()[-1]))
    return {"median_ms": statistics.median(samples), "samples_ms": samples}


def main() -> int:
    shell_after = {
        module: _cold_shell_import(module)
        for module in SHELL_IMPORT_BASELINE_MS
    }
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "shell_cold_import_before_ms": SHELL_IMPORT_BASELINE_MS,
        "shell_cold_import_after_ms": shell_after,
        "shell_cold_import_improvement": {
            module: {
                "saved_ms": SHELL_IMPORT_BASELINE_MS[module]
                - shell_after[module]["median_ms"],
                "speedup_x": SHELL_IMPORT_BASELINE_MS[module]
                / shell_after[module]["median_ms"],
            }
            for module in SHELL_IMPORT_BASELINE_MS
        },
        "beam_solver": {
            "single_udl": _timed_solver(
                "Simple beam – UDL over entire span",
                6.0,
                {
                    "w": 25.0,
                    "support_condition": "Simply supported",
                    "beam_system_mode": "Single span",
                },
            ),
            "multispan": _timed_solver(
                "Multi-span continuous beam",
                12.0,
                {
                    "beam_system_mode": "Multi-span",
                    "node_positions_m": [0.0, 4.0, 8.0, 12.0],
                    "support_types": ["Pinned", "Roller", "Roller", "Pinned"],
                    "point_loads": [{"x_m": 2.0, "P_kN": 40.0}],
                    "udl_loads": [
                        {
                            "x_start_m": 0.0,
                            "x_end_m": 12.0,
                            "w_kN_per_m": 18.0,
                        }
                    ],
                },
            ),
        },
    }
    output_dir = ROOT / "artifacts" / "performance"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "engineering_page_shell_and_solver_after.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"artifact={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
