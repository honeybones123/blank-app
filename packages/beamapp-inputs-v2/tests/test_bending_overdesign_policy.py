from inputs_v2.application.design_brain.bending_overdesign_policy import (
    generate_overdesign_geometry_cells,
    generate_reinforcement_reductions,
    generate_shear_preservation_options,
)
from inputs_v2.domain.beam_inputs import BeamInputs, LongitudinalReinforcement


def test_overdesign_geometry_search_is_bounded_and_valid() -> None:
    current = BeamInputs().validated()
    cells = generate_overdesign_geometry_cells(current, 0.4)
    assert 0 < len(cells) <= 72
    assert cells[0].width_mm == 250.0
    assert cells[0].depth_mm == 200.0
    for cell in cells:
        assert cell.width_mm >= 150.0
        assert cell.depth_mm >= 200.0
        assert cell.depth_mm <= 2.0 * cell.width_mm
        assert cell.arrangements


def test_geometry_cells_include_target_directed_reinforcement() -> None:
    current = BeamInputs(
        width_mm=275.0,
        depth_mm=475.0,
        bottom=LongitudinalReinforcement(bars=7, diameter_mm=20),
    ).validated()

    cells = generate_overdesign_geometry_cells(current, 0.61)
    target_cell = next(
        cell
        for cell in cells
        if cell.width_mm == 275.0 and cell.depth_mm == 500.0
    )
    current_effective_depth = (
        current.depth_mm
        - current.bottom.cover_mm
        - current.bottom.diameter_mm / 2.0
    )
    target = (
        current.bottom.bars
        * current.bottom.diameter_mm**2
        * current_effective_depth
        * 0.61
        / 0.925
    )
    closest = min(
        target_cell.arrangements,
        key=lambda item: abs(
            item.bars
            * item.diameter_mm**2
            * (
                target_cell.depth_mm
                - current.bottom.cover_mm
                - item.diameter_mm / 2.0
            )
            - target
        ),
    )
    error = abs(
        closest.bars
        * closest.diameter_mm**2
        * (
            target_cell.depth_mm
            - current.bottom.cover_mm
            - closest.diameter_mm / 2.0
        )
        - target
    )
    assert error / target < 0.12


def test_overdesign_geometry_locks_remove_geometry_search() -> None:
    current = BeamInputs(width_locked=True, depth_locked=True).validated()
    assert generate_overdesign_geometry_cells(current, 0.4) == ()


def test_reinforcement_cleanup_only_reduces_total_steel_index() -> None:
    current = BeamInputs().validated()
    reductions = generate_reinforcement_reductions(current)
    current_index = current.bottom.bars * current.bottom.diameter_mm**2
    assert reductions
    assert all(
        item.bars * item.diameter_mm**2 < current_index for item in reductions
    )


def test_shear_preservation_options_are_bounded_and_stronger() -> None:
    current = BeamInputs().validated()
    options = generate_shear_preservation_options(current)
    current_index = (
        current.shear.legs
        * current.shear.diameter_mm**2
        / current.shear.spacing_mm
    )
    assert 0 < len(options) <= 12
    assert all(option.reinforcement_index > current_index for option in options)
    assert list(options) == sorted(
        options,
        key=lambda option: (
            option.reinforcement_index,
            option.diameter_mm,
            option.legs,
            -option.spacing_mm,
        ),
    )
