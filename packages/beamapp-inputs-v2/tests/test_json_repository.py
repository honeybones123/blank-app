from pathlib import Path

import pytest

from inputs_v2.domain.beam_inputs import BeamInputs
from inputs_v2.infrastructure.json_repository import SCHEMA, JsonBeamInputsRepository
from inputs_v2.engineering.reinforcement_fit import evaluate_arrangement


def test_json_repository_round_trips_versioned_inputs(tmp_path: Path) -> None:
    repository = JsonBeamInputsRepository(tmp_path / "snapshots")
    inputs = BeamInputs(revision=3)
    repository.save("beam-a", inputs)
    restored = repository.load("beam-a")
    assert restored == inputs
    assert '"schema": "' + SCHEMA + '"' in (tmp_path / "snapshots" / "beam-a.json").read_text(encoding="utf-8")


def test_json_repository_rejects_older_revision(tmp_path: Path) -> None:
    repository = JsonBeamInputsRepository(tmp_path)
    repository.save("beam-a", BeamInputs(revision=4))
    with pytest.raises(ValueError, match="newer"):
        repository.save("beam-a", BeamInputs(revision=2))


def test_json_repository_rejects_tampered_hash(tmp_path: Path) -> None:
    repository = JsonBeamInputsRepository(tmp_path)
    repository.save("beam-a", BeamInputs())
    path = tmp_path / "beam-a.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"content_hash":', '"content_hash": "tampered", "old_hash":'), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        repository.load("beam-a")

def test_json_repository_round_trips_exact_layered_arrangement(tmp_path: Path) -> None:
    repository = JsonBeamInputsRepository(tmp_path)
    inputs = BeamInputs(depth_mm=500.0)
    arrangement = evaluate_arrangement(inputs, (3, 3)).arrangement
    layered = BeamInputs(depth_mm=500.0, bottom_arrangement=arrangement)
    repository.save("layered", layered)
    restored = repository.load("layered")
    assert restored is not None
    assert restored.bottom_arrangement == arrangement
