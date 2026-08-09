from inputs_v2.application.input_commands import UpdateFirstSlice, apply_input_command
from inputs_v2.domain.beam_inputs import BeamInputs, LayoutMode
from inputs_v2.presentation.components.diagram_panel import build_section_figure, build_side_figure
from inputs_v2.presentation.view_models.input_diagram import build_input_diagram_view_model


def test_diagram_uses_exact_canonical_revision() -> None:
    original = BeamInputs()
    changed = apply_input_command(
        original,
        UpdateFirstSlice(400, 600, LayoutMode.COUNT, 7, 150, 20, 40),
    )
    view = build_input_diagram_view_model(changed)
    assert view.source_revision == changed.revision
    assert view.source_hash == changed.content_hash
    assert view.resolved_bar_count == 7
    assert len(view.bars) == 7


def test_spacing_mode_resolves_bars_without_alias_state() -> None:
    inputs = apply_input_command(
        BeamInputs(),
        UpdateFirstSlice(400, 600, LayoutMode.SPACING, 5, 100, 20, 40),
    )
    view = build_input_diagram_view_model(inputs)
    assert view.resolved_bar_count == 4


def test_figure_metadata_identifies_revision_and_bar_count() -> None:
    inputs = BeamInputs()
    view = build_input_diagram_view_model(inputs)
    figure = build_section_figure(view)
    assert figure.layout.meta["source_revision"] == inputs.revision
    assert figure.layout.meta["source_hash"] == inputs.content_hash
    assert figure.layout.meta["resolved_bar_count"] == 3


def test_top_and_shear_families_share_the_canonical_revision() -> None:
    inputs = apply_input_command(
        BeamInputs(),
        UpdateFirstSlice(400, 600, LayoutMode.COUNT, 7, 150, 20, 40, LayoutMode.COUNT, 4, 150, 16, 40, 12, 4, 150),
    )
    view = build_input_diagram_view_model(inputs)
    assert view.source_revision == inputs.revision
    assert len(view.bars) == 7
    assert len(view.top_bars) == 4
    assert len(view.shear_links) >= 1


def test_side_figure_uses_same_revision_and_link_projection() -> None:
    inputs = apply_input_command(
        BeamInputs(),
        UpdateFirstSlice(400, 600, LayoutMode.COUNT, 7, 150, 20, 40,
                         shear_diameter_mm=12, shear_legs=4, shear_spacing_mm=150),
    )
    view = build_input_diagram_view_model(inputs)
    figure = build_side_figure(view)
    assert figure.layout.meta["source_revision"] == inputs.revision
    assert figure.layout.meta["source_hash"] == inputs.content_hash
    assert figure.layout.meta["shear_link_count"] == len(view.shear_links)
