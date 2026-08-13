from __future__ import annotations

from pathlib import Path

import pytest

from inputs_application.new_design_brain_adapter import (
    _require_compatible_v2_design_brain_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_accepts_current_installed_design_brain_contract() -> None:
    _require_compatible_v2_design_brain_contract(2)


@pytest.mark.parametrize("version", [None, 1, 3, "2"])
def test_runtime_rejects_stale_or_unknown_design_brain_contract(version: object) -> None:
    with pytest.raises(RuntimeError, match="Reinstall"):
        _require_compatible_v2_design_brain_contract(version)


def test_runtime_cannot_replace_or_reclassify_the_v2_family_decision() -> None:
    """V2 owns family selection through publication and Apply."""

    forbidden_modules = (
        ROOT / "application" / "whole_beam_family_restamp_policy.py",
        ROOT / "application" / "family_ladder_dispatch_policy.py",
        ROOT / "inputs_application" / "serviceability_preflight.py",
    )
    assert not any(path.exists() for path in forbidden_modules)

    adapter = (ROOT / "application" / "guidance_result_adapter.py").read_text(
        encoding="utf-8"
    )
    forbidden_authority = (
        "family_classifier",
        "strategy_lookup",
        "selected_family_id =",
        "family_override",
        "publication_builder",
        "build_authoritative_design_result",
        "restamp",
        "rank_key",
    )
    assert not any(token in adapter for token in forbidden_authority)
    assert "result.final_publication" in adapter


def test_runtime_has_one_design_brain_family_classifier_consumer() -> None:
    src = ROOT / "packages" / "beamapp-inputs-v2" / "src" / "inputs_v2"
    consumers: list[str] = []
    for path in (src / "application").rglob("*.py"):
        if path.name == "design_brain_families.py":
            continue
        if "classify_design_family_selection(" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(src).as_posix())
    assert consumers == ["application/design_guide_orchestrator.py"]
