"""Prove severe-shear generation has one minimal typed application owner."""

from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _runtime(*, geometry_locked: bool):
    from inputs_application.shear_escalation_runtime import (
        ShearEscalationRuntime,
    )

    return ShearEscalationRuntime(
        reo_bar_dias=(10, 12, 16, 20, 24),
        reo_spacings=(50.0, 75.0, 100.0, 125.0, 150.0, 200.0),
        activation_shear_state=lambda state: {
            **state,
            "lig_d": 10,
            "lig_legs": 2,
            "s_lig": 200.0,
        },
        float_from_state=lambda state, key, default: float(
            state.get(key, default)
        ),
        geometry_lock_enabled=lambda _state: geometry_locked,
        int_from_state=lambda state, key, default: int(
            state.get(key, default)
        ),
        make_auto_design_candidate_key=lambda state: tuple(
            sorted(state.items())
        ),
        resolve_geometry_width_context=lambda state: (
            "b",
            "b",
            float(state["b"]),
        ),
        shear_candidate_type=lambda before, after: (
            "geometry"
            if after.get("b") != before.get("b")
            or after.get("D") != before.get("D")
            else "shear"
        ),
        shear_reinforcement_is_active=lambda state: bool(
            state.get("lig_d")
            and state.get("lig_legs")
            and state.get("s_lig")
        ),
    )


def main() -> None:
    from inputs_application.shear_escalation_runtime import (
        ShearEscalationRuntime,
        generate_escalated_shear_states,
    )

    assert is_dataclass(ShearEscalationRuntime)
    assert ShearEscalationRuntime.__dataclass_params__.frozen
    assert tuple(ShearEscalationRuntime.__dataclass_fields__) == (
        "reo_bar_dias",
        "reo_spacings",
        "activation_shear_state",
        "float_from_state",
        "geometry_lock_enabled",
        "int_from_state",
        "make_auto_design_candidate_key",
        "resolve_geometry_width_context",
        "shear_candidate_type",
        "shear_reinforcement_is_active",
    )

    state = {"b": 300.0, "D": 600.0}
    normal = generate_escalated_shear_states(
        state,
        severity_band="severe",
        runtime=_runtime(geometry_locked=False),
    )
    extreme = generate_escalated_shear_states(
        state,
        severity_band="extreme",
        runtime=_runtime(geometry_locked=False),
    )
    locked = generate_escalated_shear_states(
        state,
        severity_band="extreme",
        runtime=_runtime(geometry_locked=True),
    )

    assert normal and extreme and locked
    assert len({tuple(sorted(row.items())) for _, row in normal}) == len(
        normal
    )
    assert len({tuple(sorted(row.items())) for _, row in extreme}) == len(
        extreme
    )
    assert max(row["lig_legs"] for _, row in normal) == 6
    assert max(row["lig_d"] for _, row in normal) == 20
    assert max(row["lig_legs"] for _, row in extreme) == 6
    assert max(row["lig_d"] for _, row in extreme) == 24
    assert any(row.get("b") == 450.0 for _, row in extreme)
    assert any(row.get("D") == 750.0 for _, row in extreme)
    assert all(
        row.get("b") == 300.0 and row.get("D") == 600.0
        for _, row in locked
    )

    provider_source = (
        ROOT / "inputs_application" / "one_click_runtime_provider.py"
    ).read_text(encoding="utf-8")
    assert "ShearEscalationRuntime(" in provider_source
    assert "generate_escalated_shear_states" in provider_source
    assert "ShearCandidateGenerationRuntime" not in provider_source
    assert "_generate_shear_candidates" not in provider_source

    print(
        "PASS: severe-shear generation uses the minimal typed application "
        "runtime and preserves reinforcement-first then unlocked-geometry order"
    )


if __name__ == "__main__":
    main()
