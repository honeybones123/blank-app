from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.diagrams.builders import (  # noqa: E402
    build_inputs_diagram_view_model,
    stable_diagram_hash,
)
from inputs_page_modules.diagrams.models import InputsDiagramSourceSnapshot  # noqa: E402
from section_props.reo_layout import resolve_longitudinal_bars_from_layout  # noqa: E402
from section_props.shape_utils import normalise_shape_name  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _old_section_2d_request(source: InputsDiagramSourceSnapshot) -> dict[str, Any]:
    layout = dict(source.layout or {})
    return {
        "shape_name": str(layout.get("shape_name", "Rectangle (b x D)") or "Rectangle (b x D)"),
        "dims": dict(layout.get("dims") or {}),
        "reo": dict(layout.get("reo") or {}),
        "show_shear": True,
        "show_dn": False,
        "dn": 0.0,
        "tension_face": source.tension_face,
        "fallback_cover_side": float(source.fallback_cover_side),
        "fallback_cover_top": float(source.fallback_cover_top),
        "fallback_cover_bot": float(source.fallback_cover_bot),
    }


def _old_beam_3d_request(source: InputsDiagramSourceSnapshot) -> dict[str, Any]:
    layout = dict(source.layout or {})
    dims = dict(layout.get("dims") or {})
    reo = dict(layout.get("reo") or {})
    shared_state = dict(source.shared_state or {})
    shape_name = str(layout.get("shape_name", "Rectangle (b x D)") or "Rectangle (b x D)")
    shape_key = normalise_shape_name(shape_name)
    fallback_width = float(dims.get("b", source.fallback_width) or source.fallback_width)
    depth = float(dims.get("D", source.outline_depth or source.fallback_depth) or source.fallback_depth)
    span = float(source.span_length or 3000.0)
    cover_bot = float(reo.get("cover_bot", source.fallback_cover_bot) or source.fallback_cover_bot)
    cover_top = float(reo.get("cover_top", source.fallback_cover_top) or source.fallback_cover_top)
    cover_side = reo.get("cover_side")
    if cover_side is None:
        cover_side = min(cover_top, cover_bot)
    reo_layout = dict(layout.get("reo_layout") or {"bottom": [], "top": []})
    resolved_bars = None
    if shape_key in ("T", "I"):
        resolved_bars = tuple(
            dict(bar)
            for bar in resolve_longitudinal_bars_from_layout(
                shape_name=shape_name,
                dims=dims,
                reo_layout=reo_layout,
            )
        )
    return {
        "shape_name": shape_name,
        "shape_key": shape_key,
        "outline_points": tuple(tuple(point) for point in source.outline_points),
        "b_box": float(source.outline_width or fallback_width),
        "D": float(source.outline_depth or depth),
        "L_plot": float(max(min(span, 3000.0), 400.0)),
        "fallback_width": float(fallback_width),
        "cover_bot": float(cover_bot),
        "cover_top": float(cover_top),
        "cover_side": float(cover_side),
        "lig_d": float(shared_state.get("lig_d", reo.get("lig_d", 0.0)) or 0.0),
        "lig_legs": int(shared_state.get("lig_legs", reo.get("lig_legs", 0)) or 0),
        "s_lig": float(shared_state.get("s_lig", reo.get("s_lig", 200.0)) or 200.0),
        "reo_layout": reo_layout,
        "cage": dict(layout.get("cage") or {}),
        "resolved_bars": resolved_bars,
    }


def _strip_hash(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("display_hash", None)
    return out


def _scenario_sources() -> dict[str, InputsDiagramSourceSnapshot]:
    rect_layout = {
        "shape_name": "Rectangle (b x D)",
        "dims": {"b": 400.0, "D": 650.0},
        "reo": {"cover_bot": 40.0, "cover_top": 40.0, "cover_side": 35.0, "lig_d": 10.0, "lig_legs": 2, "s_lig": 200.0},
        "reo_layout": {
            "bottom": [{"x": [100.0, 200.0, 300.0], "y": 590.0, "db": 20.0}],
            "top": [{"x": [120.0, 280.0], "y": 60.0, "db": 16.0}],
        },
        "cage": {"x0": 35.0, "x1": 365.0, "y0": 45.0, "y1": 605.0},
    }
    t_layout = {
        "shape_name": "T-Section",
        "dims": {"bf": 800.0, "tf": 150.0, "bw": 300.0, "D": 700.0, "b": 300.0},
        "reo": {"cover_bot": 45.0, "cover_top": 40.0, "cover_side": 40.0, "lig_d": 10.0, "lig_legs": 2, "s_lig": 175.0},
        "reo_layout": {
            "bottom": [{"x": [290.0, 400.0, 510.0], "y": 640.0, "db": 20.0}],
            "top": [{"x": [260.0, 540.0], "y": 55.0, "db": 16.0}],
        },
        "cage": {"x0": 260.0, "x1": 540.0, "y0": 50.0, "y1": 650.0},
    }
    return {
        "rect_normal": InputsDiagramSourceSnapshot(
            layout=rect_layout,
            shared_state={"lig_d": 10.0, "lig_legs": 2, "s_lig": 200.0},
            tension_face="bottom",
            fallback_width=400.0,
            fallback_depth=650.0,
            span_length=2000.0,
            outline_points=((0.0, 0.0), (400.0, 0.0), (400.0, 650.0), (0.0, 650.0), (0.0, 0.0)),
            outline_width=400.0,
            outline_depth=650.0,
        ),
        "rect_missing_shear_links": InputsDiagramSourceSnapshot(
            layout=rect_layout,
            shared_state={"lig_d": 0.0, "lig_legs": 0, "s_lig": 200.0},
            tension_face=None,
            fallback_width=400.0,
            fallback_depth=650.0,
            span_length=0.0,
            outline_points=((0.0, 0.0), (400.0, 0.0), (400.0, 650.0), (0.0, 650.0), (0.0, 0.0)),
            outline_width=400.0,
            outline_depth=650.0,
        ),
        "t_section_resolved_bars": InputsDiagramSourceSnapshot(
            layout=t_layout,
            shared_state={"lig_d": 10.0, "lig_legs": 2, "s_lig": 175.0},
            tension_face="top",
            fallback_width=300.0,
            fallback_depth=700.0,
            span_length=3600.0,
            outline_points=((0.0, 0.0), (800.0, 0.0), (800.0, 150.0), (550.0, 150.0), (550.0, 700.0), (250.0, 700.0), (250.0, 150.0), (0.0, 150.0), (0.0, 0.0)),
            outline_width=800.0,
            outline_depth=700.0,
        ),
    }


def run_snapshot() -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    failures: list[str] = []
    for name, source in _scenario_sources().items():
        extracted = build_inputs_diagram_view_model(source)
        old_section = _old_section_2d_request(source)
        old_beam = _old_beam_3d_request(source)
        new_section = _strip_hash(asdict(extracted.section_2d))
        new_beam = _strip_hash(asdict(extracted.beam_3d))
        section_match = old_section == new_section
        beam_match = old_beam == new_beam
        if not section_match:
            failures.append(f"{name}:section_2d_request_mismatch")
        if not beam_match:
            failures.append(f"{name}:beam_3d_request_mismatch")
        scenarios.append(
            {
                "name": name,
                "section_match": section_match,
                "beam_match": beam_match,
                "section_hash": extracted.section_2d.display_hash,
                "beam_hash": extracted.beam_3d.display_hash,
                "display_hash": extracted.display_hash,
            }
        )
    status = "PASS" if not failures else "FAIL"
    return {
        "status": status,
        "decision": "READY_FOR_DIAGRAM_STATE_EXTRACTION" if status == "PASS" else "DIAGRAM_PARITY_GAPS_REMAIN",
        "scenarios": scenarios,
        "failures": failures,
        "product_behavior_changed": False,
        "live_cutover_performed": False,
        "old_page_path_remains_authoritative": True,
        "module_hash": stable_diagram_hash({"scenarios": scenarios}),
    }


def write_artifacts(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_diagram_view_model_parity_{ts}.json"
    md_path = AUDIT_DIR / f"inputs_diagram_view_model_parity_{ts}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Inputs Diagram View-Model Parity Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        f"Decision: `{snapshot['decision']}`",
        "",
        "## Scenarios",
    ]
    for scenario in snapshot["scenarios"]:
        lines.append(
            f"- `{scenario['name']}`: section=`{scenario['section_match']}`, beam3d=`{scenario['beam_match']}`"
        )
    lines.extend(["", "## Failures"])
    if snapshot["failures"]:
        lines.extend(f"- `{failure}`" for failure in snapshot["failures"])
    else:
        lines.append("- None")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = run_snapshot()
    json_path, md_path = write_artifacts(snapshot)
    print(f"inputs_diagram_view_model_parity_snapshot {snapshot['status']}")
    print(f"decision={snapshot['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

