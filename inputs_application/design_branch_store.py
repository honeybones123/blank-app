"""Single storage and command owner for beam design branches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping

from application.contracts.design_branch import (
    BeamDesignSnapshot,
    DesignBranch,
    MainDesignSelection,
    canonical_hash,
)


BRANCH_SNAPSHOT_STATE_KEY = "_beam_design_branch_snapshots_v1"
MAIN_DESIGN_SELECTION_STATE_KEY = "_beam_main_design_selection_v1"
BRANCH_MIGRATION_STATE_KEY = "_beam_design_branch_migration_v1"
BRANCH_MIGRATION_VERSION = "dual_design_branches.v1"
ACTIVE_DESIGN_BRANCH_CONTEXT_KEY = "_runtime_active_design_branch"

# LOAD_ANALYSIS receives its action policy from LoadAnalysisSnapshot and its
# solved actions from DerivedDesignActionsStore. These fields must never be
# copied into the editable design branch payload.
LOAD_ANALYSIS_BRANCH_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {
        "actions_source",
        "actions_mode",
        "loads_edit_mode",
        "loads_edit_toggle",
        "design_actions_source",
        "design_section_x_m",
        "section_cursor_x_m",
        "design_section_committed",
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
        "load_Mstar_proxy",
        "load_Mstar_pos_proxy",
        "load_Mstar_neg_proxy",
        "load_Vstar_proxy",
        "load_Nstar_proxy",
    }
)


class StaleBranchRevisionError(ValueError):
    pass


class StaleSelectionRevisionError(ValueError):
    pass


@dataclass(frozen=True)
class BranchUpdate:
    updates: Mapping[str, Any]
    source: str = "branch_edit"


def branch_for_page(
    page_slug: str | None,
    selection: MainDesignSelection,
) -> DesignBranch:
    return (
        DesignBranch.LOAD_ANALYSIS
        if str(page_slug or "").strip().lower() == "design"
        else selection.selected_branch
    )


class BeamDesignBranchStore:
    """Persist branch records without exposing session state as an API."""

    def __init__(self, storage: MutableMapping[str, Any]) -> None:
        self._state = storage

    def _branches(self) -> dict[str, Any]:
        value = self._state.get(BRANCH_SNAPSHOT_STATE_KEY)
        return dict(value) if isinstance(value, dict) else {}

    def _selections(self) -> dict[str, Any]:
        value = self._state.get(MAIN_DESIGN_SELECTION_STATE_KEY)
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _snapshot_from_record(record: Any) -> BeamDesignSnapshot | None:
        if isinstance(record, BeamDesignSnapshot):
            return record
        if not isinstance(record, Mapping):
            return None
        return BeamDesignSnapshot(
            beam_id=str(record.get("beam_id") or ""),
            design_branch=DesignBranch(str(record.get("design_branch"))),
            revision=int(record.get("revision", 0) or 0),
            content_hash=str(record.get("content_hash") or ""),
            payload=dict(record.get("payload") or {}),
            source=str(record.get("source") or ""),
            source_revision=(
                int(record["source_revision"])
                if record.get("source_revision") is not None
                else None
            ),
            source_hash=(
                str(record.get("source_hash"))
                if record.get("source_hash")
                else None
            ),
        )

    @staticmethod
    def _selection_from_record(record: Any) -> MainDesignSelection | None:
        if isinstance(record, MainDesignSelection):
            return record
        if not isinstance(record, Mapping):
            return None
        return MainDesignSelection(
            beam_id=str(record.get("beam_id") or ""),
            selected_branch=DesignBranch(str(record.get("selected_branch"))),
            revision=int(record.get("revision", 0) or 0),
            content_hash=str(record.get("content_hash") or ""),
        )

    def get(self, beam_id: str, branch: DesignBranch) -> BeamDesignSnapshot | None:
        beam_records = self._branches().get(str(beam_id), {})
        if not isinstance(beam_records, Mapping):
            return None
        return self._snapshot_from_record(beam_records.get(DesignBranch(branch).value))

    def selection(self, beam_id: str) -> MainDesignSelection:
        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            raise ValueError("beam_id is required")
        selected = self._selection_from_record(self._selections().get(resolved_beam_id))
        return selected or MainDesignSelection(
            beam_id=resolved_beam_id,
            selected_branch=DesignBranch.BEAM_INPUTS,
            revision=0,
        )

    def selected_snapshot(self, beam_id: str) -> BeamDesignSnapshot | None:
        selection = self.selection(beam_id)
        return self.get(beam_id, selection.selected_branch)

    def ensure_migrated(
        self,
        beam_id: str,
        *,
        beam_inputs_seed: Mapping[str, Any],
        load_analysis_seed: Mapping[str, Any] | None = None,
        load_analysis_source_revision: int | None = None,
        load_analysis_source_hash: str | None = None,
    ) -> None:
        """Idempotently create both branches once for one beam."""

        resolved_beam_id = str(beam_id or "").strip()
        if not resolved_beam_id:
            raise ValueError("beam_id is required")
        migrations = dict(self._state.get(BRANCH_MIGRATION_STATE_KEY) or {})
        existing_records = self._branches().get(resolved_beam_id)
        migration_complete = bool(
            isinstance(existing_records, Mapping)
            and all(branch.value in existing_records for branch in DesignBranch)
            and resolved_beam_id in self._selections()
        )
        if (
            migrations.get(resolved_beam_id) == BRANCH_MIGRATION_VERSION
            and migration_complete
        ):
            return

        branches = self._branches()
        beam_records = dict(branches.get(resolved_beam_id) or {})
        if DesignBranch.BEAM_INPUTS.value not in beam_records:
            payload = dict(beam_inputs_seed or {})
            snapshot = BeamDesignSnapshot(
                beam_id=resolved_beam_id,
                design_branch=DesignBranch.BEAM_INPUTS,
                revision=1 if payload else 0,
                content_hash=canonical_hash(payload),
                payload=payload,
                source="dual_branch_migration:beam_inputs",
            )
            beam_records[DesignBranch.BEAM_INPUTS.value] = snapshot.to_record()
        if DesignBranch.LOAD_ANALYSIS.value not in beam_records:
            payload = dict(
                load_analysis_seed
                if load_analysis_seed is not None
                else beam_inputs_seed or {}
            )
            snapshot = BeamDesignSnapshot(
                beam_id=resolved_beam_id,
                design_branch=DesignBranch.LOAD_ANALYSIS,
                revision=1 if payload else 0,
                content_hash=canonical_hash(payload),
                payload=payload,
                source=(
                    "dual_branch_migration:existing_load_analysis"
                    if (
                        load_analysis_seed is not None
                        and (
                            load_analysis_source_revision is not None
                            or load_analysis_source_hash is not None
                        )
                    )
                    else "dual_branch_migration:seed_from_beam_inputs"
                ),
                source_revision=load_analysis_source_revision,
                source_hash=load_analysis_source_hash,
            )
            beam_records[DesignBranch.LOAD_ANALYSIS.value] = snapshot.to_record()

        branches[resolved_beam_id] = beam_records
        self._state[BRANCH_SNAPSHOT_STATE_KEY] = branches
        selections = self._selections()
        selections.setdefault(
            resolved_beam_id,
            MainDesignSelection(
                beam_id=resolved_beam_id,
                selected_branch=DesignBranch.BEAM_INPUTS,
                revision=0,
            ).to_record(),
        )
        self._state[MAIN_DESIGN_SELECTION_STATE_KEY] = selections
        migrations[resolved_beam_id] = BRANCH_MIGRATION_VERSION
        self._state[BRANCH_MIGRATION_STATE_KEY] = migrations

    def replace(
        self,
        beam_id: str,
        branch: DesignBranch,
        *,
        expected_branch_revision: int,
        payload: Mapping[str, Any],
        source: str,
    ) -> BeamDesignSnapshot:
        resolved_branch = DesignBranch(branch)
        current = self.get(beam_id, resolved_branch)
        current_revision = int(current.revision if current is not None else 0)
        if int(expected_branch_revision) != current_revision:
            raise StaleBranchRevisionError(
                f"expected branch revision {expected_branch_revision}, current is {current_revision}"
            )
        resolved_payload = dict(payload or {})
        new_hash = canonical_hash(resolved_payload)
        if current is not None and current.content_hash == new_hash:
            return current
        snapshot = BeamDesignSnapshot(
            beam_id=str(beam_id),
            design_branch=resolved_branch,
            revision=current_revision + 1,
            content_hash=new_hash,
            payload=resolved_payload,
            source=str(source or "branch_replace"),
        )
        branches = self._branches()
        beam_records = dict(branches.get(str(beam_id)) or {})
        beam_records[resolved_branch.value] = snapshot.to_record()
        branches[str(beam_id)] = beam_records
        self._state[BRANCH_SNAPSHOT_STATE_KEY] = branches
        return snapshot

    def apply_branch_edit(
        self,
        beam_id: str,
        branch: DesignBranch,
        *,
        expected_branch_revision: int,
        update: BranchUpdate,
    ) -> BeamDesignSnapshot:
        current = self.get(beam_id, branch)
        base = current.to_payload() if current is not None else {}
        base.update(dict(update.updates or {}))
        return self.replace(
            beam_id,
            branch,
            expected_branch_revision=expected_branch_revision,
            payload=base,
            source=update.source,
        )

    def select_main_design_branch(
        self,
        beam_id: str,
        branch: DesignBranch,
        *,
        expected_selection_revision: int,
    ) -> MainDesignSelection:
        current = self.selection(beam_id)
        if current.revision != int(expected_selection_revision):
            raise StaleSelectionRevisionError(
                f"expected selection revision {expected_selection_revision}, current is {current.revision}"
            )
        resolved_branch = DesignBranch(branch)
        if current.selected_branch is resolved_branch:
            return current
        if self.get(beam_id, resolved_branch) is None:
            raise ValueError("selected branch has not been migrated")
        selection = MainDesignSelection(
            beam_id=str(beam_id),
            selected_branch=resolved_branch,
            revision=current.revision + 1,
        )
        selections = self._selections()
        selections[str(beam_id)] = selection.to_record()
        self._state[MAIN_DESIGN_SELECTION_STATE_KEY] = selections
        return selection

    def set_active_context(self, branch: DesignBranch) -> DesignBranch:
        resolved = DesignBranch(branch)
        self._state[ACTIVE_DESIGN_BRANCH_CONTEXT_KEY] = resolved.value
        return resolved

    def active_context(self, beam_id: str, *, page_slug: str | None = None) -> DesignBranch:
        if page_slug is not None:
            return branch_for_page(page_slug, self.selection(beam_id))
        raw = self._state.get(ACTIVE_DESIGN_BRANCH_CONTEXT_KEY)
        if raw:
            return DesignBranch(str(raw))
        return self.selection(beam_id).selected_branch

    def export_for_beam(self, beam_id: str) -> dict[str, Any]:
        branch_records = self._branches().get(str(beam_id), {})
        return {
            "migration_version": dict(
                self._state.get(BRANCH_MIGRATION_STATE_KEY) or {}
            ).get(str(beam_id)),
            "branches": dict(branch_records) if isinstance(branch_records, Mapping) else {},
            "main_selection": self.selection(beam_id).to_record(),
        }

    def import_for_beam(self, beam_id: str, payload: Mapping[str, Any]) -> None:
        resolved_beam_id = str(beam_id or "").strip()
        branch_payload = dict(payload or {})
        records = dict(branch_payload.get("branches") or {})
        validated: dict[str, Any] = {}
        for branch in DesignBranch:
            snapshot = self._snapshot_from_record(records.get(branch.value))
            if snapshot is not None and snapshot.beam_id == resolved_beam_id:
                validated[branch.value] = snapshot.to_record()
        if validated:
            branches = self._branches()
            branches[resolved_beam_id] = validated
            self._state[BRANCH_SNAPSHOT_STATE_KEY] = branches
        selection = self._selection_from_record(branch_payload.get("main_selection"))
        if selection is not None and selection.beam_id == resolved_beam_id:
            selections = self._selections()
            selections[resolved_beam_id] = selection.to_record()
            self._state[MAIN_DESIGN_SELECTION_STATE_KEY] = selections
        migrations = dict(self._state.get(BRANCH_MIGRATION_STATE_KEY) or {})
        if branch_payload.get("migration_version"):
            migrations[resolved_beam_id] = str(branch_payload["migration_version"])
            self._state[BRANCH_MIGRATION_STATE_KEY] = migrations

    def delete_beam(self, beam_id: str) -> None:
        resolved = str(beam_id or "").strip()
        if not resolved:
            return
        branches = self._branches()
        branches.pop(resolved, None)
        self._state[BRANCH_SNAPSHOT_STATE_KEY] = branches
        selections = self._selections()
        selections.pop(resolved, None)
        self._state[MAIN_DESIGN_SELECTION_STATE_KEY] = selections
        migrations = dict(self._state.get(BRANCH_MIGRATION_STATE_KEY) or {})
        migrations.pop(resolved, None)
        self._state[BRANCH_MIGRATION_STATE_KEY] = migrations


def apply_branch_edit(
    storage: MutableMapping[str, Any],
    beam_id: str,
    branch: DesignBranch,
    expected_branch_revision: int,
    updates: Mapping[str, Any],
    *,
    source: str = "branch_edit",
) -> BeamDesignSnapshot:
    return BeamDesignBranchStore(storage).apply_branch_edit(
        beam_id,
        branch,
        expected_branch_revision=expected_branch_revision,
        update=BranchUpdate(updates=dict(updates), source=source),
    )


def select_main_design_branch(
    storage: MutableMapping[str, Any],
    beam_id: str,
    branch: DesignBranch,
    expected_selection_revision: int,
) -> MainDesignSelection:
    return BeamDesignBranchStore(storage).select_main_design_branch(
        beam_id,
        branch,
        expected_selection_revision=expected_selection_revision,
    )


__all__ = [
    "ACTIVE_DESIGN_BRANCH_CONTEXT_KEY",
    "BRANCH_MIGRATION_STATE_KEY",
    "BRANCH_MIGRATION_VERSION",
    "BRANCH_SNAPSHOT_STATE_KEY",
    "BeamDesignBranchStore",
    "BranchUpdate",
    "MAIN_DESIGN_SELECTION_STATE_KEY",
    "LOAD_ANALYSIS_BRANCH_EXCLUDED_FIELDS",
    "StaleBranchRevisionError",
    "StaleSelectionRevisionError",
    "apply_branch_edit",
    "branch_for_page",
    "select_main_design_branch",
]
