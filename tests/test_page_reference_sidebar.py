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
    assert len(model.items) == len(BEAM_PROJECT_PARAM_KEYS)
    assert _item(model, "b").value == 300.0
    assert _item(model, "fc").value == 40.0
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
