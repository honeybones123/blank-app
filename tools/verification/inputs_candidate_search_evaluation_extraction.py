"""Freeze application ownership of search-candidate evaluation coordination."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    owner = (
        ROOT / "inputs_application" / "candidate_search_evaluation.py"
    ).read_text(encoding="utf-8")
    bridge = (ROOT / "inputs_page_app_contract_bridge.py").read_text(encoding="utf-8")
    assert "@dataclass(frozen=True)" in owner
    assert "inputs_page_app_contract_bridge" not in owner
    assert "streamlit" not in owner
    assert "globals()" not in owner
    assert "runtime=CandidateSearchEvaluationRuntime(" in bridge
    assert "return evaluate_search_candidate(" in bridge
    print("PASS: search-candidate evaluation is application-owned and typed")


if __name__ == "__main__":
    main()
