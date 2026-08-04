"""Verify permanent Design overview production assembly."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    adapter = (
        ROOT / "inputs_page_modules" / "design_overview_adapter.py"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "inputs_page_app_contract_bridge.py").read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in adapter
    assert "inputs_page_route_coordinators" not in adapter
    assert "runtime=DesignOverviewRuntime(" in adapter
    assert "return collect_design_overview_owned(" in bridge
    print("PASS: Design overview production adapter has no legacy dependency")


if __name__ == "__main__":
    main()
