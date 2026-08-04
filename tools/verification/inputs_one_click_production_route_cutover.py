"""Lock the production Inputs one-click route to the permanent application runtime."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "inputs_page.py"
ENTRYPOINT = ROOT / "inputs_application/one_click_entrypoint.py"


def main() -> None:
    page_source = PAGE.read_text(encoding="utf-8")
    entrypoint_source = ENTRYPOINT.read_text(encoding="utf-8")
    tree = ast.parse(page_source)
    imports = {
        (node.module, alias.name, alias.asname)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert (
        "inputs_application.page_runtime",
        "build_inputs_page_runtime",
        None,
    ) in imports
    assert "inputs_page_route_coordinators" not in page_source
    assert "inputs_page_app_contract_bridge" not in page_source
    assert "inputs_page_app_contract_bridge" not in entrypoint_source
    assert "build_one_click_runtime_provider" in entrypoint_source
    print(
        "PASS: production Inputs page and one-click routes use only permanent "
        "typed application runtimes"
    )


if __name__ == "__main__":
    main()
