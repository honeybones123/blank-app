"""Beam-owned Load Analysis draft and result storage."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, MutableMapping


_DRAFTS_KEY = "_load_analysis_drafts_by_beam_v1"
_RESULTS_KEY = "_load_analysis_results_by_beam_v1"
_ACTIVE_BEAM_KEY = "_load_analysis_restored_beam_id_v1"
_ROUTE_TOKENS_KEY = "_load_analysis_route_restore_tokens_by_beam_v1"
_MODES_KEY = "_load_analysis_modes_by_beam_v1"


@dataclass(frozen=True)
class LoadAnalysisSnapshot:
    beam_id: str
    values: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.values))


def _freeze_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(copy.deepcopy(dict(values or {})))


def is_load_analysis_widget_key(key: str) -> bool:
    value = str(key or "")
    return value.startswith(("load_", "sfd_")) or value in {
        "design_loads_edit_toggle",
        "design_actions_source_selector",
        "design_section_x_slider",
        "design_section_x_input",
        "design_bmd_show_m_peak_marker",
    }


class LoadAnalysisStateStore:
    """Retain Load Analysis state outside Streamlit's transient widget keys."""

    def __init__(self, session_state: MutableMapping[str, Any]):
        self._state = session_state

    def _beam_id(self, beam_id: str | None = None) -> str:
        return str(beam_id or self._state.get("active_beam_id") or "default")

    def current(self, beam_id: str | None = None) -> LoadAnalysisSnapshot:
        resolved = self._beam_id(beam_id)
        drafts = self._state.get(_DRAFTS_KEY)
        payload = drafts.get(resolved, {}) if isinstance(drafts, dict) else {}
        return LoadAnalysisSnapshot(resolved, _freeze_mapping(payload))

    def restore_widgets(
        self,
        beam_id: str | None = None,
        *,
        route_token: object | None = None,
    ) -> LoadAnalysisSnapshot:
        """Restore the beam-owned draft once on each Load Analysis route entry.

        The application router still hydrates legacy shared widget keys before
        the page fragment runs.  A new route token therefore authorises this
        store to replace those transient values with the persisted Load
        Analysis draft.  Fragment reruns retain the same token and must not
        overwrite a user's in-progress edit.
        """

        snapshot = self.current(beam_id)
        modes = dict(self._state.get(_MODES_KEY) or {})
        if self._beam_id(beam_id) in modes:
            snapshot_values = snapshot.to_dict()
            snapshot_values["design_loads_edit_toggle"] = bool(modes[self._beam_id(beam_id)])
            snapshot = LoadAnalysisSnapshot(snapshot.beam_id, _freeze_mapping(snapshot_values))
        switched = str(self._state.get(_ACTIVE_BEAM_KEY) or "") != snapshot.beam_id
        tokens = copy.deepcopy(dict(self._state.get(_ROUTE_TOKENS_KEY) or {}))
        resolved_token = None if route_token is None else str(route_token)
        new_route_entry = bool(
            resolved_token is not None
            and tokens.get(snapshot.beam_id) != resolved_token
        )
        for key, value in snapshot.values.items():
            if switched or new_route_entry or key not in self._state:
                self._state[key] = copy.deepcopy(value)
        self._state[_ACTIVE_BEAM_KEY] = snapshot.beam_id
        if resolved_token is not None:
            tokens[snapshot.beam_id] = resolved_token
            self._state[_ROUTE_TOKENS_KEY] = tokens
        return snapshot

    def capture_widgets(self, beam_id: str | None = None) -> LoadAnalysisSnapshot:
        resolved = self._beam_id(beam_id)
        values = {
            str(key): copy.deepcopy(value)
            for key, value in self._state.items()
            if is_load_analysis_widget_key(str(key))
        }
        drafts = copy.deepcopy(dict(self._state.get(_DRAFTS_KEY) or {}))
        drafts[resolved] = values
        self._state[_DRAFTS_KEY] = drafts
        modes = copy.deepcopy(dict(self._state.get(_MODES_KEY) or {}))
        modes[resolved] = bool(values.get("design_loads_edit_toggle", self._state.get("design_loads_edit_toggle", False)))
        self._state[_MODES_KEY] = modes
        self._state[_ACTIVE_BEAM_KEY] = resolved
        return LoadAnalysisSnapshot(resolved, _freeze_mapping(values))

    def publish_results(self, beam_id: str | None = None, **values: Any) -> None:
        resolved = self._beam_id(beam_id)
        results = copy.deepcopy(dict(self._state.get(_RESULTS_KEY) or {}))
        current = copy.deepcopy(dict(results.get(resolved) or {}))
        current.update(copy.deepcopy(values))
        results[resolved] = current
        self._state[_RESULTS_KEY] = results

    def results(self, beam_id: str | None = None) -> dict[str, Any]:
        resolved = self._beam_id(beam_id)
        results = self._state.get(_RESULTS_KEY)
        return copy.deepcopy(
            dict(results.get(resolved) or {}) if isinstance(results, dict) else {}
        )


__all__ = ["LoadAnalysisSnapshot", "LoadAnalysisStateStore", "is_load_analysis_widget_key"]
