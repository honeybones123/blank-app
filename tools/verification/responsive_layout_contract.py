"""Static safeguards for the responsive containers certified in a browser."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from ui.summary_sections import summary_card_css
from widgets_helpers import apply_global_widget_css


def main() -> None:
    summary_css = summary_card_css()
    widget_css = inspect.getsource(apply_global_widget_css)

    assert ".summary-detail-shell" in summary_css
    assert "box-sizing: border-box" in summary_css
    assert "max-width: 100%" in summary_css
    assert ".summary-detail-inner" in summary_css
    assert "min-width: 0" in summary_css

    assert "@media (max-width: 1200px)" in summary_css
    assert "@media (max-width: 1200px)" in widget_css
    assert ".sb-tooltip-bubble" in widget_css
    assert "left: auto" in widget_css
    assert "right: 0" in widget_css

    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app_tree = ast.parse(app_path.read_text(encoding="utf-8"))
    module_calls = [
        node
        for node in app_tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_apply_sharp_embed_css"
    ]
    main_fn = next(
        node
        for node in app_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    main_calls = [
        node
        for node in ast.walk(main_fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_apply_sharp_embed_css"
    ]
    assert module_calls == [], "responsive CSS must not be emitted only at import"
    assert len(main_calls) == 1, "responsive CSS must be emitted once per app run"

    print("responsive layout contract: PASS")


if __name__ == "__main__":
    main()
