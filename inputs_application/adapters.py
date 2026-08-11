"""Production-shaped adapters over extracted, non-legacy owners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping

from application.engineering_snapshot import (
    build_engineering_input_snapshot_from_resolved_state,
)
from application.design_result_store import EngineeringResultStore
from application.design_run_coordinator import ensure_design_result
from application.guidance_result_adapter import (
    guidance_payload_from_authoritative_design_result,
)
from application.contracts.design_brain import (
    AuthoritativeDesignResult,
    EngineeringInputSnapshot,
)
from inputs_application.contracts import (
    InputsApplyCommand,
    InputsEngineeringResult,
    InputsPageRequest,
    InputsPublicationResult,
    InputsSessionMutation,
)
from inputs_application.recommendation_envelope import (
    effective_apply_mode_and_payload,
    recommendation_blocked_reason,
    recommendation_commit_eligible,
    recommendation_updates,
)
from state_and_helpers import SHARED_DEFAULTS
from inputs_application.post_apply_state import store_typed_post_apply_acceptance
from inputs_application.one_click_session import (
    pop_inputs_widget_keys_for_shared_updates,
)


# A Design Brain proposal may revise the beam design, never its applied loads.
# Keep this boundary explicit instead of accepting every legacy shared key.
DESIGN_RECOMMENDATION_UPDATE_KEYS = frozenset(
    {
        "b",
        "D",
        "L",
        "sec_shape",
        "cover_bot",
        "cover_top",
        "bot_row_count",
        "top_row_count",
        "top_bars",
        "top_spacing",
        "db_top",
        "lig_d",
        "lig_legs",
        "s_lig",
        "bot1_count",
        "bot1_spacing",
        "bot1_layout_mode",
        "bot2_count",
        "bot2_spacing",
        "bot2_layout_mode",
        "top1_count",
        "top1_spacing",
        "top1_layout_mode",
        "top2_count",
        "top2_spacing",
        "top2_layout_mode",
        "db_bot_1",
        "db_bot_2",
        "db_top_1",
        "db_top_2",
        *{
            f"{face}_row_{row}_{field}"
            for face in ("bot", "top")
            for row in (1, 2)
            for field in ("bars", "spacing", "dia", "mode")
        },
    }
)


DESIGN_ACTION_INVARIANT_KEYS = (
    "actions_source",
    "actions_mode",
    "design_actions_source",
    "Tu_star",
    "P_star",
    "N_star",
    "uls_Mstar",
    "uls_Mstar_pos_manual",
    "uls_Mstar_neg_manual",
    "uls_Vstar",
    "uls_Nstar",
    "sls_Mstar",
    "sls_Mstar_pos_manual",
    "sls_Mstar_neg_manual",
    "sls_Vstar",
    "sls_Nstar",
    "Mu_star_manual",
    "Mu_star_pos_manual",
    "Mu_star_neg_manual",
)


EngineeringEvaluator = Callable[
    [EngineeringInputSnapshot, bool],
    InputsEngineeringResult | Mapping[str, Any],
]
PublicationBuilder = Callable[
    [InputsPageRequest, InputsEngineeringResult],
    InputsPublicationResult,
]
ApplyExecutor = Callable[
    [InputsApplyCommand, InputsPublicationResult],
    InputsSessionMutation,
]
SharedStateWriter = Callable[..., None]
ActiveBeamPersister = Callable[[], Any]
ApplyFinalizer = Callable[..., Mapping[str, Any] | None]


def _expand_longitudinal_shared_alias_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Keep legacy and row-model reinforcement fields atomic in one mutation."""

    expanded = dict(updates)
    alias_pairs = (
        ("bot1_count", "bot_row_1_bars"),
        ("db_bot_1", "bot_row_1_dia"),
        ("bot1_layout_mode", "bot_row_1_mode"),
        ("bot1_spacing", "bot_row_1_spacing"),
        ("bot2_count", "bot_row_2_bars"),
        ("db_bot_2", "bot_row_2_dia"),
        ("bot2_layout_mode", "bot_row_2_mode"),
        ("bot2_spacing", "bot_row_2_spacing"),
        ("top1_count", "top_row_1_bars"),
        ("db_top_1", "top_row_1_dia"),
        ("top1_layout_mode", "top_row_1_mode"),
        ("top1_spacing", "top_row_1_spacing"),
        ("top2_count", "top_row_2_bars"),
        ("db_top_2", "top_row_2_dia"),
        ("top2_layout_mode", "top_row_2_mode"),
        ("top2_spacing", "top_row_2_spacing"),
    )
    for legacy_key, row_key in alias_pairs:
        if legacy_key in expanded and row_key not in expanded:
            expanded[row_key] = expanded[legacy_key]
        elif row_key in expanded and legacy_key not in expanded:
            expanded[legacy_key] = expanded[row_key]

    for section in ("bot", "top"):
        affected = any(
            key.startswith(f"{section}1_")
            or key.startswith(f"{section}2_")
            or key.startswith(f"{section}_row_")
            or key in {f"db_{section}_1", f"db_{section}_2"}
            for key in expanded
        )
        if not affected or f"{section}_row_count" in expanded:
            continue
        row_1 = expanded.get(
            f"{section}_row_1_bars",
            expanded.get(f"{section}1_count"),
        )
        row_2 = expanded.get(
            f"{section}_row_2_bars",
            expanded.get(f"{section}2_count"),
        )
        try:
            row_1_count = int(float(row_1 or 0))
            row_2_count = int(float(row_2 or 0))
        except (TypeError, ValueError):
            continue
        expanded[f"{section}_row_count"] = (
            2 if row_2_count > 0 else 1 if row_1_count > 0 else 0
        )
    return expanded


@dataclass
class ResolvedStateEngineeringPort:
    """Project resolved state with the canonical snapshot owner, then evaluate."""

    evaluator: EngineeringEvaluator
    contract_versions: Mapping[str, Any] = field(default_factory=dict)
    calculation_versions: Mapping[str, Any] = field(default_factory=dict)

    def evaluate(
        self,
        engineering_state: Mapping[str, object],
        *,
        force_recompute: bool = False,
    ) -> InputsEngineeringResult:
        snapshot = build_engineering_input_snapshot_from_resolved_state(
            engineering_state,
            contract_versions=self.contract_versions,
            calculation_versions=self.calculation_versions,
        )
        evaluated = self.evaluator(snapshot, bool(force_recompute))
        if isinstance(evaluated, InputsEngineeringResult):
            if evaluated.engineering_hash != snapshot.engineering_hash:
                raise ValueError("engineering evaluator returned the wrong engineering hash")
            return InputsEngineeringResult(
                engineering_hash=evaluated.engineering_hash,
                overview=evaluated.overview,
                checks=evaluated.checks,
                snapshot=snapshot,
            )
        payload = dict(evaluated or {})
        return InputsEngineeringResult(
            engineering_hash=snapshot.engineering_hash,
            overview=dict(payload.get("overview") or {}),
            checks=dict(payload.get("checks") or {}),
            snapshot=snapshot,
        )


@dataclass
class AuthoritativeDesignGuidePort:
    """Reuse or compute one immutable Design Brain result, then publish it."""

    result_store: EngineeringResultStore
    compute: Callable[[EngineeringInputSnapshot], AuthoritativeDesignResult]

    def publish(
        self,
        request: InputsPageRequest,
        engineering: InputsEngineeringResult,
    ) -> InputsPublicationResult:
        snapshot = engineering.snapshot
        if not isinstance(snapshot, EngineeringInputSnapshot):
            raise TypeError("engineering result is missing EngineeringInputSnapshot")
        result = ensure_design_result(
            result_store=self.result_store,
            snapshot=snapshot,
            compute_fn=self.compute,
            force=bool(request.force_recompute),
        )
        payload = guidance_payload_from_authoritative_design_result(result)
        publication = dict(payload.get("final_design_guide_publication") or {})
        if not publication:
            publication = dict(result.final_publication or {})
        cta = dict(publication.get("cta") or result.cta_model or {})
        outcome = str(
            publication.get("outcome_state")
            or result.family_outcome
            or ("ACTION" if cta.get("enabled") else "PASS")
        ).strip().upper()
        return InputsPublicationResult(
            publication_hash=str(
                publication.get("publication_hash")
                or result.publication_authority_hash
                or ""
            ),
            outcome=outcome,
            family_id=str(
                publication.get("selected_family")
                or publication.get("selected_family_id")
                or result.governing_family
                or ""
            ).strip()
            or None,
            cta=cta,
            payload=payload,
        )


@dataclass
class CallableDesignGuidePort:
    publisher: PublicationBuilder

    def publish(
        self,
        request: InputsPageRequest,
        engineering: InputsEngineeringResult,
    ) -> InputsPublicationResult:
        result = self.publisher(request, engineering)
        if not isinstance(result, InputsPublicationResult):
            raise TypeError("publisher must return InputsPublicationResult")
        return result


@dataclass
class CallableApplyPort:
    executor: ApplyExecutor

    def execute(
        self,
        command: InputsApplyCommand,
        *,
        publication: InputsPublicationResult,
    ) -> InputsSessionMutation:
        result = self.executor(command, publication)
        if not isinstance(result, InputsSessionMutation):
            raise TypeError("executor must return InputsSessionMutation")
        return result


@dataclass
class CanonicalRecommendationApplyPort:
    """Plan one canonical recommendation as an explicit shared-state mutation."""

    source: str = "guidance:typed_inputs_application"

    def execute(
        self,
        command: InputsApplyCommand,
        *,
        publication: InputsPublicationResult,
    ) -> InputsSessionMutation:
        recommendation = dict(command.payload)
        if publication.outcome != "ACTION" or not bool(publication.cta.get("enabled")):
            return InputsSessionMutation(
                status="failed",
                reason="authoritative_publication_not_actionable",
            )
        if not recommendation_commit_eligible(recommendation):
            return InputsSessionMutation(
                status="failed",
                reason=recommendation_blocked_reason(recommendation)
                or "candidate_not_commit_eligible",
            )
        mode, payload = effective_apply_mode_and_payload(recommendation)
        updates = {}
        if mode and isinstance(payload, dict):
            candidate_updates = (
                payload.get("resolved_candidate_updates")
                or payload.get("updates")
            )
            if isinstance(candidate_updates, dict):
                updates = dict(candidate_updates)
        if not updates:
            updates = recommendation_updates(recommendation)
        expanded_updates = _expand_longitudinal_shared_alias_updates(updates)
        row_model_updates = {
            str(key): value
            for key, value in expanded_updates.items()
            if str(key).startswith(("bot_row_", "top_row_"))
        }
        shared_updates = {
            key: value
            for key, value in expanded_updates.items()
            if key in SHARED_DEFAULTS
            and key in DESIGN_RECOMMENDATION_UPDATE_KEYS
            and not str(key).startswith("_")
        }
        if not shared_updates and not row_model_updates:
            return InputsSessionMutation(
                status="failed",
                reason="canonical_apply_payload_has_no_shared_updates",
            )
        return InputsSessionMutation(
            # Preserve row-model fields alongside shared mirrors.  The
            # SharedStateSessionPort writes these first so canonical
            # convenience resync cannot restore stale legacy reinforcement.
            updates={**row_model_updates, **shared_updates},
            removals=(
                "_auto_design_last_fingerprint",
                "_inputs_action_apply_recommendation_payload",
            ),
            rerun_required=True,
            status="rerun_required",
            reason=f"canonical_apply_planned:{mode or 'direct_updates'}",
        )


@dataclass
class MappingSessionPort:
    """Commit one explicit mutation to a supplied session mapping."""

    session_state: MutableMapping[str, Any]
    committed: list[InputsSessionMutation] = field(default_factory=list)

    def commit(self, mutation: InputsSessionMutation) -> None:
        if not isinstance(mutation, InputsSessionMutation):
            raise TypeError("mutation must be InputsSessionMutation")
        for key in mutation.removals:
            self.session_state.pop(key, None)
        self.session_state.update(dict(mutation.updates))
        self.committed.append(mutation)


@dataclass
class SharedStateSessionPort:
    """Commit typed Apply mutations through the canonical shared-state writer."""

    session_state: MutableMapping[str, Any]
    set_shared: SharedStateWriter
    finalize_publish: ApplyFinalizer
    persist_active_beam: ActiveBeamPersister
    source: str = "guidance:typed_inputs_application"
    focus_section: str | None = "model"
    store_post_apply_acceptance: bool = True
    committed: list[InputsSessionMutation] = field(default_factory=list)

    def commit(self, mutation: InputsSessionMutation) -> None:
        if not isinstance(mutation, InputsSessionMutation):
            raise TypeError("mutation must be InputsSessionMutation")
        active_beam_id = str(
            self.session_state.get("active_beam_id") or ""
        ).strip()
        input_store = None
        canonical_before: dict[str, Any] = {}
        if active_beam_id:
            from inputs_application.engineering_input_store import (
                InputSnapshotStore,
            )

            input_store = InputSnapshotStore(self.session_state)
            canonical_before = dict(
                input_store.current_for_beam(active_beam_id).snapshot or {}
            )
        if not canonical_before:
            # First Apply for a beam may predate the typed beam snapshot. Use
            # the current canonical projection once, then commit only through
            # InputSnapshotStore below.
            from state_and_helpers import get_beam_project_param_snapshot

            canonical_before = dict(get_beam_project_param_snapshot())
        actions_before = {
            key: canonical_before.get(key)
            for key in DESIGN_ACTION_INVARIANT_KEYS
        }
        for key in mutation.removals:
            self.session_state.pop(key, None)
        row_model_updates = {
            str(key): value
            for key, value in mutation.updates.items()
            if str(key).startswith(("bot_row_", "top_row_"))
        }
        # Row-model fields are canonical input state even though they are not
        # Streamlit shared-default keys.  Commit them before the shared writer
        # and its convenience-field resync so mirrors are derived from the
        # exact proposed arrangement.
        self.session_state.update(row_model_updates)
        shared_updates = (
            {
                key: value
                for key, value in mutation.updates.items()
                if key in SHARED_DEFAULTS
                and key in DESIGN_RECOMMENDATION_UPDATE_KEYS
            }
            if mutation.status != "failed"
            else {}
        )
        shared_before = {
            key: self.session_state.get(key)
            for key in shared_updates
        }
        for key, value in shared_updates.items():
            self.set_shared(key, value, source=self.source)
        shared_after = {
            key: self.session_state.get(key)
            for key in shared_updates
        }
        # The next authoritative snapshot must hydrate from the committed
        # shared transaction.  Leaving the previous Streamlit widget mirrors
        # alive lets their pre-Apply values overwrite these updates during the
        # current-widget projection step.
        cleared_widget_keys = pop_inputs_widget_keys_for_shared_updates(
            # Row-model fields are also canonical widget inputs.  Clearing
            # only the legacy shared aliases leaves e.g. inputs_bot_row_1_bars
            # in Streamlit's widget state, so the next rerun visibly restores
            # the pre-Apply value even though the committed transaction and
            # calculations already contain the proposed arrangement.
            {**row_model_updates, **shared_updates},
            session_state=self.session_state,
        )
        self.session_state["_typed_apply_state_commit_probe"] = {
            "status": mutation.status,
            "source": self.source,
            "sync_lock": bool(self.session_state.get("_sync_lock")),
            "requested_updates": dict(shared_updates),
            "shared_before": shared_before,
            "shared_after": shared_after,
            "cleared_widget_keys": sorted(cleared_widget_keys),
            "all_requested_updates_committed": bool(shared_updates)
            and all(
                shared_after.get(key) == value
                for key, value in shared_updates.items()
            ),
        }
        if shared_updates:
            # Apply is an input transaction, not only a shared-key mutation.
            # Promote the exact post-Apply canonical beam snapshot before the
            # next render can ask the InputSnapshotStore for its authority.
            # Without this, the shared mapping contains the proposed values
            # while the beam-owned snapshot still contains the pre-Apply
            # values, so setup legitimately rehydrates the old result.
            if active_beam_id:
                canonical_after = dict(canonical_before)
                canonical_after.update(row_model_updates)
                canonical_after.update(shared_updates)
                actions_after = {
                    key: canonical_after.get(key)
                    for key in DESIGN_ACTION_INVARIANT_KEYS
                }
                if actions_after != actions_before:
                    raise ValueError(
                        "typed Apply attempted to change design actions"
                    )
                committed_input = input_store.commit_active_beam(
                    canonical_after,
                    changed_keys=tuple(
                        sorted({*row_model_updates, *shared_updates})
                    ),
                    source=f"{self.source}:input_transaction",
                )
                self.session_state[
                    "_inputs_authoritative_result_snapshot_update_pending"
                ] = True
                # The Apply rerun must reseed every Inputs widget from the
                # committed beam snapshot.  This includes V2 row-model keys
                # (for example inputs_bot_row_1_bars), which are not reliably
                # refreshed by Streamlit once a widget has an existing value.
                # Set the one-shot flag at the transaction boundary so the
                # page shell, rather than the Design Brain fragment, owns the
                # hydration on the next render.
                self.session_state["_force_inputs_widget_reseed_once"] = True
                self.session_state["_inputs_pending_input_revision"] = int(
                    committed_input.revision
                )
                self.session_state["_typed_apply_input_transaction_probe"] = {
                    "beam_id": active_beam_id,
                    "revision": int(committed_input.revision),
                    "changed_keys": list(committed_input.changed_keys),
                    "design_actions_preserved": True,
                    "bot_row_1_dia": committed_input.snapshot.get(
                        "bot_row_1_dia"
                    ),
                    "db_bot_1": committed_input.snapshot.get("db_bot_1"),
                }
            self.finalize_publish(
                updated_keys=sorted(shared_updates),
                source=self.source,
                focus_section=self.focus_section,
                set_run_design_clicked=True,
            )
            # Persist the committed shared values before the Apply-triggered
            # rerun can hydrate this beam from its stored record.
            self.persist_active_beam()
            if self.store_post_apply_acceptance:
                store_typed_post_apply_acceptance(
                    self.session_state,
                    {
                        key: self.session_state.get(key, default)
                        for key, default in SHARED_DEFAULTS.items()
                    },
                )
        self.committed.append(mutation)


__all__ = [
    "AuthoritativeDesignGuidePort",
    "CanonicalRecommendationApplyPort",
    "CallableApplyPort",
    "CallableDesignGuidePort",
    "MappingSessionPort",
    "ResolvedStateEngineeringPort",
    "SharedStateSessionPort",
]
