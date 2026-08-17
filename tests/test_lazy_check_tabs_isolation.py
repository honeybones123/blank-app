from engineering_page_sections.lazy_check_tabs import render_lazy_check_tab_selector
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}
        self.markdown_calls: list[str] = []
        self.radio_calls: list[dict[str, object]] = []

    def markdown(self, body: str, **_kwargs: object) -> None:
        self.markdown_calls.append(body)

    def radio(self, _label: str, *, options, key: str, **_kwargs: object) -> str:
        self.radio_calls.append({"options": tuple(options), "key": key})
        return str(self.session_state.get(key) or tuple(options)[0])


def test_lazy_check_tabs_use_selector_scoped_scroll_storage() -> None:
    st = _FakeStreamlit()

    assert render_lazy_check_tab_selector(
        st,
        labels=("ULS", "SLS"),
        key="bending_check_tab",
        aria_label="Bending checks",
        anchor_id="bending-check-tabs-anchor",
    ) == "ULS"
    assert render_lazy_check_tab_selector(
        st,
        labels=("Torsion", "Reinforcement"),
        key="shear_check_tab",
        aria_label="Shear checks",
        anchor_id="shear-check-tabs-anchor",
    ) == "Torsion"

    bending_markup, shear_markup = st.markdown_calls
    assert 'sb_calc_tab_scroll_y::bending_check_tab' in bending_markup
    assert 'sb_calc_tab_scroll_y::shear_check_tab' in shear_markup
    assert 'const key = "sb_calc_tab_scroll_y"' not in bending_markup
    assert 'belongsToThisSelector(label)' in bending_markup
    assert 'win.__sbCalcTabScrollSelectors' in shear_markup


def test_shear_uses_the_shared_check_tab_boundary() -> None:
    """Shear must not retain an independent tab/scroll implementation."""

    source = (ROOT / "shear_page_runtime.py").read_text(encoding="utf-8-sig")
    start = source.index("# 3. SHEAR DESIGN CHECKS UI")
    end = source.index("# TAB 1: Torsion + dimensions", start)
    selector_source = source[start:end]

    assert "render_lazy_check_tab_selector(" in selector_source
    assert "anchor_id=\"shear-check-tabs-anchor\"" in selector_source
    assert 'st.radio(\n        "Shear design checks"' not in selector_source
    assert "st.session_state.get(JUMP_NAV_TAB_KEY)" not in selector_source
