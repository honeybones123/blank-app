"""Pure session store for Design Guide reference and history keys."""

from __future__ import annotations

from typing import Any, MutableMapping


class GuidanceUiStateStore:
    def __init__(self, session_state: MutableMapping[str, Any]) -> None:
        self._state = session_state

    def reference_beam_id(self) -> str:
        return str(self._state.get("_design_guide_ref_beam_id") or "")

    def active_beam_id(self) -> str:
        return str(self._state.get("active_beam_id") or "")

    def set_beam_reference(self, beam_id: str, *, depth: float, width: float) -> None:
        self._state["_design_guide_ref_beam_id"] = beam_id
        self._state["design_guide_reference_D"] = depth
        self._state["design_guide_reference_b"] = width

    def session_anchor_depth(self) -> Any:
        return self._state.get("design_guide_session_anchor_D")

    def set_session_anchor_depth(self, depth: float) -> None:
        self._state["design_guide_session_anchor_D"] = depth

    def history_anchor(self) -> Any:
        return self._state.get("_design_guide_history_anchor")

    def apply_history_reset(self, *, reset_history: bool, current_anchor: Any) -> None:
        if reset_history:
            self._state["_design_guide_step_history"] = []
            self._state["_design_guide_first_target_band_step"] = None
        self._state["_design_guide_history_anchor"] = current_anchor


__all__ = ["GuidanceUiStateStore"]
