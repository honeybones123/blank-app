"""Canonical presentation tokens shared by every application page.

Values in this module are a locked rendering contract. Refactors may change
where these tokens are consumed, but changing a value is a separate visual
design decision and must be reviewed as such.
"""

from __future__ import annotations


SHARED_LAYOUT_TOKENS: dict[str, str] = {
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


def shared_layout_token_css() -> str:
    declarations = "\n".join(
        f"  --sb-{name}: {value};"
        for name, value in SHARED_LAYOUT_TOKENS.items()
    )
    return f":root {{\n{declarations}\n}}"


__all__ = ["SHARED_LAYOUT_TOKENS", "shared_layout_token_css"]
