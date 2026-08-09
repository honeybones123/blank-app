from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from inputs_v2.domain.beam_inputs import BeamInputs, DeflectionInputs, TimeDependentInputs, VoidInputs


def test_time_dependent_and_void_inputs_are_canonical_and_hashed() -> None:
    current = BeamInputs().validated()
    command = UpdateFirstSlice(
        width_mm=current.width_mm,
        depth_mm=current.depth_mm,
        bottom_mode=current.bottom.mode,
        bottom_bars=current.bottom.bars,
        bottom_spacing_mm=current.bottom.spacing_mm,
        bottom_diameter_mm=current.bottom.diameter_mm,
        bottom_cover_mm=current.bottom.cover_mm,
        shrinkage_time_days=730,
        creep_time_days=540,
        age_at_loading_days=56,
        duct_count=2,
        duct_diameter_mm=80,
    )
    updated = apply_input_command(current, command)
    assert updated.time_dependent == TimeDependentInputs(730, 540, 56)
    assert updated.voids == VoidInputs(2, 80)
    assert updated.content_hash != current.content_hash


def test_deflection_inputs_are_applied_and_validated() -> None:
    current = BeamInputs().validated()
    command = UpdateFirstSlice(
        width_mm=current.width_mm, depth_mm=current.depth_mm,
        bottom_mode=current.bottom.mode, bottom_bars=current.bottom.bars,
        bottom_spacing_mm=current.bottom.spacing_mm,
        bottom_diameter_mm=current.bottom.diameter_mm,
        bottom_cover_mm=current.bottom.cover_mm,
        deflection_support_condition="Cantilever", deflection_limit_ratio=300.0,
    )
    updated = apply_input_command(current, command)
    assert updated.deflection == DeflectionInputs("Cantilever", 300.0)


def test_void_diameter_without_ducts_is_rejected() -> None:
    try:
        VoidInputs(ducts=0, diameter_mm=80).validated()
    except ValueError as exc:
        assert "diameter" in str(exc)
    else:
        raise AssertionError("invalid void input was accepted")
