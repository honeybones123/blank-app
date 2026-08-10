"""Single optimistic-concurrency owner for analysis-only beam state."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

from application.contracts.load_analysis import LoadAnalysisSnapshot


LOAD_ANALYSIS_SNAPSHOT_STATE_KEY = "_load_analysis_snapshot_by_beam_v1"


class StaleLoadAnalysisRevisionError(ValueError):
    pass


class LoadAnalysisSnapshotStore:
    def __init__(self, storage: MutableMapping[str, Any]) -> None:
        self._state = storage

    def current(self, beam_id: str) -> LoadAnalysisSnapshot | None:
        records = self._state.get(LOAD_ANALYSIS_SNAPSHOT_STATE_KEY)
        record = records.get(str(beam_id)) if isinstance(records, dict) else None
        if isinstance(record, LoadAnalysisSnapshot):
            return record
        if not isinstance(record, Mapping):
            return None
        return LoadAnalysisSnapshot(
            beam_id=str(record.get("beam_id") or beam_id),
            revision=int(record.get("revision", 0) or 0),
            content_hash=str(record.get("content_hash") or ""),
            analysis=dict(record.get("analysis") or {}),
        )

    def ensure_seeded(self, beam_id: str, analysis: Mapping[str, Any]) -> LoadAnalysisSnapshot:
        current = self.current(beam_id)
        if current is not None:
            return current
        return self.replace(
            beam_id,
            expected_revision=0,
            analysis=analysis,
        )

    def replace(
        self,
        beam_id: str,
        *,
        expected_revision: int,
        analysis: Mapping[str, Any],
    ) -> LoadAnalysisSnapshot:
        current = self.current(beam_id)
        current_revision = int(current.revision if current else 0)
        if int(expected_revision) != current_revision:
            raise StaleLoadAnalysisRevisionError(
                f"expected Load Analysis revision {expected_revision}, current is {current_revision}"
            )
        candidate = LoadAnalysisSnapshot(
            beam_id=str(beam_id),
            revision=current_revision + 1,
            analysis=dict(analysis or {}),
        )
        if current is not None and current.content_hash == candidate.content_hash:
            return current
        records = dict(self._state.get(LOAD_ANALYSIS_SNAPSHOT_STATE_KEY) or {})
        records[str(beam_id)] = {
            "beam_id": candidate.beam_id,
            "revision": candidate.revision,
            "content_hash": candidate.content_hash,
            "analysis": candidate.to_mutable_dict(),
        }
        self._state[LOAD_ANALYSIS_SNAPSHOT_STATE_KEY] = records
        return candidate

    def export_for_beam(self, beam_id: str) -> dict[str, Any]:
        current = self.current(beam_id)
        if current is None:
            return {}
        return {
            "beam_id": current.beam_id,
            "revision": current.revision,
            "content_hash": current.content_hash,
            "analysis": current.to_mutable_dict(),
        }

    def import_for_beam(self, beam_id: str, record: Mapping[str, Any]) -> None:
        if not isinstance(record, Mapping) or not record:
            return
        snapshot = LoadAnalysisSnapshot(
            beam_id=str(record.get("beam_id") or beam_id),
            revision=int(record.get("revision", 0) or 0),
            content_hash=str(record.get("content_hash") or ""),
            analysis=dict(record.get("analysis") or {}),
        )
        if snapshot.beam_id != str(beam_id):
            raise ValueError("Load Analysis snapshot belongs to another beam")
        records = dict(self._state.get(LOAD_ANALYSIS_SNAPSHOT_STATE_KEY) or {})
        records[str(beam_id)] = {
            "beam_id": snapshot.beam_id,
            "revision": snapshot.revision,
            "content_hash": snapshot.content_hash,
            "analysis": snapshot.to_mutable_dict(),
        }
        self._state[LOAD_ANALYSIS_SNAPSHOT_STATE_KEY] = records

    def delete_beam(self, beam_id: str) -> None:
        records = dict(self._state.get(LOAD_ANALYSIS_SNAPSHOT_STATE_KEY) or {})
        records.pop(str(beam_id), None)
        self._state[LOAD_ANALYSIS_SNAPSHOT_STATE_KEY] = records


__all__ = [
    "LOAD_ANALYSIS_SNAPSHOT_STATE_KEY",
    "LoadAnalysisSnapshotStore",
    "StaleLoadAnalysisRevisionError",
]
