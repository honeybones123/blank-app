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


def test_retired_beam_snapshot_mirror_has_no_runtime_consumer() -> None:
    """Old sessions migrate once; no page/router may revive the old store."""

    retired_key = "_inputs_committed_engineering_state_by_beam_v1"
    allowed_migration_owner = ROOT / "inputs_application" / "engineering_input_store.py"
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("tests/", "tools/", "packages/", ".venv/")):
            continue
        if path == allowed_migration_owner:
            continue
        if retired_key in path.read_text(encoding="utf-8-sig"):
            offenders.append(relative)
    assert offenders == []


def test_global_input_snapshot_view_has_no_engineering_authority() -> None:
    """Only the no-beam migration branch may read the compatibility view."""

    permitted = {
        "inputs_application/engineering_input_store.py",
        "inputs_application/page_runtime/setup.py",
    }
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(("tests/", "tools/", "packages/", ".venv/")):
            continue
        source = path.read_text(encoding="utf-8-sig")
        uses_global_view = (
            "input_store.current()" in source
            or "input_snapshots.current()" in source
        )
        if uses_global_view and relative not in permitted:
            offenders.append(relative)
    assert offenders == []
