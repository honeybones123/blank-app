from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "inputs_v2"
RUNTIME_ROOT = Path(r"C:\Users\jonathon\OneDrive\Documents\GitHub\complete-app - Runtime")


def python_files():
    return tuple(SRC.rglob("*.py"))


def imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_domain_and_application_do_not_import_streamlit_or_presentation() -> None:
    protected = tuple((SRC / "domain").rglob("*.py")) + tuple((SRC / "application").rglob("*.py"))
    for path in protected:
        imports = imports_in(path)
        assert not any(name == "streamlit" or name.startswith("streamlit.") for name in imports), path
        if "domain" in path.parts:
            assert not any(name.startswith("inputs_v2.presentation") for name in imports), path


def test_no_runtime_import_or_path_reference() -> None:
    forbidden = ("state_and_helpers", "inputs_page_modules", "inputs_application", "complete-app - Runtime")
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        if path.name == "test_architecture.py":
            continue
        assert not any(token in text for token in forbidden), path


def test_only_application_command_creates_next_revision() -> None:
    writers = []
    for path in python_files():
        if "next_revision(" in path.read_text(encoding="utf-8"):
            writers.append(path.relative_to(SRC).as_posix())
    assert len(writers) == 2
    assert set(writers) == {"application/input_commands.py", "domain/beam_inputs.py"}


def test_css_selectors_are_scoped_or_approved_foundations() -> None:
    css = (SRC / "presentation" / "foundations.py").read_text(encoding="utf-8")
    css = css.split("<style>", 1)[1].split("</style>", 1)[0]
    selectors = re.findall(r"(?m)^\s*(\.[A-Za-z0-9_-]+(?:\s+\.[A-Za-z0-9_-]+)*)\s*\{", css)
    for selector in selectors:
        selector = selector.strip()
        assert selector == ".stApp" or selector.startswith(".inputs-v2-root"), selector


def test_lab_is_outside_existing_runtime() -> None:
    assert RUNTIME_ROOT not in ROOT.parents
    assert ROOT != RUNTIME_ROOT


def test_components_do_not_access_raw_session_state() -> None:
    for path in (SRC / "presentation" / "components").rglob("*.py"):
        assert "session_state" not in path.read_text(encoding="utf-8"), path


def test_presentation_does_not_contain_design_brain_decisions() -> None:
    app = (SRC / "app.py").read_text(encoding="utf-8")
    forbidden = (
        "classify_design_family",
        "current_target_band",
        "proposed_target_band",
        "safe_geometry_cleanup",
        "EngineeringAdviceResult(",
        "apply_allowed=",
        "terminal_outcome(",
    )
    assert not any(token in app for token in forbidden)


def test_family_sorter_has_only_one_application_consumer() -> None:
    consumers = []
    for path in (SRC / "application").rglob("*.py"):
        if path.name == "design_brain_families.py":
            continue
        if "classify_design_family(" in path.read_text(encoding="utf-8"):
            consumers.append(path.relative_to(SRC).as_posix())
    assert consumers == ["application/design_guide_orchestrator.py"]


def test_apply_permission_is_owned_by_decision_boundary() -> None:
    owners = []
    for path in python_files():
        if "apply_allowed=" in path.read_text(encoding="utf-8"):
            owners.append(path.relative_to(SRC).as_posix())
    assert owners == ["application/design_brain/family_owners.py"]


def test_orchestrator_does_not_select_concrete_ladder_methods() -> None:
    orchestrator = (SRC / "application" / "design_guide_orchestrator.py").read_text(encoding="utf-8")
    forbidden = (
        "preview_bending_overdesign(", "preview_shear_overdesign(",
        "preview_combined_overdesign(", "preview_combined_failure(",
        "preview_shear_only(", "preview_serviceability(",
        "preview_geometry_detailing(",
    )
    assert not any(token in orchestrator for token in forbidden)


def test_candidate_execution_uses_the_shared_evaluation_pipeline() -> None:
    service = (SRC / "application" / "design_brain_service.py").read_text(encoding="utf-8")
    # Direct application remains permitted only in the two final Apply
    # compatibility boundaries and the selected-preview publication boundary,
    # never inside candidate search loops.
    assert service.count("apply_candidate(current,") == 3
    assert "def _evaluate(" in service
    assert "evaluate_candidate(current, candidate, self._calculate_for_design_brain)" in service
    assert "Every Design Brain candidate must identify its owning ladder stage" in service
    assert 'self.last_search_metrics["stage_rejections"]' in service
    assert "def publish_preview(" in service
    assert "synthetic SLS actions never appear" in service


def test_family_pipelines_do_not_recalculate_proposed_inputs_outside_gateway() -> None:
    """Families may calculate their current baseline, but never a proposal."""
    pipeline_root = SRC / "application" / "design_brain"
    forbidden = (
        "self._calculate(updated_inputs)",
        "self._calculate(candidate.proposal)",
        "self._calculate(proposal)",
    )
    for path in pipeline_root.glob("*pipeline.py"):
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_family_contract_is_the_only_terminal_decision_centre() -> None:
    orchestrator = (SRC / "application" / "design_guide_orchestrator.py").read_text(encoding="utf-8")
    owners = (SRC / "application" / "design_brain" / "family_owners.py").read_text(encoding="utf-8")

    assert "return owner.decide(current, result, self._service)" in orchestrator
    assert "apply_allowed=" not in orchestrator
    assert "DecisionStatus(" not in orchestrator
    assert "TargetBandBlocker(" not in orchestrator
    assert ".improvement_policy.accepts(" not in orchestrator
    assert ".resolve_outcome(" not in orchestrator
    assert ".proves_exact_stop(" not in orchestrator
    assert "def decide(" in owners
    assert "self.improvement_policy.accepts(" in owners
    assert "self.proves_exact_stop(" in owners
    assert "self.resolve_outcome(" in owners


def test_every_pipeline_candidate_declares_an_owned_stage() -> None:
    pipeline_root = SRC / "application" / "design_brain"
    for path in pipeline_root.glob("*pipeline.py"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"self\._evaluate\((.*?)\)", source, re.DOTALL):
            assert "stage_id=" in match.group(0), path


def test_no_broad_terminal_shortcut_exists() -> None:
    """A passing calculation alone cannot prove target-band or exact-stop."""
    classifier = (SRC / "application" / "design_brain_families.py").read_text(encoding="utf-8")
    assert "def terminal_outcome(" not in classifier
    assert "EXACT_STOP_PROVEN" not in classifier.split("class DesignFamily", 1)[0]


def test_family_dispatch_is_typed_and_not_reflection_based() -> None:
    owners = (SRC / "application" / "design_brain" / "family_owners.py").read_text(encoding="utf-8")
    assert "getattr(service" not in owners
    assert "ladder_method" not in owners
    assert "ladder: FamilyLadder" in owners


def test_clause_numbers_are_owned_only_by_engineering_metadata() -> None:
    clause_pattern = re.compile(r'["\'](?:2|4|8)\.\d+(?:\.\d+)*["\']')
    for root in (SRC / "application", SRC / "presentation"):
        for path in root.rglob("*.py"):
            assert not clause_pattern.search(path.read_text(encoding="utf-8")), path
    app = (SRC / "app.py").read_text(encoding="utf-8")
    assert not clause_pattern.search(app)


def test_visible_design_brain_copy_does_not_publish_internal_family_codes() -> None:
    app = (SRC / "app.py").read_text(encoding="utf-8")
    assert "decision.display_heading" not in app  # presentation consumes the typed card model
    assert "decision.reason" not in app
    assert "decision.family.value" in app  # permitted only as an aria-hidden CSS state marker
    assert 'aria-hidden="true"' in app


def test_app_has_no_engineering_no_load_decision_branch() -> None:
    app = (SRC / "app.py").read_text(encoding="utf-8")
    assert "NO_DESIGN_ACTIONS" not in app
    assert "actions.bending_moment_knm" not in app.split("def _render_design_brain", 1)[1].split("def _render_detailed_controls", 1)[0]
    assert "DesignGuideOrchestrator" in app


def test_every_active_design_brain_family_owns_a_complete_contract() -> None:
    from inputs_v2.application.design_brain.family_owners import FAMILY_CONTRACTS, FAMILY_OWNERS, TERMINAL_FAMILIES
    from inputs_v2.application.design_brain_families import DesignFamily
    from inputs_v2.application.design_brain.text_contracts import FAMILY_TEXT_CONTRACTS

    assert set(FAMILY_OWNERS) == set(DesignFamily) - TERMINAL_FAMILIES
    assert set(FAMILY_CONTRACTS) == set(DesignFamily)
    assert set(FAMILY_TEXT_CONTRACTS) == set(DesignFamily)
    assert len({owner.contract.owner_id for owner in FAMILY_OWNERS.values()}) == len(FAMILY_OWNERS)
    assert len({owner.ladder for owner in FAMILY_OWNERS.values()}) == len(FAMILY_OWNERS)
    for family, owner in FAMILY_OWNERS.items():
        contract = owner.contract
        assert contract.family is family
        assert contract.entry_condition_id
        assert callable(contract.entry_condition)
        assert contract.ladder_stages
        assert all(stage.stage_id and stage.permitted_changes for stage in contract.ladder_stages)
        assert contract.permitted_changes
        assert contract.prohibited_changes
        assert not set(contract.permitted_changes) & set(contract.prohibited_changes)
        assert contract.required_checks
        assert contract.improvement_policy.active_domains
        assert contract.ranking_policy.criteria
        assert contract.exact_stop_policy.required_stage_ids == tuple(
            stage.stage_id for stage in contract.ladder_stages
        )
        assert contract.blocker_contract_id
        assert contract.blocker_wording
        assert contract.action_intent
        assert contract.pass_intent
        assert contract.blocked_intent
    for family in TERMINAL_FAMILIES:
        contract = FAMILY_CONTRACTS[family]
        assert contract.entry_condition_id
        assert callable(contract.entry_condition)
        assert contract.ladder_stages
        assert contract.required_checks
        assert contract.action_intent
        assert contract.pass_intent
        assert contract.blocked_intent


def test_family_contract_binding_cannot_leak_between_ladder_runs() -> None:
    from inputs_v2.application.design_brain.family_owners import FAMILY_OWNERS
    from inputs_v2.application.design_brain_families import DesignFamily
    from inputs_v2.application.design_brain_service import DesignBrainService
    from inputs_v2.domain.beam_inputs import BeamInputs

    service = DesignBrainService()
    owner = FAMILY_OWNERS[DesignFamily.BENDING_OVERDESIGN_GOVERNS]

    owner.preview(BeamInputs().validated(), service)

    assert service._active_family_contract is None


def test_family_change_boundary_rejects_undeclared_or_unknown_fields() -> None:
    import pytest
    from dataclasses import replace
    from inputs_v2.application.design_brain.family_owners import (
        FAMILY_OWNERS,
        assert_candidate_proposal_permitted,
        assert_permitted_changes,
    )
    from inputs_v2.application.design_brain_families import DesignFamily
    from inputs_v2.application.design_brain_apply import propose_neutral_candidate
    from inputs_v2.domain.beam_inputs import BeamInputs

    contract = FAMILY_OWNERS[DesignFamily.BENDING_OVERDESIGN_GOVERNS].contract
    assert_permitted_changes(contract, ("bottom_bars", "bottom_diameter_mm", "width_mm"))
    with pytest.raises(ValueError, match="undeclared changes"):
        assert_permitted_changes(contract, ("supports",))
    current = BeamInputs().validated()
    proposal = propose_neutral_candidate(current).proposal
    hidden_action_change = replace(proposal, shear_force_kn=10.0)
    with pytest.raises(ValueError, match="crosses owned boundaries: actions"):
        assert_candidate_proposal_permitted(contract, current, hidden_action_change)


def test_search_budget_intent_is_explicitly_owned_by_each_family_contract() -> None:
    from inputs_v2.application.design_brain.family_owners import (
        FAMILY_CONTRACTS,
        TERMINAL_FAMILIES,
    )
    from inputs_v2.application.design_brain.search_profile import SearchKind
    from inputs_v2.application.design_brain_families import DesignFamily

    repair = {
        DesignFamily.GEOMETRY_DETAILING_GOVERNS,
        DesignFamily.SERVICEABILITY_GOVERNS,
        DesignFamily.BENDING_AND_SHEAR_FAIL_GOVERN,
        DesignFamily.SHEAR_FAIL_GOVERNS,
        DesignFamily.SHEAR_FAIL_BENDING_OPTIMISE_GOVERNS,
        DesignFamily.BENDING_FAIL_GOVERNS,
        DesignFamily.BENDING_FAIL_SHEAR_OVERDESIGN_GOVERNS,
    }
    optimise = {
        DesignFamily.COMBINED_OVERDESIGN,
        DesignFamily.BENDING_OVERDESIGN_GOVERNS,
        DesignFamily.SHEAR_OVERDESIGN_GOVERNS,
    }

    assert {family for family, contract in FAMILY_CONTRACTS.items() if contract.search_kind is SearchKind.REPAIR} == repair
    assert {family for family, contract in FAMILY_CONTRACTS.items() if contract.search_kind is SearchKind.OPTIMISATION} == optimise
    assert {family for family, contract in FAMILY_CONTRACTS.items() if contract.search_kind is SearchKind.TERMINAL} == TERMINAL_FAMILIES

    service = (SRC / "application" / "design_brain_service.py").read_text(encoding="utf-8")
    assert '"OVERDESIGN" in' not in service
    assert ".search_kind" in service


def test_only_repair_contracts_may_accept_a_compliant_result_below_target_band() -> None:
    from inputs_v2.application.design_brain.family_owners import FAMILY_CONTRACTS
    from inputs_v2.application.design_brain.search_profile import SearchKind

    for contract in FAMILY_CONTRACTS.values():
        assert contract.improvement_policy.allow_compliant_repair is (
            contract.search_kind is SearchKind.REPAIR
        )


def test_optimisation_exact_stop_is_owned_by_the_family_contract() -> None:
    from inputs_v2.application.design_brain.family_owners import FAMILY_CONTRACTS
    from inputs_v2.application.design_brain.search_profile import SearchKind

    for contract in FAMILY_CONTRACTS.values():
        if contract.search_kind is SearchKind.OPTIMISATION:
            assert contract.retain_compliant_on_optimisation_exhaustion
            assert contract.exact_stop_policy.reason_codes
        else:
            assert not contract.retain_compliant_on_optimisation_exhaustion


def test_shear_failure_ladder_does_not_reclassify_the_selected_family() -> None:
    pipeline = (
        SRC / "application" / "design_brain" / "shear_failure_pipeline.py"
    ).read_text(encoding="utf-8")

    assert 'return DesignBrainPreview(seed, before, before, (), False, "shear_not_failed")' not in pipeline
    assert "Entry into this family is owned by the family classifier" in pipeline


def test_search_evidence_stage_sets_cannot_escape_the_selected_family_contract() -> None:
    from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
    from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs

    decision = DesignGuideOrchestrator().decide(
        BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0)).validated()
    )
    evidence = decision.search_evidence

    assert set(evidence.attempted_stage_ids) <= set(evidence.declared_stage_ids)
    assert set(evidence.completed_stage_ids) <= set(evidence.attempted_stage_ids)
    attempt_counts = dict(evidence.stage_attempt_counts)
    valid_counts = dict(evidence.stage_valid_counts)
    assert set(attempt_counts) == set(evidence.attempted_stage_ids)
    assert set(valid_counts) <= set(attempt_counts)
    assert all(valid_counts.get(stage_id, 0) <= count for stage_id, count in attempt_counts.items())
    assert sum(attempt_counts.values()) == evidence.candidates_attempted
    assert sum(valid_counts.values()) == evidence.candidates_valid
    assert len(evidence.candidate_records) == evidence.candidates_attempted
    assert all(record.stage_id in evidence.attempted_stage_ids for record in evidence.candidate_records)
    assert all(record.candidate_id for record in evidence.candidate_records)
    assert all(record.elapsed_ms >= 0.0 for record in evidence.candidate_records)
    assert tuple(stage.stage_id for stage in evidence.stages) == evidence.declared_stage_ids
    assert all(
        stage.completed is (stage.stage_id in evidence.completed_stage_ids)
        for stage in evidence.stages
    )
    assert all(stage.stop_reason for stage in evidence.stages if stage.completed)


def test_candidate_audit_records_preserve_every_gateway_rejection() -> None:
    from inputs_v2.application.design_guide_orchestrator import DesignGuideOrchestrator
    from inputs_v2.domain.beam_inputs import ActionInputs, BeamInputs

    decision = DesignGuideOrchestrator().decide(
        BeamInputs(actions=ActionInputs(bending_moment_knm=1000.0)).validated()
    )
    evidence = decision.search_evidence
    recorded_rejections: dict[str, int] = {}
    for record in evidence.candidate_records:
        assert record.row_counts
        assert record.calculated_checks or record.rejection_codes in {
            ("candidate_validation_failed",),
            ("reinforcement_fit_failed",),
        }
        for code in record.rejection_codes:
            recorded_rejections[code] = recorded_rejections.get(code, 0) + 1

    assert recorded_rejections == dict(evidence.rejection_counts)
