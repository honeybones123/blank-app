"""Contracts for the shared read-only page reference sidebar."""

from __future__ import annotations

import ast
from pathlib import Path
import sys

import pytest

from engineering_page_sections.page_reference_sidebar import (
    PAGE_REFERENCE_BUILDERS,
    PageReferenceItem,
    PageReferenceModel,
    _display_scalar,
    build_beam_inputs_reference,
    build_page_reference_model,
    render_page_reference_sidebar,
)


ROOT = Path(__file__).resolve().parents[1]


def _active_page_slugs() -> set[str]:
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "PAGES"
            for target in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            raise AssertionError("The active PAGES registry must remain a dict")
        return {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    raise AssertionError("The active PAGES registry was not found")


def _item(model: PageReferenceModel, key: str) -> PageReferenceItem:
    return next(item for item in model.items if item.key == key)


def test_every_active_page_has_one_reference_builder() -> None:
    assert set(PAGE_REFERENCE_BUILDERS) == _active_page_slugs()
    for slug in _active_page_slugs():
        model = build_page_reference_model(slug, {})
        assert model.page_key == slug


def test_reference_items_have_unique_complete_metadata() -> None:
    for slug, builder in PAGE_REFERENCE_BUILDERS.items():
        model = builder({})
        keys = [item.key for item in model.items]
        assert len(keys) == len(set(keys)), slug
        assert all(item.symbol.strip() for item in model.items), slug
        assert all(item.name.strip() for item in model.items), slug
        assert all(item.definition.strip() for item in model.items), slug
        assert all(item.category.strip() for item in model.items), slug


def test_beam_inputs_reference_tracks_the_canonical_parameter_contract() -> None:
    from state_and_helpers import BEAM_PROJECT_PARAM_KEYS

    model = build_beam_inputs_reference(
        {"b": 300.0, "fc": 40.0, "reference_source": "Beam Inputs"}
    )
    # The canonical contract remains fully represented.  The three additional
    # items are the existing load-view selector plus two compact, explicitly
    # derived bottom/top reo summaries.
    assert len(model.items) == len(BEAM_PROJECT_PARAM_KEYS) + 3
    assert _item(model, "b").value == 300.0
    assert _item(model, "fc").value == 40.0
    assert _item(model, "loads_edit_mode").input_label == "View SLS loads"
    assert _item(model, "bot_reinforcement_notation").value == "None"
    assert _item(model, "top_reinforcement_notation").value == "None"
    assert model.source_label == "Beam Inputs"


@pytest.mark.parametrize(
    ("slug", "values", "key", "expected"),
    [
        ("design", {"M_uls": 215.3}, "M_uls", 215.3),
        ("bending", {"M_star": 215.3}, "M_star", 215.3),
        ("shear", {"V_eq": 96.0}, "V_eq", 96.0),
        ("creep", {"t_creep": 365.0}, "t_creep", 365.0),
        ("shrinkage", {"t_shrink": 365.0}, "t_shrink", 365.0),
        ("crack", {"wmax_char_limit": 0.3}, "wmax_char_limit", 0.3),
        ("deflection", {"defl_limit_ratio": 250.0}, "defl_limit_ratio", 250.0),
    ],
)
def test_page_values_are_projected_without_recalculation(
    slug: str, values: dict[str, object], key: str, expected: object
) -> None:
    model = build_page_reference_model(slug, values)
    assert _item(model, key).value == expected


def test_branch_reference_models_are_isolated_and_do_not_mutate_inputs() -> None:
    beam_values = {"b": 300.0, "reference_source": "Beam Inputs"}
    load_values = {"L_m": 4.5, "reference_source": "Load Analysis"}

    beam_model = build_beam_inputs_reference(beam_values)
    load_model = build_page_reference_model("design", load_values)

    assert _item(beam_model, "b").value == 300.0
    assert _item(load_model, "L_m").value == 4.5
    assert beam_values == {"b": 300.0, "reference_source": "Beam Inputs"}
    assert load_values == {"L_m": 4.5, "reference_source": "Load Analysis"}
    assert beam_model.source_label == "Beam Inputs"
    assert load_model.source_label == "Load Analysis"


def test_reference_model_is_immutable() -> None:
    model = build_page_reference_model("bending", {"b": 300.0})
    with pytest.raises((AttributeError, TypeError)):
        model.page_key = "shear"  # type: ignore[misc]


def test_repeating_input_metadata_is_engineering_friendly() -> None:
    model = build_beam_inputs_reference(
        {
            "bot_row_1_bars": 3,
            "design_ms_G_1": 30.0,
            "design_span_len_1": 4.0,
        }
    )
    rows = {item.key: item for item in model.items}
    assert rows["bot_row_1_bars"].symbol == "n_{bot,1}"
    assert rows["bot_row_1_bars"].units == "bars"
    assert rows["bot_row_1_bars"].definition.startswith("Number of bars")
    assert rows["design_ms_G_1"].symbol == "G_{1}"
    assert rows["design_ms_G_1"].units == "kN"
    assert rows["design_span_len_1"].units == "m"


def test_active_reo_projection_uses_exact_page_controls_and_live_notation() -> None:
    model = build_page_reference_model(
        "bending",
        {
            "bot_row_count": 2,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 10,
            "bot_row_2_mode": "Spacing",
            "bot_row_2_spacing": 200,
            "bot_row_2_dia": 16,
            "top_row_count": 1,
            "top_row_1_mode": "Count",
            "top_row_1_bars": 2,
            "top_row_1_dia": 12,
        },
    )
    items = {item.key: item for item in model.items if item.visible}
    assert items["bot_row_count"].input_label == "Rows"
    assert items["bot_row_1_mode"].input_label == "Layout"
    assert items["bot_row_1_bars"].input_label == "Bars"
    assert items["bot_row_2_spacing"].input_label == "Spacing"
    assert items["bot_row_1_dia"].input_label == "Ø (mm)"
    assert "bot_row_1_spacing" not in items
    assert items["bot_reinforcement_notation"].value == "3-N10 + N16 @ 200"
    assert items["top_reinforcement_notation"].value == "2-N12"


def test_zero_reinforcement_rows_do_not_reappear_from_stale_aliases() -> None:
    model = build_page_reference_model(
        "bending",
        {
            "bot_row_count": 0,
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 20,
            "top_row_count": 0,
            "top_row_1_bars": 2,
            "top_row_1_dia": 16,
        },
    )
    visible = {item.key: item for item in model.items if item.visible}
    assert "bot_row_1_bars" not in visible
    assert "top_row_1_bars" not in visible
    assert visible["bot_reinforcement_notation"].value == "None"
    assert visible["top_reinforcement_notation"].value == "None"


def test_page_specific_action_labels_override_shared_family_metadata() -> None:
    inputs = build_page_reference_model(
        "inputs",
        {
            "manual_uls_Vstar": 96.0,
            "manual_uls_Nstar": 4.0,
            "inputs_detailed_mode": True,
            "t_creep": 365.0,
            "crack_k1": 0.8,
        },
    )
    assert _item(inputs, "manual_uls_Vstar").input_label == "Design shear Vu* (kN)"
    assert _item(inputs, "manual_uls_Nstar").input_label == "Axial force N* (kN)"
    assert _item(inputs, "t_creep").input_label == "Creep time t (days)"
    assert _item(inputs, "crack_k1").input_label == "k1"

    shear = build_page_reference_model(
        "shear",
        {
            "loads_edit_mode": "SLS",
            "sls_Mstar": 80.0,
            "sls_Vstar": 60.0,
            "sls_Nstar": 3.0,
        },
    )
    shear_items = {item.key: item for item in shear.items if item.visible}
    assert shear_items["sls_Mstar_pos_manual"].input_label == "Positive design moment Mu*+ (kNm)"
    assert shear_items["manual_sls_Vstar"].value == 60.0
    assert "manual_uls_Vstar" not in shear_items
    assert "uls_Mstar_pos_manual" not in shear_items

    load_analysis = build_page_reference_model(
        "design",
        {"actions_source": "Manual design actions (inputs below)"},
    )
    assert _item(load_analysis, "actions_source").input_label == (
        "Use Load Analysis actions for Beam Inputs"
    )


def test_conditional_page_inputs_follow_the_active_method_or_load_case() -> None:
    simplified_udl = build_page_reference_model(
        "deflection",
        {
            "load_case": "UDL",
            "beam_system_mode": "Single span",
            "defl_use_simplified_ief": True,
            "defl_Ief_user": 123.0,
            "g_udl_kNm_per_m": 4.0,
            "q_udl_kNm_per_m": 6.0,
        },
    )
    simplified_keys = {item.key for item in simplified_udl.items if item.visible}
    assert "defl_Ief_user" not in simplified_keys
    assert {"g_udl_kNm_per_m", "q_udl_kNm_per_m"} <= simplified_keys

    user_ief_point = build_page_reference_model(
        "deflection",
        {
            "load_case": "Single point load",
            "beam_system_mode": "Single span",
            "defl_use_simplified_ief": False,
            "defl_Ief_user": 123.0,
            "P_sls_kN": 42.0,
            "a_m": 1.5,
        },
    )
    point_keys = {item.key for item in user_ief_point.items if item.visible}
    assert "defl_Ief_user" in point_keys
    assert {"P_sls_kN", "a_m"} <= point_keys
    assert "g_udl_kNm_per_m" not in point_keys

    deflection = build_page_reference_model(
        "deflection",
        {"beam_system_mode": "Single span", "load_case": "UDL"},
    )
    assert _item(deflection, "beam_system_mode").input_label == "Beam system mode"


def test_shear_action_and_duct_controls_project_current_values() -> None:
    model = build_page_reference_model(
        "shear",
        {
            "loads_edit_mode": "ULS",
            "uls_Mstar": 120.0,
            "uls_Vstar": 96.0,
            "uls_Nstar": 4.0,
            "uls_Mstar_pos_manual": 115.0,
            "shear_include_prestress_effects_ui": True,
            "P_star": 50.0,
            "n_ducts": 2,
            "duct_dia": 80.0,
            "k_d_option": "0.5 — steel ducts, grouted",
        },
    )
    items = {item.key: item for item in model.items if item.visible}
    assert items["manual_uls_Vstar"].value == 96.0
    assert items["manual_uls_Nstar"].value == 4.0
    assert items["P_star"].input_label == "Prestress force P* (kN)"
    assert items["n_ducts"].value == 2
    assert items["n_ducts"].units == "ducts"
    assert items["k_d_option"].input_label == "k_d factor for prestressing ducts"
    assert _display_scalar(2, "ducts") == "2 ducts"


def test_renderer_mounts_exactly_the_two_read_only_folders(monkeypatch) -> None:
    class _Expander:
        def __init__(self, labels: list[str], label: str) -> None:
            self._labels = labels
            self._label = label

        def __enter__(self):
            self._labels.append(self._label)
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> bool:
            return False

    class _Sidebar:
        def __init__(self) -> None:
            self.labels: list[str] = []

        def expander(self, label: str, *, expanded: bool):
            assert expanded is False
            return _Expander(self.labels, label)

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.sidebar = _Sidebar()

        @staticmethod
        def markdown(*args, **kwargs) -> None:
            del args, kwargs

        @staticmethod
        def caption(*args, **kwargs) -> None:
            del args, kwargs

    fake_streamlit = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    render_page_reference_sidebar(build_page_reference_model("start", {}))

    assert fake_streamlit.sidebar.labels == [
        "Glossary of terms",
        "Current page values",
    ]


def test_renderer_uses_exact_page_labels_and_keeps_derived_reo_out_of_glossary(
    monkeypatch,
) -> None:
    class _Expander:
        def __init__(self, sidebar, label: str) -> None:
            self._sidebar = sidebar
            self._label = label

        def __enter__(self):
            self._sidebar.active_label = self._label
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> bool:
            self._sidebar.active_label = None
            return False

    class _Sidebar:
        def __init__(self) -> None:
            self.active_label: str | None = None

        def expander(self, label: str, *, expanded: bool):
            del expanded
            return _Expander(self, label)

    class _FakeStreamlit:
        def __init__(self) -> None:
            self.sidebar = _Sidebar()
            self.markdown_values: dict[str, list[str]] = {}

        def markdown(self, value: str, **kwargs) -> None:
            del kwargs
            label = self.sidebar.active_label
            assert label is not None
            self.markdown_values.setdefault(label, []).append(value)

        @staticmethod
        def caption(*args, **kwargs) -> None:
            del args, kwargs

    fake_streamlit = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)

    model = build_page_reference_model(
        "inputs",
        {
            "sec_shape": "RECT",
            "bot_row_count": 1,
            "bot_row_1_mode": "Count",
            "bot_row_1_bars": 3,
            "bot_row_1_dia": 10,
            "top_row_count": 1,
            "top_row_1_mode": "Count",
            "top_row_1_bars": 2,
            "top_row_1_dia": 12,
        },
    )
    render_page_reference_sidebar(model)

    # The renderer keeps each category readable by emitting one markdown
    # block per category, while the fake sidebar keeps the two folders
    # separate for precise presentation assertions.
    glossary = "\n".join(fake_streamlit.markdown_values["Glossary of terms"])
    current_values = "\n".join(fake_streamlit.markdown_values["Current page values"])
    assert "**Bottom Reinforcement — Layer 1 — Bars**" in glossary
    assert "Page input: `Bars`" in glossary
    assert "**Bottom Reinforcement — Layer 1 — Ø (mm)**" in glossary
    assert "Read-only reo summary" not in glossary
    assert "**Bottom reinforcement arrangement (derived)** = 3-N10" in current_values
    assert "**Bottom Reinforcement — Layer 1 — Bars** = 3 bars" in current_values


def test_current_value_formatting_preserves_small_dimensionless_values() -> None:
    assert _display_scalar(0.00142, None) == "0.00142"
    assert _display_scalar(300, "mm") == "300 mm"
    assert _display_scalar(False, None) == "Not included"
    assert _display_scalar(None, "MPa") == "—"


def test_reference_module_has_no_solver_or_session_state_dependency() -> None:
    source = (ROOT / "engineering_page_sections/page_reference_sidebar.py").read_text(
        encoding="utf-8"
    )
    assert "st.session_state" not in source
    assert "solve_" not in source
    assert "calculate_" not in source
    assert "recalc_" not in source
