"""Versioned, path-scoped persistence for the isolated V2 lab."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from inputs_v2.domain.beam_inputs import (
    ActionInputs,
    BeamInputs,
    LongitudinalReinforcement,
    LayoutMode,
    MaterialInputs,
    ServiceabilityInputs,
    ShearReinforcement,
    SupportInputs,
    TimeDependentInputs,
    VoidInputs,
    DeflectionInputs,
)
from inputs_v2.domain.reinforcement_arrangement import ReinforcementArrangement, ReinforcementRow


SCHEMA = "inputs_v2.beam_inputs.v1"


class JsonBeamInputsRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, beam_id: str) -> Path:
        safe_id = "".join(char for char in str(beam_id) if char.isalnum() or char in "-_")
        if not safe_id:
            raise ValueError("beam_id must contain at least one safe character")
        path = (self.root / f"{safe_id}.json").resolve()
        if self.root not in path.parents:
            raise ValueError("beam path escaped repository root")
        return path

    def save(self, beam_id: str, inputs: BeamInputs) -> None:
        inputs.validated()
        path = self._path(beam_id)
        current = self.load(beam_id)
        if current is not None and current.revision > inputs.revision:
            raise ValueError("Cannot overwrite a newer beam revision.")
        payload = {
            "schema": SCHEMA,
            "beam_id": str(beam_id),
            "revision": inputs.revision,
            "content_hash": inputs.content_hash,
            "inputs": asdict(inputs),
        }
        payload["inputs"]["bottom"]["mode"] = inputs.bottom.mode.value
        payload["inputs"]["top"]["mode"] = inputs.top.mode.value
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def load(self, beam_id: str) -> BeamInputs | None:
        path = self._path(beam_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != SCHEMA:
            raise ValueError("Unsupported Inputs V2 persistence schema")
        raw = dict(payload.get("inputs") or {})
        bottom_raw = dict(raw.pop("bottom") or {})
        top_raw = dict(raw.pop("top") or {})
        shear_raw = dict(raw.pop("shear") or {})
        materials_raw = dict(raw.pop("materials") or {})
        actions_raw = dict(raw.pop("actions") or {})
        supports_raw = dict(raw.pop("supports") or {})
        time_dependent_raw = dict(raw.pop("time_dependent") or {})
        voids_raw = dict(raw.pop("voids") or {})
        deflection_raw = dict(raw.pop("deflection") or {})
        serviceability_raw = dict(raw.pop("serviceability") or {})
        arrangement_raw = raw.pop("bottom_arrangement", None)
        arrangement = None
        if arrangement_raw:
            arrangement = ReinforcementArrangement(
                total_bar_count=int(arrangement_raw["total_bar_count"]),
                bar_diameter_mm=float(arrangement_raw["bar_diameter_mm"]),
                rows=tuple(ReinforcementRow(**row) for row in arrangement_raw.get("rows", ())),
                layer_count=int(arrangement_raw["layer_count"]),
                clear_row_gap_mm=float(arrangement_raw["clear_row_gap_mm"]),
                reinforcement_centroid_mm=float(arrangement_raw["reinforcement_centroid_mm"]),
                effective_depth_mm=float(arrangement_raw["effective_depth_mm"]),
            )
        restored = BeamInputs(
            **raw,
            bottom_arrangement=arrangement,
            bottom=LongitudinalReinforcement(mode=LayoutMode(bottom_raw.pop("mode")), **bottom_raw),
            top=LongitudinalReinforcement(mode=LayoutMode(top_raw.pop("mode")), **top_raw),
            shear=ShearReinforcement(**shear_raw),
            materials=MaterialInputs(**materials_raw),
            actions=ActionInputs(**actions_raw),
            supports=SupportInputs(**supports_raw),
            time_dependent=TimeDependentInputs(**time_dependent_raw),
            voids=VoidInputs(**voids_raw),
            deflection=DeflectionInputs(**deflection_raw),
            serviceability=ServiceabilityInputs(**serviceability_raw),
        ).validated()
        if payload.get("content_hash") != restored.content_hash:
            raise ValueError("Persisted content hash does not match Inputs V2 payload")
        return restored
