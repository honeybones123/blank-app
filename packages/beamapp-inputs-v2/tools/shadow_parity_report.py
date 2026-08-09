"""Generate a local fixture-vs-copied-engine shadow parity report."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inputs_v2.application.calculation_coordinator import calculate_fixture_current, calculate_legacy_shadow_current
from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs


CASES = (
    BeamInputs().validated(),
    BeamInputs(actions=ActionInputs(bending_moment_knm=200.0, shear_force_kn=300.0)).validated(),
    BeamInputs(width_mm=300.0, depth_mm=500.0).validated(),
)


def main() -> int:
    rows = []
    for inputs in CASES:
        fixture = calculate_fixture_current(inputs)
        shadow = calculate_legacy_shadow_current(inputs)
        rows.append({
            "revision": inputs.revision,
            "input_hash": inputs.content_hash,
            "fixture_status": fixture.status if fixture else None,
            "shadow_status": shadow.status if shadow else None,
            "fixture_families": sorted(fixture.families) if fixture else [],
            "shadow_families": sorted(shadow.families) if shadow else [],
            "shadow_bending_capacity": shadow.families.get("bending", {}).get("phi_Mu_kNm") if shadow else None,
            "shadow_shear_capacity": shadow.families.get("shear", {}).get("phi_Vu") if shadow else None,
        })
    output = ROOT / "outputs" / "shadow-parity-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema": "inputs_v2.shadow_parity.v1", "cases": rows}, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
