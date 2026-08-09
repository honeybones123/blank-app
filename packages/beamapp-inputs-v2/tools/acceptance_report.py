"""Emit a machine-readable acceptance snapshot for the isolated lab."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "visual-baselines" / "manifest.json").read_text(encoding="utf-8"))

report = {
    "scope": "inputs_v2_isolated_lab",
    "tests": "run pytest -q",
    "architecture": "run tools/architecture_check.py",
    "visual": {
        "status": manifest["status"],
        "states": len(manifest["states"]),
        "viewports": len(manifest["viewports"]),
    },
    "runtime_integration": "not_approved",
    "open_gates": [
        "approved current-page reference captures",
        "full current-page behaviour parity",
        "production engineering adapter parity",
        "production persistence/report/export adapters",
        "explicit integration approval",
    ],
}
print(json.dumps(report, indent=2, sort_keys=True))
