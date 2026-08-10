"""Branch-bound Apply intent and validation.

This module is page-neutral.  Renderers may stamp an Apply payload with the
identity of the exact branch publication they display; the typed Apply
boundary validates that identity again immediately before mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, MutableMapping

from application.contracts.design_brain import AuthoritativeDesignResult
from application.contracts.design_branch import DesignBranch, canonical_hash
from inputs_application.design_branch_store import BeamDesignBranchStore, branch_for_page
from inputs_application.design_guide_fragment_store import PublicationStore
from inputs_application.load_analysis_store import LoadAnalysisSnapshotStore


BRANCH_APPLY_IDENTITY_KEY = "_branch_apply_identity"


@dataclass(frozen=True)
class BranchApplyIdentity:
    beam_id: str
    design_branch: str
    branch_revision: int
    branch_hash: str
    load_analysis_revision: int | None
    load_analysis_hash: str | None
    action_source: str
    action_selection_policy: str
    design_actions_hash: str
    calculation_result_hash: str
    publication_authority_hash: str
    candidate_id: str
    require_selection_match: bool
    selection_revision: int | None = None
    selection_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _page_slug(state: Mapping[str, Any]) -> str:
    return str(
        state.get("_active_page_slug") or state.get("page_slug") or "inputs"
    ).strip().lower()


def _action_identity(branch: DesignBranch, payload: Mapping[str, Any]) -> tuple[str, str]:
    if branch is DesignBranch.LOAD_ANALYSIS:
        policy = str(payload.get("design_actions_source") or "max").strip().lower()
        return "load_analysis", "selected_section" if policy == "section" else "maximum"
    source = str(payload.get("actions_mode") or payload.get("actions_source") or "manual").strip().lower()
    if source in {"analysis", "calculated", "design", "load_analysis"}:
        policy = str(payload.get("design_actions_source") or "max").strip().lower()
        return "load_analysis", "selected_section" if policy == "section" else "maximum"
    return "manual", "manual"


def _candidate_id(payload: Mapping[str, Any]) -> str:
    resolved = payload.get("resolved_candidate")
    resolved = resolved if isinstance(resolved, Mapping) else {}
    return str(
        payload.get("source_candidate_id")
        or payload.get("candidate_id")
        or payload.get("recommendation_id")
        or resolved.get("source_candidate_id")
        or resolved.get("candidate_id")
        or ""
    ).strip()


def _actions_hash(result: AuthoritativeDesignResult | None) -> str:
    calculations = dict((result.current_calculations if result is not None else {}) or {})
    return canonical_hash(dict(calculations.get("actions_used") or {}))


def _calculation_result_hash(result: AuthoritativeDesignResult | None) -> str:
    """Hash the actual calculation contract, not merely its input identity."""

    return canonical_hash(
        dict((result.current_calculations if result is not None else {}) or {})
    )


def build_branch_apply_identity(
    state: MutableMapping[str, Any],
    *,
    result: AuthoritativeDesignResult,
    payload: Mapping[str, Any],
) -> BranchApplyIdentity:
    beam_id = str(state.get("active_beam_id") or "").strip()
    if not beam_id:
        raise ValueError("Apply requires an active beam")
    store = BeamDesignBranchStore(state)
    selection = store.selection(beam_id)
    page_slug = _page_slug(state)
    branch = branch_for_page(page_slug, selection)
    snapshot = store.get(beam_id, branch)
    if snapshot is None:
        raise ValueError("Apply requires a current branch snapshot")
    action_source, action_policy = _action_identity(branch, snapshot.payload)
    analysis = (
        LoadAnalysisSnapshotStore(state).current(beam_id)
        if action_source == "load_analysis"
        else None
    )
    fragment = PublicationStore(state).current(
        beam_id=beam_id,
        design_branch=branch,
    )
    publication_hash = str(
        result.publication_authority_hash
        or fragment.active_publication_authority_hash
        or ""
    )
    require_selection = page_slug != "design"
    return BranchApplyIdentity(
        beam_id=beam_id,
        design_branch=branch.value,
        branch_revision=snapshot.revision,
        branch_hash=snapshot.content_hash,
        load_analysis_revision=(analysis.revision if analysis is not None else None),
        load_analysis_hash=(analysis.content_hash if analysis is not None else None),
        action_source=action_source,
        action_selection_policy=action_policy,
        design_actions_hash=_actions_hash(result),
        calculation_result_hash=_calculation_result_hash(result),
        publication_authority_hash=publication_hash,
        candidate_id=_candidate_id(payload),
        require_selection_match=require_selection,
        selection_revision=(selection.revision if require_selection else None),
        selection_hash=(selection.content_hash if require_selection else None),
    )


def stamp_branch_apply_identity(
    state: MutableMapping[str, Any],
    *,
    result: AuthoritativeDesignResult,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    stamped = dict(payload)
    stamped[BRANCH_APPLY_IDENTITY_KEY] = build_branch_apply_identity(
        state,
        result=result,
        payload=stamped,
    ).to_dict()
    return stamped


def validate_branch_apply_identity(
    state: MutableMapping[str, Any],
    *,
    result: AuthoritativeDesignResult | None,
    payload: Mapping[str, Any],
) -> tuple[bool, str]:
    raw = payload.get(BRANCH_APPLY_IDENTITY_KEY)
    if not isinstance(raw, Mapping):
        return False, "missing_branch_apply_identity"
    try:
        expected = BranchApplyIdentity(**dict(raw))
        branch = DesignBranch(expected.design_branch)
    except (TypeError, ValueError):
        return False, "invalid_branch_apply_identity"
    beam_id = str(state.get("active_beam_id") or "").strip()
    if beam_id != expected.beam_id:
        return False, "stale_apply_beam_changed"
    store = BeamDesignBranchStore(state)
    selection = store.selection(beam_id)
    current_branch = branch_for_page(_page_slug(state), selection)
    if current_branch is not branch:
        return False, "stale_apply_branch_changed"
    snapshot = store.get(beam_id, branch)
    if snapshot is None:
        return False, "stale_apply_branch_missing"
    if snapshot.revision != expected.branch_revision or snapshot.content_hash != expected.branch_hash:
        return False, "stale_apply_branch_revision"
    action_source, action_policy = _action_identity(branch, snapshot.payload)
    if (action_source, action_policy) != (
        expected.action_source,
        expected.action_selection_policy,
    ):
        return False, "stale_apply_action_source"
    analysis = (
        LoadAnalysisSnapshotStore(state).current(beam_id)
        if action_source == "load_analysis"
        else None
    )
    if (analysis.revision if analysis else None) != expected.load_analysis_revision:
        return False, "stale_apply_load_analysis_revision"
    if (analysis.content_hash if analysis else None) != expected.load_analysis_hash:
        return False, "stale_apply_load_analysis_hash"
    if expected.require_selection_match and (
        selection.revision != expected.selection_revision
        or selection.content_hash != expected.selection_hash
    ):
        return False, "stale_apply_main_selection"
    if result is None:
        return False, "stale_apply_result_missing"
    if _calculation_result_hash(result) != expected.calculation_result_hash:
        return False, "stale_apply_calculation_result"
    if _actions_hash(result) != expected.design_actions_hash:
        return False, "stale_apply_design_actions"
    fragment = PublicationStore(state).current(
        beam_id=beam_id,
        design_branch=branch,
    )
    if str(fragment.active_publication_authority_hash or "") != expected.publication_authority_hash:
        return False, "stale_apply_publication"
    if str(result.publication_authority_hash or "") != expected.publication_authority_hash:
        return False, "stale_apply_result_publication"
    if _candidate_id(payload) != expected.candidate_id:
        return False, "stale_apply_candidate"
    return True, "branch_apply_identity_valid"


__all__ = [
    "BRANCH_APPLY_IDENTITY_KEY",
    "BranchApplyIdentity",
    "build_branch_apply_identity",
    "stamp_branch_apply_identity",
    "validate_branch_apply_identity",
]
