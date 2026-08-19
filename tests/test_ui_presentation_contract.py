from __future__ import annotations

from pathlib import Path

from ui.design_tokens import SHARED_LAYOUT_TOKENS, shared_layout_token_css


ROOT = Path(__file__).resolve().parents[1]


def test_ui_ownership_contract_names_the_single_rendering_owners() -> None:
    contract = (ROOT / "UI_PRESENTATION_CONTRACT.md").read_text(encoding="utf-8")

    assert "Application title and navigation" in contract
    assert "Calculation-card shell and state colour" in contract
    assert "Engineering values" in contract
    assert "Generated Streamlit class names are not stable selectors" in contract
    assert "cold-page benchmark" in contract


def test_shared_layout_tokens_preserve_the_locked_values() -> None:
    assert SHARED_LAYOUT_TOKENS == {
        "page-content-width": "calc(100% - 2rem)",
        "heading-size": "1.45rem",
        "body-size": "0.92rem",
        "section-gap": "2rem",
        "card-gap": "1.25rem",
        "card-radius": "8px",
        "card-padding-y": "0.72rem",
        "card-padding-x": "1rem",
        "collapsed-card-height": "40px",
        "heading-color": "#0f172a",
    }
    css = shared_layout_token_css()
    for name, value in SHARED_LAYOUT_TOKENS.items():
        assert f"--sb-{name}: {value};" in css


def test_geometry_audit_covers_every_page_and_required_viewport() -> None:
    source = (
        ROOT / "tools" / "verification" / "helpers" / "ui_geometry_audit.py"
    ).read_text(encoding="utf-8")

    for slug in ("start", "inputs", "design", "bending", "shear", "creep", "shrinkage", "crack", "deflection"):
        assert f'"{slug}"' in source
    assert '"desktop": {"width": 1440, "height": 1000}' in source
    assert '"narrow": {"width": 768, "height": 1000}' in source
    assert "full_page=True" in source
    assert "summaryRect" in source
