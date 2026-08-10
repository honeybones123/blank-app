"""Page-neutral execution owner for branch engineering work.

The current Streamlit workspace can migrate into this service incrementally;
pages are deliberately absent from the contract.  All cache and publication
identities include the branch workspace rather than a widget/session alias.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, MutableMapping

from application.contracts.design_branch import canonical_hash
from application.contracts.design_brain import AuthoritativeDesignResult
from application.design_result_store import EngineeringResultStore
from inputs_application.branch_workspace import EngineeringWorkspaceSnapshot
from inputs_application.design_actions_store import DerivedDesignActionsStore
from inputs_application.design_guide_fragment_store import PublicationStore


CALCULATION_CACHE_KEY = "_branch_workspace_calculation_cache_v1"
DESIGN_BRAIN_CACHE_KEY = "_branch_workspace_design_brain_cache_v1"
BRANCH_RESULT_KEY = "_branch_workspace_results_v1"


@dataclass(frozen=True)
class BranchWorkspaceResult:
    workspace: EngineeringWorkspaceSnapshot
    calculation_result: Any
    design_brain_result: AuthoritativeDesignResult | None
    calculation_cache_hit: bool
    design_brain_cache_hit: bool
    calculation_cache_key: str
    design_brain_cache_key: str


@dataclass(frozen=True)
class RuntimeCalculationProfile:
    identity: str = "runtime-calculation.v1"


@dataclass(frozen=True)
class RuntimeSearchProfile:
    identity: str = "installed-v2-default-search"
    family_hint: str | None = None
    debug_enabled: bool = False


@dataclass(frozen=True)
class RuntimePreferenceProfile:
    preference_profile_id: str = "runtime-standard-buildable"
    preference_profile_version: str = "1"
    design_brain_version: str = "installed-v2"
    family_contract_version: str = "family-owned.v1"


class WorkspaceApplicationService:
    """Execute one immutable workspace through injected engineering ports."""

    def __init__(
        self,
        storage: MutableMapping[str, Any],
        *,
        calculate: Callable[[EngineeringWorkspaceSnapshot, Any], Any],
        run_design_brain: Callable[[EngineeringWorkspaceSnapshot, Any, Any, Any], AuthoritativeDesignResult],
    ) -> None:
        self._state = storage
        self._calculate = calculate
        self._run_design_brain = run_design_brain

    @staticmethod
    def _profile_value(profile: Any, *names: str, default: str = "") -> str:
        for name in names:
            value = getattr(profile, name, None)
            if value not in (None, ""):
                return str(getattr(value, "value", value))
        return default

    def execute(
        self,
        workspace: EngineeringWorkspaceSnapshot,
        calculation_profile: Any,
        search_profile: Any,
        preference_profile: Any,
        *,
        include_design_brain: bool = True,
    ) -> BranchWorkspaceResult:
        calculation_key = canonical_hash(
            {
                "workspace_engineering_hash": workspace.engineering_hash,
                "calculation_version": workspace.identity.calculation_version,
                "calculation_profile": repr(calculation_profile),
            }
        )
        calculation_cache = dict(self._state.get(CALCULATION_CACHE_KEY) or {})
        calculation_hit = calculation_key in calculation_cache
        calculation_result = calculation_cache.get(calculation_key)
        if not calculation_hit:
            calculation_result = self._calculate(workspace, calculation_profile)
            calculation_cache[calculation_key] = calculation_result
            self._state[CALCULATION_CACHE_KEY] = calculation_cache

        engineering_result_hash = canonical_hash(
            getattr(calculation_result, "to_dict", lambda: calculation_result)()
            if callable(getattr(calculation_result, "to_dict", None))
            else calculation_result
        )
        brain_key = canonical_hash(
            {
                "beam_id": workspace.identity.beam_id,
                "design_branch": workspace.identity.design_branch.value,
                "workspace_engineering_hash": workspace.engineering_hash,
                "engineering_result_hash": engineering_result_hash,
                "design_brain_version": self._profile_value(
                    preference_profile, "design_brain_version", default="installed-v2"
                ),
                "family_contract_version": self._profile_value(
                    preference_profile, "family_contract_version", default="runtime"
                ),
                "preference_profile_id": self._profile_value(
                    preference_profile, "preference_profile_id"
                ),
                "preference_profile_version": self._profile_value(
                    preference_profile, "preference_profile_version"
                ),
                "search_profile": repr(search_profile),
            }
        )
        brain_cache = dict(self._state.get(DESIGN_BRAIN_CACHE_KEY) or {})
        brain_hit = bool(include_design_brain and brain_key in brain_cache)
        brain_result = brain_cache.get(brain_key) if include_design_brain else None
        if include_design_brain and not brain_hit:
            brain_result = self._run_design_brain(
                workspace,
                calculation_result,
                search_profile,
                preference_profile,
            )
            brain_cache[brain_key] = brain_result
            self._state[DESIGN_BRAIN_CACHE_KEY] = brain_cache

        if brain_result is not None and not isinstance(
            brain_result, AuthoritativeDesignResult
        ):
            raise TypeError("Design Brain port must return AuthoritativeDesignResult")
        calculation_engineering_hash = str(
            getattr(calculation_result, "engineering_hash", "") or ""
        )
        if (
            brain_result is not None
            and calculation_engineering_hash
            and brain_result.engineering_hash != calculation_engineering_hash
        ):
            raise ValueError(
                "Design Brain result does not match the calculated engineering identity"
            )
        branch_key = (
            f"{workspace.identity.beam_id}:"
            f"{workspace.identity.design_branch.value}"
        )
        result = BranchWorkspaceResult(
            workspace=workspace,
            calculation_result=calculation_result,
            design_brain_result=brain_result,
            calculation_cache_hit=calculation_hit,
            design_brain_cache_hit=brain_hit,
            calculation_cache_key=calculation_key,
            design_brain_cache_key=brain_key,
        )
        results = dict(self._state.get(BRANCH_RESULT_KEY) or {})
        results[branch_key] = result
        self._state[BRANCH_RESULT_KEY] = results
        if workspace.design_actions is not None:
            DerivedDesignActionsStore(self._state).publish(
                workspace.identity,
                workspace.design_actions,
            )
        authoritative_result = (
            brain_result
            if brain_result is not None
            else (
                calculation_result
                if isinstance(calculation_result, AuthoritativeDesignResult)
                else None
            )
        )
        if authoritative_result is not None:
            EngineeringResultStore(
                self._state,
                beam_id=workspace.identity.beam_id,
                design_branch=workspace.identity.design_branch,
            ).store(
                authoritative_result,
                source_input_revision=workspace.identity.branch_revision,
            )
        if brain_result is not None:
            publication_store = PublicationStore(self._state)
            current = publication_store.current(
                beam_id=workspace.identity.beam_id,
                design_branch=workspace.identity.design_branch,
            )
            if current.pending_workspace_revision != workspace.identity.branch_revision:
                publication_store.begin_refresh(
                    workspace_revision=workspace.identity.branch_revision,
                    beam_id=workspace.identity.beam_id,
                    design_branch=workspace.identity.design_branch,
                )
            publication_store.publish(
                brain_result,
                workspace_revision=workspace.identity.branch_revision,
                beam_id=workspace.identity.beam_id,
                design_branch=workspace.identity.design_branch,
            )
        return result


def execute_installed_v2_workspace(
    storage: MutableMapping[str, Any],
    workspace: EngineeringWorkspaceSnapshot,
    *,
    calculation_profile: Any | None = None,
    search_profile: Any | None = None,
    preference_profile: Any | None = None,
    include_design_brain: bool = True,
    family_hint: str | None = None,
    debug_enabled: bool = False,
) -> BranchWorkspaceResult:
    """Execute Runtime's sole installed V2 implementation for one branch.

    This composition boundary is intentionally page-neutral.  It is the only
    place in the branch cutover that binds the workspace resolver to the
    concrete calculation/Design Brain implementation.
    """

    from application.design_brain_port import DesignBrainRequest
    from application.engineering_snapshot import (
        build_engineering_input_snapshot_from_resolved_state,
    )
    from inputs_application.design_brain_composition import (
        build_design_brain_service,
        calculate_v2_authoritative_result,
    )

    def _calculate(
        resolved_workspace: EngineeringWorkspaceSnapshot,
        _profile: Any,
    ) -> AuthoritativeDesignResult:
        resolved_state = resolved_workspace.to_mutable_state()
        engineering_snapshot = build_engineering_input_snapshot_from_resolved_state(
            resolved_state
        )
        return calculate_v2_authoritative_result(
            engineering_snapshot=engineering_snapshot,
            resolved_inputs=resolved_state,
            input_revision=resolved_workspace.identity.branch_revision,
        )

    # Calculation-only consumers (currently Load Analysis) must not even
    # construct the Design Brain service.  Beam Inputs remains the sole UI
    # execution and Apply surface for recommendations.
    design_brain_service = (
        build_design_brain_service(adapter_name="v2")
        if include_design_brain
        else None
    )

    effective_search_profile = search_profile or RuntimeSearchProfile(
        family_hint=str(family_hint or "").strip() or None,
        debug_enabled=bool(debug_enabled),
    )

    def _run_design_brain(
        resolved_workspace: EngineeringWorkspaceSnapshot,
        calculation_result: AuthoritativeDesignResult,
        selected_search_profile: Any,
        _preference_profile: Any,
    ) -> AuthoritativeDesignResult:
        if design_brain_service is None:
            raise RuntimeError("Design Brain execution is disabled for this workspace")
        resolved_state = resolved_workspace.to_mutable_state()
        engineering_snapshot = build_engineering_input_snapshot_from_resolved_state(
            resolved_state
        )
        execution = design_brain_service.run(
            DesignBrainRequest(
                engineering_snapshot=engineering_snapshot,
                input_revision=resolved_workspace.identity.branch_revision,
                family_hint=(
                    str(getattr(selected_search_profile, "family_hint", "") or "").strip()
                    or None
                ),
                resolved_inputs=resolved_state,
                engineering_calculations=dict(
                    calculation_result.current_calculations or {}
                ),
                debug_enabled=bool(
                    getattr(selected_search_profile, "debug_enabled", False)
                ),
            )
        )
        return execution.result

    return WorkspaceApplicationService(
        storage,
        calculate=_calculate,
        run_design_brain=_run_design_brain,
    ).execute(
        workspace,
        calculation_profile or RuntimeCalculationProfile(),
        effective_search_profile,
        preference_profile or RuntimePreferenceProfile(),
        include_design_brain=include_design_brain,
    )


__all__ = [
    "BranchWorkspaceResult",
    "RuntimeCalculationProfile",
    "RuntimePreferenceProfile",
    "RuntimeSearchProfile",
    "WorkspaceApplicationService",
    "execute_installed_v2_workspace",
]
