"""Inventory retired route-bridge references without treating them as gates.

Historical verifiers are retained as audit evidence until their provenance is
classified. This inventory makes the boundary explicit: only scripts listed
as current release gates may define readiness, and none may reference the
retired route-coordinator module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_ROOT = ROOT / "tools" / "verification"
MANIFEST = VERIFICATION_ROOT / "release_gate_manifest.json"
REGISTRY = VERIFICATION_ROOT / "legacy_verifier_registry.json"
RETIRED_TOKEN = "inputs_page_route_coordinators"


def _manifest_scripts() -> set[str]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scripts: set[str] = set()
    for section in ("prerequisite_gates", "release_gates"):
        for gate in payload.get(section, []):
            command = str(gate.get("command") or "")
            for token in command.replace("\\", "/").split():
                if token.startswith("tools/verification/") and token.endswith(".py"):
                    scripts.add(token.rsplit("/", 1)[-1])
    return scripts


def build_inventory() -> dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    current_gate_scripts = _manifest_scripts()
    historical: list[str] = []
    current_gate_hits: list[str] = []
    for path in sorted(VERIFICATION_ROOT.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        if RETIRED_TOKEN not in path.read_text(encoding="utf-8", errors="replace"):
            continue
        if path.name in current_gate_scripts:
            current_gate_hits.append(path.name)
        else:
            historical.append(path.name)
    return {
        "schema": "beam.legacy_route_bridge_inventory.v1",
        "status": "PASS" if not current_gate_hits else "FAIL",
        "retirement_status": str(registry.get("status") or "UNKNOWN"),
        "retired_token": RETIRED_TOKEN,
        "historical_reference_count": len(historical),
        "historical_references": historical,
        "current_gate_reference_count": len(current_gate_hits),
        "current_gate_references": current_gate_hits,
        "release_gate_manifest": str(MANIFEST),
        "retirement_registry": str(REGISTRY),
    }


def main() -> int:
    result = build_inventory()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
