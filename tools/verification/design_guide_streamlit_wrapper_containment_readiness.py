"""Readiness proof for a narrow Streamlit wrapper containment experiment.

Proof-only. The current smoothness evidence points at Streamlit's own
stMainBlockContainer width hydration. This verifier decides whether a narrow
CSS experiment is justified, and blocks broad/global retries that previous
impact proof already found non-material.

It does not change product behaviour, layout, publication, CTA/apply semantics,
visible wording, widget keys, family runtimes, or engineering behaviour.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "app.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, flags=re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _source_markers() -> dict[str, Any]:
    source = APP_PY.read_text(encoding="utf-8", errors="replace")
    sharp_css = _function_block(source, "_apply_sharp_embed_css")
    return {
        "sharp_css_exists": bool(sharp_css),
        "page_config_wide": 'layout="wide"' in source,
        "sharp_css_called_before_inputs_import": source.find("_apply_sharp_embed_css()") < source.find("import inputs_page"),
        "scoped_main_block_rule_present": ".stApp [data-testid=\"stMainBlockContainer\"]" in sharp_css,
        "scoped_block_container_rule_present": ".stApp .block-container" in sharp_css,
        "max_width_1180_present": "max-width: 1180px" in sharp_css,
        "unscoped_main_block_guard_present": bool(
            re.search(r"(^|\n)\s*\[data-testid=\"stMainBlockContainer\"\]\s*,", sharp_css)
        ),
        "wrapper_containment_guard_present": "dg-wrapper-containment-guard" in sharp_css
        or "contain: inline-size" in sharp_css
        or "contain: layout" in sharp_css,
        "broad_root_transform_or_zoom_absent": "transform:" not in sharp_css and "zoom:" not in sharp_css,
    }


def _capture() -> dict[str, Any]:
    wrapper = _latest("design_guide_streamlit_wrapper_shift_detail")
    root_impact = _latest("design_guide_streamlit_root_width_guard_impact")
    owner_audit = _latest("design_guide_first_paint_layout_hotspot_owner")
    wrapper_cls = dict((wrapper.get("payload") or {}).get("classification") or {})
    impact_payload = dict(root_impact.get("payload") or {})
    owner_summary = dict((owner_audit.get("payload") or {}).get("summary") or {})
    return {
        "source_markers": _source_markers(),
        "latest_wrapper_detail": {
            "path": wrapper.get("path"),
            "status": wrapper.get("status"),
            "classification": wrapper_cls,
        },
        "latest_root_width_guard_impact": {
            "path": root_impact.get("path"),
            "status": root_impact.get("status"),
            "decision": impact_payload.get("decision"),
            "guard_kept": impact_payload.get("guard_kept"),
            "improvement": impact_payload.get("improvement"),
        },
        "latest_first_paint_owner": {
            "path": owner_audit.get("path"),
            "status": owner_audit.get("status"),
            "summary": owner_summary,
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    markers = dict(capture.get("source_markers") or {})
    wrapper = dict((capture.get("latest_wrapper_detail") or {}).get("classification") or {})
    impact = dict(capture.get("latest_root_width_guard_impact") or {})
    top_owner = str(wrapper.get("top_owner") or "")
    owner_value = dict(wrapper.get("owner_value") or {})
    wrapper_value = float(owner_value.get("streamlit_layout_wrapper") or 0.0)
    layout_total = float(wrapper.get("layout_shift_total") or 0.0)
    root_impact_decision = str(impact.get("decision") or "")
    broad_guard_not_material = root_impact_decision == "ROOT_WIDTH_GUARD_NOT_MATERIAL"

    blockers: list[str] = []
    if top_owner != "streamlit_layout_wrapper":
        blockers.append("wrapper_not_current_top_owner")
    if wrapper_value < 0.05 or layout_total < 0.08:
        blockers.append("wrapper_shift_not_material_enough")
    if not broad_guard_not_material:
        blockers.append("broad_root_width_guard_impact_missing_or_not_nonmaterial")
    if not markers.get("sharp_css_exists"):
        blockers.append("sharp_css_missing")
    if not markers.get("page_config_wide"):
        blockers.append("streamlit_wide_page_config_missing")
    if not markers.get("scoped_main_block_rule_present"):
        blockers.append("current_scoped_main_block_rule_missing")
    if not markers.get("broad_root_transform_or_zoom_absent"):
        blockers.append("unsafe_broad_transform_or_zoom_present")

    guard_present = bool(markers.get("wrapper_containment_guard_present"))
    if blockers:
        decision = "NOT_READY_FOR_WRAPPER_CONTAINMENT_EXPERIMENT"
        next_slice = "Do not change wrapper CSS; rerun/reproduce current evidence or resolve blockers first."
        ready = False
    elif guard_present:
        decision = "WRAPPER_CONTAINMENT_GUARD_ALREADY_PRESENT"
        next_slice = "Run source-node and broad smoothness impact snapshots to decide whether to keep it."
        ready = True
    else:
        decision = "READY_FOR_NARROW_WRAPPER_CONTAINMENT_EXPERIMENT"
        next_slice = (
            "Add a narrow CSS experiment scoped to stMain/stMainBlockContainer using layout containment or "
            "stable inline-size containment, then run source-node, first-paint owner, broad smoothness, and locks."
        )
        ready = True

    return {
        "status": "PASS",
        "decision": decision,
        "ready_for_narrow_wrapper_containment_experiment": ready,
        "wrapper_containment_guard_present": guard_present,
        "blockers": blockers,
        "product_behaviour_changed": False,
        "recommended_next_slice": next_slice,
        "allowed_experiment_scope": {
            "selectors": [
                ".stApp [data-testid=\"stMain\"]",
                ".stApp [data-testid=\"stMainBlockContainer\"]",
            ],
            "forbidden": [
                "global body transform or zoom",
                "changing app max width",
                "hiding Streamlit content",
                "panel-specific Design Brain placeholder changes",
                "CTA/apply/publication/render ownership changes",
            ],
        },
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_wrapper_containment_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_wrapper_containment_readiness_{stamp}.md"
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Streamlit Wrapper Containment Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{cls.get('decision')}`",
        f"- Ready: `{cls.get('ready_for_narrow_wrapper_containment_experiment')}`",
        f"- Guard present: `{cls.get('wrapper_containment_guard_present')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{item}`" for item in cls.get("blockers") or [])
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "```json",
            json.dumps(
                {
                    "latest_wrapper_detail": payload.get("latest_wrapper_detail"),
                    "latest_root_width_guard_impact": payload.get("latest_root_width_guard_impact"),
                    "source_markers": payload.get("source_markers"),
                    "allowed_experiment_scope": cls.get("allowed_experiment_scope"),
                },
                indent=2,
                sort_keys=True,
                default=str,
            )[:12000],
            "```",
            "",
            "## Recommendation",
            "",
            str(cls.get("recommended_next_slice") or ""),
            "",
        ]
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_streamlit_wrapper_containment_readiness.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_streamlit_wrapper_containment_readiness {payload['status']}")
    print(f"decision={classification['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
