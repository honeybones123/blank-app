"""Verify bridge-independent full candidate production assembly."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    adapter = (
        ROOT / "inputs_page_modules" / "recommendation_candidate_adapter.py"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "inputs_page_app_contract_bridge.py").read_text(encoding="utf-8")
    assert "inputs_page_app_contract_bridge" not in adapter
    assert "FullCandidateEvaluationRuntime(" in adapter
    assert "collect_design_overview(" in adapter
    assert "return evaluate_full_candidate_owned(" in bridge
    print("PASS: full candidate production adapter has no legacy dependency")


if __name__ == "__main__":
    main()
