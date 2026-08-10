from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
import unittest

from application.contracts.design_actions import DesignActionsSnapshot
from application.contracts.design_brain import AuthoritativeDesignResult
from application.contracts.design_branch import DesignBranch
from application.design_result_store import EngineeringResultStore
from inputs_application.branch_apply_identity import (
    stamp_branch_apply_identity,
    validate_branch_apply_identity,
)
from inputs_application.branch_workspace import (
    ActionSelectionPolicy,
    ActionSource,
    resolve_branch_workspace,
)
from inputs_application.design_actions_store import DerivedDesignActionsStore
from inputs_application.design_branch_store import (
    BeamDesignBranchStore,
    StaleBranchRevisionError,
    branch_for_page,
)
from inputs_application.design_guide_fragment_store import PublicationStore
from inputs_application.load_analysis_store import (
    LoadAnalysisSnapshotStore,
    StaleLoadAnalysisRevisionError,
)
from inputs_application.engineering_input_store import InputSnapshotStore
from inputs_application.workspace_application_service import WorkspaceApplicationService


def _actions(mu: float, vu: float, *, mode: str = "manual") -> DesignActionsSnapshot:
    return DesignActionsSnapshot(
        mu=mu,
        mu_signed=mu,
        mu_pos=max(mu, 0.0),
        mu_neg=max(-mu, 0.0),
        has_sagging_case=mu >= 0.0,
        has_hogging_case=mu < 0.0,
        vu=vu,
        nu=0.0,
        sls_m=0.0,
        sls_m_signed=0.0,
        sls_m_pos=0.0,
        sls_m_neg=0.0,
        sls_v=0.0,
        sls_n=0.0,
        tu=0.0,
        pu=0.0,
        source=mode,
        actions_source=mode,
        actions_mode=mode,
        design_actions_source="max" if mode != "manual" else "manual",
        sls_line_load=0.0,
        sls_point_load=0.0,
    )


def _result(engineering_hash: str, candidate_id: str) -> AuthoritativeDesignResult:
    return AuthoritativeDesignResult(
        engineering_hash=engineering_hash,
        current_calculations={"actions_used": {"Mu": 100.0, "Vu": 20.0}},
        governing_family="TEST",
        selected_candidate={"candidate_id": candidate_id},
        final_publication={"candidate_id": candidate_id},
        apply_payload={"candidate_id": candidate_id},
    ).with_publication_authority_hash()


class DualDesignBranchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state: dict[str, object] = {
            "active_beam_id": "beam-1",
            "_active_page_slug": "inputs",
        }
        self.store = BeamDesignBranchStore(self.state)
        self.store.ensure_migrated(
            "beam-1",
            beam_inputs_seed={"b": 250, "D": 450, "actions_mode": "manual"},
            load_analysis_seed={"b": 350, "D": 600},
        )

    def test_snapshots_are_recursively_immutable_and_defensive(self) -> None:
        current = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        self.assertIsNotNone(current)
        self.assertIsInstance(current.payload, MappingProxyType)
        mutable = current.to_mutable_dict()
        mutable["b"] = 999
        self.assertEqual(current.payload["b"], 250)
        with self.assertRaises(TypeError):
            current.payload["b"] = 999

    def test_toggle_changes_only_selection_and_restores_both_designs(self) -> None:
        beam = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        analysis = self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS)
        selection = self.store.selection("beam-1")
        changed = self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        self.assertEqual(changed.revision, selection.revision + 1)
        self.assertEqual(
            self.store.get("beam-1", DesignBranch.BEAM_INPUTS), beam
        )
        self.assertEqual(
            self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS), analysis
        )
        self.assertEqual(branch_for_page("inputs", changed), DesignBranch.LOAD_ANALYSIS)
        self.assertEqual(branch_for_page("bending", changed), DesignBranch.LOAD_ANALYSIS)
        self.assertEqual(branch_for_page("design", changed), DesignBranch.LOAD_ANALYSIS)
        restored = self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.BEAM_INPUTS,
            expected_selection_revision=changed.revision,
        )
        self.assertEqual(restored.selected_branch, DesignBranch.BEAM_INPUTS)
        self.assertEqual(self.store.selected_snapshot("beam-1"), beam)

    def test_export_import_restores_both_branches_and_selection(self) -> None:
        selection = self.store.selection("beam-1")
        selected = self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        exported = self.store.export_for_beam("beam-1")
        restored_state: dict[str, object] = {}
        restored = BeamDesignBranchStore(restored_state)
        restored.import_for_beam("beam-1", exported)
        self.assertEqual(restored.selection("beam-1"), selected)
        for branch in DesignBranch:
            self.assertEqual(
                restored.get("beam-1", branch),
                self.store.get("beam-1", branch),
            )

    def test_stale_branch_and_load_analysis_edits_are_rejected(self) -> None:
        current = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        updated = self.store.replace(
            "beam-1",
            DesignBranch.BEAM_INPUTS,
            expected_branch_revision=current.revision,
            payload={**current.to_mutable_dict(), "b": 275},
            source="test",
        )
        with self.assertRaises(StaleBranchRevisionError):
            self.store.replace(
                "beam-1",
                DesignBranch.BEAM_INPUTS,
                expected_branch_revision=current.revision,
                payload={**updated.to_mutable_dict(), "D": 500},
                source="stale",
            )
        analysis_store = LoadAnalysisSnapshotStore(self.state)
        first = analysis_store.ensure_seeded("beam-1", {"spans": [4.0]})
        analysis_store.replace(
            "beam-1",
            expected_revision=first.revision,
            analysis={"spans": [5.0]},
        )
        with self.assertRaises(StaleLoadAnalysisRevisionError):
            analysis_store.replace(
                "beam-1",
                expected_revision=first.revision,
                analysis={"spans": [6.0]},
            )

    def test_workspace_identity_excludes_selection_and_tracks_dependencies(self) -> None:
        beam = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        manual = resolve_branch_workspace(
            beam,
            None,
            ActionSource.MANUAL,
            ActionSelectionPolicy.MANUAL,
        )
        self.assertIsNone(manual.identity.load_analysis_revision)
        selection = self.store.selection("beam-1")
        self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        manual_again = resolve_branch_workspace(
            beam,
            None,
            ActionSource.MANUAL,
            ActionSelectionPolicy.MANUAL,
        )
        self.assertEqual(manual.engineering_hash, manual_again.engineering_hash)
        analysis = LoadAnalysisSnapshotStore(self.state).ensure_seeded(
            "beam-1", {"spans": [4.0]}
        )
        load_branch = self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS)
        calculated = resolve_branch_workspace(
            load_branch,
            analysis,
            ActionSource.LOAD_ANALYSIS,
            ActionSelectionPolicy.MAXIMUM,
            derived_design_actions=_actions(120.0, 40.0, mode="design"),
        )
        self.assertEqual(calculated.identity.load_analysis_revision, analysis.revision)

    def test_load_analysis_branch_rejects_manual_input_actions(self) -> None:
        analysis = LoadAnalysisSnapshotStore(self.state).ensure_seeded(
            "beam-1", {"spans": [4.0]}
        )
        load_branch = self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS)

        with self.assertRaisesRegex(
            ValueError,
            "LOAD_ANALYSIS always derives actions from Load Analysis",
        ):
            resolve_branch_workspace(
                load_branch,
                analysis,
                ActionSource.MANUAL,
                ActionSelectionPolicy.MANUAL,
                derived_design_actions=_actions(999.0, 999.0, mode="manual"),
            )

    def test_derived_actions_are_not_projected_after_dependency_changes(self) -> None:
        analysis = LoadAnalysisSnapshotStore(self.state).ensure_seeded(
            "beam-1", {"spans": [4.0]}
        )
        branch = self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS)
        workspace = resolve_branch_workspace(
            branch,
            analysis,
            ActionSource.LOAD_ANALYSIS,
            ActionSelectionPolicy.MAXIMUM,
            derived_design_actions=_actions(120.0, 40.0, mode="design"),
        )
        action_store = DerivedDesignActionsStore(self.state)
        action_store.publish(workspace.identity, workspace.design_actions)
        self.assertIsNotNone(
            action_store.current_for_dependencies(
                "beam-1",
                DesignBranch.LOAD_ANALYSIS,
                branch_revision=branch.revision,
                branch_hash=branch.content_hash,
                load_analysis_revision=analysis.revision,
                load_analysis_hash=analysis.content_hash,
            )
        )
        self.assertIsNone(
            action_store.current_for_dependencies(
                "beam-1",
                DesignBranch.LOAD_ANALYSIS,
                branch_revision=branch.revision,
                branch_hash=branch.content_hash,
                load_analysis_revision=analysis.revision + 1,
                load_analysis_hash=analysis.content_hash,
            )
        )

    def test_two_publications_and_results_coexist(self) -> None:
        publications = PublicationStore(self.state)
        for index, branch in enumerate(DesignBranch, start=1):
            result = _result(f"hash-{branch.value}", f"candidate-{index}")
            EngineeringResultStore(
                self.state, beam_id="beam-1", design_branch=branch
            ).store(result, source_input_revision=index)
            publications.begin_refresh(
                workspace_revision=index,
                beam_id="beam-1",
                design_branch=branch,
            )
            publications.publish(
                result,
                workspace_revision=index,
                beam_id="beam-1",
                design_branch=branch,
            )
        self.assertEqual(
            EngineeringResultStore(
                self.state,
                beam_id="beam-1",
                design_branch=DesignBranch.BEAM_INPUTS,
            ).current().engineering_hash,
            "hash-beam_inputs",
        )
        self.assertEqual(
            publications.current(
                beam_id="beam-1", design_branch=DesignBranch.LOAD_ANALYSIS
            ).active_engineering_hash,
            "hash-load_analysis",
        )

    def test_selection_only_change_causes_zero_execution(self) -> None:
        beam = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        workspace = resolve_branch_workspace(
            beam,
            None,
            ActionSource.MANUAL,
            ActionSelectionPolicy.MANUAL,
        )
        calls = {"calculation": 0, "brain": 0}

        def calculate(resolved, profile):
            calls["calculation"] += 1
            return {"workspace": resolved.engineering_hash, "profile": profile}

        def run_brain(resolved, calculation, search, preference):
            calls["brain"] += 1
            return _result(resolved.engineering_hash, "candidate-1")

        service = WorkspaceApplicationService(
            self.state, calculate=calculate, run_design_brain=run_brain
        )
        first = service.execute(workspace, "calc", "fast", "standard")
        selection = self.store.selection("beam-1")
        self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        second = service.execute(workspace, "calc", "fast", "standard")
        self.assertFalse(first.calculation_cache_hit)
        self.assertTrue(second.calculation_cache_hit)
        self.assertTrue(second.design_brain_cache_hit)
        self.assertEqual(calls, {"calculation": 1, "brain": 1})

    def test_calculation_only_execution_reuses_calculation_for_brain(self) -> None:
        beam = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        workspace = resolve_branch_workspace(
            beam,
            None,
            ActionSource.MANUAL,
            ActionSelectionPolicy.MANUAL,
        )
        calls = {"calculation": 0, "brain": 0}

        def calculate(resolved, profile):
            calls["calculation"] += 1
            return _result(resolved.engineering_hash, "calculation")

        def run_brain(resolved, calculation, search, preference):
            calls["brain"] += 1
            return _result(resolved.engineering_hash, "candidate")

        service = WorkspaceApplicationService(
            self.state, calculate=calculate, run_design_brain=run_brain
        )
        calculation_only = service.execute(
            workspace,
            "calc",
            "fast",
            "standard",
            include_design_brain=False,
        )
        complete = service.execute(workspace, "calc", "fast", "standard")
        self.assertIsNone(calculation_only.design_brain_result)
        self.assertTrue(complete.calculation_cache_hit)
        self.assertFalse(complete.design_brain_cache_hit)
        self.assertEqual(calls, {"calculation": 1, "brain": 1})

    def test_input_store_is_a_branch_command_facade_only(self) -> None:
        input_store = InputSnapshotStore(self.state)
        current = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        committed = input_store.commit_for_beam(
            "beam-1",
            {**current.to_mutable_dict(), "b": 275},
            source="test",
            branch=DesignBranch.BEAM_INPUTS,
            expected_branch_revision=current.revision,
        )
        self.assertEqual(committed.revision, current.revision + 1)
        self.assertEqual(
            self.store.get("beam-1", DesignBranch.BEAM_INPUTS).payload["b"],
            275,
        )
        self.assertNotIn("_inputs_engineering_input_snapshot_by_beam_v2", self.state)
        self.assertNotIn("_inputs_committed_engineering_state_by_beam_v1", self.state)

    def test_inputs_apply_is_stale_after_selection_changes(self) -> None:
        branch = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        result = _result("engineering-1", "candidate-1")
        EngineeringResultStore(
            self.state,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        ).store(result, source_input_revision=branch.revision)
        publications = PublicationStore(self.state)
        publications.begin_refresh(
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        )
        publications.publish(
            result,
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        )
        payload = stamp_branch_apply_identity(
            self.state,
            result=result,
            payload={"candidate_id": "candidate-1"},
        )
        valid, _ = validate_branch_apply_identity(
            self.state, result=result, payload=payload
        )
        self.assertTrue(valid)
        selection = self.store.selection("beam-1")
        self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        valid, reason = validate_branch_apply_identity(
            self.state, result=result, payload=payload
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "stale_apply_branch_changed")

    def test_load_analysis_apply_survives_main_selection_change(self) -> None:
        self.state["_active_page_slug"] = "design"
        branch = self.store.get("beam-1", DesignBranch.LOAD_ANALYSIS)
        analysis = LoadAnalysisSnapshotStore(self.state).ensure_seeded(
            "beam-1", {"spans": [4.0]}
        )
        result = _result("engineering-la", "candidate-la")
        EngineeringResultStore(
            self.state,
            beam_id="beam-1",
            design_branch=DesignBranch.LOAD_ANALYSIS,
        ).store(result, source_input_revision=branch.revision)
        publications = PublicationStore(self.state)
        publications.begin_refresh(
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.LOAD_ANALYSIS,
        )
        publications.publish(
            result,
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.LOAD_ANALYSIS,
        )
        payload = stamp_branch_apply_identity(
            self.state,
            result=result,
            payload={"candidate_id": "candidate-la"},
        )
        self.assertEqual(analysis.revision, 1)
        selection = self.store.selection("beam-1")
        self.store.select_main_design_branch(
            "beam-1",
            DesignBranch.LOAD_ANALYSIS,
            expected_selection_revision=selection.revision,
        )
        valid, reason = validate_branch_apply_identity(
            self.state, result=result, payload=payload
        )
        self.assertTrue(valid, reason)

    def test_apply_binds_actual_calculation_contract(self) -> None:
        branch = self.store.get("beam-1", DesignBranch.BEAM_INPUTS)
        result = _result("engineering-1", "candidate-1")
        EngineeringResultStore(
            self.state,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        ).store(result, source_input_revision=branch.revision)
        publications = PublicationStore(self.state)
        publications.begin_refresh(
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        )
        publications.publish(
            result,
            workspace_revision=branch.revision,
            beam_id="beam-1",
            design_branch=DesignBranch.BEAM_INPUTS,
        )
        payload = stamp_branch_apply_identity(
            self.state,
            result=result,
            payload={"candidate_id": "candidate-1"},
        )
        changed_calculation = replace(
            result,
            current_calculations={
                "actions_used": {"Mu": 100.0, "Vu": 20.0},
                "bending_utilisation": 0.91,
            },
        )
        valid, reason = validate_branch_apply_identity(
            self.state,
            result=changed_calculation,
            payload=payload,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "stale_apply_calculation_result")


if __name__ == "__main__":
    unittest.main()
