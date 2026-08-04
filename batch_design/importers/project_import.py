"""Import beam rows or templates from another StructuralBase project payload."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from batch_design.importers.base import BatchImportResult
from batch_design.models import BatchBeamCase, BatchBeamSource, BatchBeamTemplate, BatchImportWarning


def _load_payload(project: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(project, dict):
        return copy.deepcopy(project)
    path = Path(project)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _section_label(params: dict[str, Any]) -> str | None:
    shape = str(params.get("sec_shape") or "RECT").upper()
    if shape == "T":
        return f"T bw {params.get('bw')} bf {params.get('bf')} D {params.get('D')}"
    if shape == "I":
        return f"I tw {params.get('tw')} bf {params.get('bf')} D {params.get('D')}"
    width = params.get("b")
    depth = params.get("D")
    if width is None and depth is None:
        return None
    return f"RECT {width} x {depth}"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def import_beams_from_project(
    project: dict[str, Any] | str | Path,
    *,
    as_templates: bool = False,
) -> BatchImportResult | list[BatchBeamTemplate]:
    """Import beams from a StructuralBase project without mutating the source."""

    payload = _load_payload(project)
    records = payload.get("beam_records") if isinstance(payload.get("beam_records"), dict) else {}
    order = list(payload.get("beam_order") or records.keys())
    warnings: list[BatchImportWarning] = []

    if as_templates:
        templates: list[BatchBeamTemplate] = []
        for beam_id in order:
            record = copy.deepcopy(records.get(beam_id) or {})
            params = dict(record.get("params") or {})
            summary = dict(record.get("summary") or {})
            capacities = {
                "mz_star": _float_or_none(summary.get("phi_Mu_cap")) or 0.0,
                "vz_star": _float_or_none(summary.get("phi_Vu_cap")) or 0.0,
            }
            templates.append(
                BatchBeamTemplate(
                    template_id=str(beam_id),
                    label=str(record.get("beam_label") or beam_id),
                    source=BatchBeamSource.STRUCTURALBASE_PROJECT,
                    section=_section_label(params),
                    length=_float_or_none(params.get("L")),
                    capacities=capacities,
                    parameters=params,
                    reinforcement={
                        "bottom": params.get("bottom_reo"),
                        "top": params.get("top_reo"),
                        "lig_d": params.get("lig_d"),
                        "lig_legs": params.get("lig_legs"),
                        "s_lig": params.get("s_lig"),
                    },
                    passing=str(summary.get("overall_status") or "").upper() == "PASS",
                    utilisation=_float_or_none(summary.get("Mu_utilisation") or summary.get("Vu_utilisation")),
                )
            )
        return templates

    rows: list[BatchBeamCase] = []
    for beam_id in order:
        record = copy.deepcopy(records.get(beam_id) or {})
        params = dict(record.get("params") or {})
        if not record:
            warnings.append(
                BatchImportWarning(
                    row_number=None,
                    member_id=str(beam_id),
                    severity="warning",
                    message="Beam ID was listed in project order but no record was found.",
                )
            )
            continue
        rows.append(
            BatchBeamCase(
                member_id=str(beam_id),
                source=BatchBeamSource.STRUCTURALBASE_PROJECT,
                existing_section=_section_label(params),
                length=_float_or_none(params.get("L")),
                n_star=_float_or_none(params.get("Nu_star")),
                vy_star=_float_or_none(params.get("Vy_star")),
                vz_star=_float_or_none(params.get("Vu_star")),
                mx_star=_float_or_none(params.get("Tu_star")),
                my_star=_float_or_none(params.get("My_star")),
                mz_star=_float_or_none(params.get("Mu_star")),
                confidence=1.0,
                governing_metadata={"source_beam_label": record.get("beam_label")},
            )
        )

    return BatchImportResult(
        rows=rows,
        warnings=warnings,
        metadata={"source_type": "structuralbase_project", "mutated_source": False},
    )
