from pathlib import Path

from inputs_v2.presentation.foundations import scoped_css


LAB_ROOT = Path(__file__).parents[1]


def test_runtime_visual_contract_is_present_and_explicit() -> None:
    contract = (LAB_ROOT / "RUNTIME_VISUAL_CONTRACT.md").read_text(encoding="utf-8")
    for required in ("1180px", "2.25rem", "14px", "Bottom Reinforcement", "sibling columns"):
        assert required in contract


def test_v2_shell_uses_runtime_shell_measurements() -> None:
    css = scoped_css()
    for required in ("font-size: 14px", "max-width: 1180px", "2.25rem", "padding-top: 2rem"):
        assert required in css
def test_design_brain_visual_shell_remains_frozen() -> None:
    """Architecture changes must not redesign the accepted V2 card shell."""
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src" / "inputs_v2"
    app = (src / "app.py").read_text(encoding="utf-8")
    css = (src / "presentation" / "foundations.py").read_text(encoding="utf-8")
    assert "st.expander(summary_label, expanded=False)" in app
    assert "🧠" in css
    assert "inputs-v2-brain-state-fail" in css
    assert "inputs-v2-brain-state-optimise" in css
    assert "inputs-v2-brain-state-pass" in css
    assert "background:#fff0f0" in css
    assert "background:#eef3ff" in css
    assert "background:#edf8ef" in css
    assert 'st.button("Apply recommendation"' in app
    assert "use_container_width=True" in app


def test_engineering_summary_header_owns_expand_and_collapse() -> None:
    """The visible card shell, not a hidden overlay, owns disclosure state."""
    src = Path(__file__).resolve().parents[1] / "src" / "inputs_v2"
    app = (src / "app.py").read_text(encoding="utf-8")
    css = (src / "presentation" / "foundations.py").read_text(encoding="utf-8")

    assert '<summary class="inputs-v2-check-main" aria-label="Expand checks">' in app
    assert '<div class="inputs-v2-check-table-wrap"><table>' in app
    assert "position:absolute; inset:0; z-index:3" not in css
    assert ".inputs-v2-check-details[open] .inputs-v2-check-chevron" in css
