import pytest

from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from inputs_v2.domain.beam_inputs import BeamInputs, LayoutMode, MaterialInputs


def command(**overrides) -> UpdateFirstSlice:
    values = {
        "width_mm": 250.0,
        "depth_mm": 300.0,
        "bottom_mode": LayoutMode.COUNT,
        "bottom_bars": 3,
        "bottom_spacing_mm": 150.0,
        "bottom_diameter_mm": 10,
        "bottom_cover_mm": 40.0,
    }
    values.update(overrides)
    return UpdateFirstSlice(**values)


def test_one_command_creates_one_revision() -> None:
    original = BeamInputs().validated()
    changed = apply_input_command(original, command(bottom_bars=6))
    assert original.revision == 0
    assert changed.revision == 1
    assert changed.bottom.bars == 6


def test_no_content_change_does_not_create_revision() -> None:
    original = BeamInputs().validated()
    assert apply_input_command(original, command()) is original


def test_invalid_command_is_atomic() -> None:
    original = BeamInputs().validated()
    with pytest.raises(ValueError):
        apply_input_command(original, command(width_mm=150.0, bottom_cover_mm=100.0))
    assert original == BeamInputs()


def test_canonical_model_does_not_expose_legacy_aliases() -> None:
    inputs = BeamInputs()
    assert not hasattr(inputs, "bot1_count")
    assert not hasattr(inputs, "db_bot_1")


@pytest.mark.parametrize("strength", (400.0, 600.0))
def test_reinforcement_without_modeled_product_evidence_is_rejected(strength: float) -> None:
    with pytest.raises(ValueError, match="Only 500 MPa reinforcement is supported"):
        MaterialInputs(reinforcement_strength_mpa=strength).validated()
