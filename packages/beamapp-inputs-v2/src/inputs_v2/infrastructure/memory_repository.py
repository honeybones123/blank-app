"""Disposable repository for isolated V2 tests; no file or Runtime access."""

from __future__ import annotations

from inputs_v2.domain.beam_inputs import BeamInputs


class InMemoryBeamInputsRepository:
    def __init__(self) -> None:
        self._records: dict[str, BeamInputs] = {}

    def save(self, beam_id: str, inputs: BeamInputs) -> None:
        previous = self._records.get(str(beam_id))
        if previous is not None and previous.revision > inputs.revision:
            raise ValueError("Cannot overwrite a newer beam revision.")
        self._records[str(beam_id)] = inputs

    def load(self, beam_id: str) -> BeamInputs | None:
        return self._records.get(str(beam_id))

