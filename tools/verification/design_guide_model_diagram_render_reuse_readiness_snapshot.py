"""Proof-only readiness for model/diagram render reuse.

This verifier does not implement a cache or bypass. It proves whether the
Inputs page already has a stable model/diagram fingerprint and figure cache, and
whether the remaining live cost is Plotly component remount/render churn.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _function_block(source: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda item: item.stat().st_mtime)
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


def _capture() -> dict[str, Any]:
    source = _read(ROOT / "inputs_page.py")
    section_2d = _function_block(source, "_render_section_2d_diagram_block")
    section_3d = _function_block(source, "_render_3d_diagram_block")
    fingerprint = _function_block(source, "_inputs_geometry_fingerprint")
    model_keys_match = re.search(
        r"MODEL_RENDER_FINGERPRINT_KEYS\s*=\s*PRIMARY_GEOMETRY_KEYS\s*\|\s*\{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    model_keys_body = model_keys_match.group("body") if model_keys_match else ""
    baseline = _latest("design_guide_post_zero_authority_browser_live_smoothness_baseline")
    latest_profile = _latest("design_guide_browser_live_smoothness_profile")
    baseline_payload = dict(baseline.get("payload") or {})
    aggregate = dict(baseline_payload.get("aggregate") or {})
    stable_counts = dict(aggregate.get("stable_no_change_rebuild_counts") or {})
    latest_profile_payload = dict(latest_profile.get("payload") or {})
    hotspots = list(latest_profile_payload.get("top_hotspots") or [])
    top_hotspot = hotspots[0] if hotspots else {}
    return {
        "source_checks": {
            "fingerprint_helper_exists": bool(fingerprint),
            "fingerprint_uses_model_render_key_set": "MODEL_RENDER_FINGERPRINT_KEYS" in fingerprint,
            "fingerprint_includes_shear_keys": all(
                token in model_keys_body
                for token in (
                    '"lig_d"',
                    '"lig_legs"',
                    '"s_lig"',
                )
            ),
            "two_d_figure_cache_present": all(
                token in section_2d
                for token in (
                    '"_inputs_model_2d_geo_fp"',
                    '"_inputs_model_2d_fig"',
                    "cached_fp == geo_fp",
                )
            ),
            "three_d_figure_cache_present": all(
                token in section_3d
                for token in (
                    '"_inputs_model_3d_cache"',
                    "cached_fp == geo_fp",
                    "cached_fig is not None",
                )
            ),
            "two_d_still_renders_plotly_after_cache": "render_plotly_diagram(" in section_2d,
            "three_d_still_renders_plotly_after_cache": "render_plotly_diagram(" in section_3d,
            "render_reuse_guard_not_yet_present": "_inputs_model_diagram_render_reuse" not in source,
        },
        "latest_profile": {
            "status": latest_profile.get("status"),
            "path": latest_profile.get("path"),
            "top_hotspot": top_hotspot,
        },
        "baseline": {
            "status": baseline.get("status"),
            "path": baseline.get("path"),
            "recommended_first_target": aggregate.get("recommended_first_implementation_target"),
            "stable_no_change_rebuild_counts": stable_counts,
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    checks = dict(capture.get("source_checks") or {})
    baseline = dict(capture.get("baseline") or {})
    latest = dict(capture.get("latest_profile") or {})
    top = dict(latest.get("top_hotspot") or {})
    stable_model_rebuilds = int(
        (baseline.get("stable_no_change_rebuild_counts") or {}).get("model_diagram_rebuild_estimate") or 0
    )
    ready = bool(
        checks.get("fingerprint_helper_exists")
        and checks.get("fingerprint_includes_shear_keys")
        and checks.get("two_d_figure_cache_present")
        and checks.get("three_d_figure_cache_present")
        and checks.get("two_d_still_renders_plotly_after_cache")
        and checks.get("three_d_still_renders_plotly_after_cache")
        and baseline.get("status") == "PASS"
        and (
            stable_model_rebuilds > 0
            or "model/diagram panel render reuse" in str(baseline.get("recommended_first_target") or "")
            or str(top.get("class") or "") == "E"
        )
    )
    if ready:
        decision = "READY_FOR_TRACE_ONLY_RENDER_REUSE_GUARD"
        next_slice = (
            "Add trace-only model/diagram render reuse decisions keyed by _inputs_geometry_fingerprint; "
            "do not skip render yet."
        )
    else:
        decision = "NOT_READY"
        next_slice = "Refresh browser/live baseline and inspect diagram fingerprint/cache source before implementation."
    return {
        "status": "PASS" if ready else "PARTIAL",
        "decision": decision,
        "ready_for_live_bypass": False,
        "ready_for_trace_only_guard": ready,
        "stable_model_diagram_rebuild_estimate": stable_model_rebuilds,
        "next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    return "\n".join(
        [
            "# Design Guide Model/Diagram Render Reuse Readiness",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Decision: `{cls.get('decision')}`",
            f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
            f"- Ready for live bypass: `{cls.get('ready_for_live_bypass')}`",
            f"- Ready for trace-only guard: `{cls.get('ready_for_trace_only_guard')}`",
            f"- Stable model/diagram rebuild estimate: `{cls.get('stable_model_diagram_rebuild_estimate')}`",
            "",
            "## Source Checks",
            "",
            "```json",
            json.dumps(payload.get("source_checks") or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Latest Browser/Live Evidence",
            "",
            "```json",
            json.dumps(
                {
                    "baseline": payload.get("baseline"),
                    "latest_profile": payload.get("latest_profile"),
                },
                indent=2,
                sort_keys=True,
                default=str,
            )[:12000],
            "```",
            "",
            "## Next Slice",
            "",
            str(cls.get("next_slice") or ""),
            "",
        ]
    )


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    stamp = _stamp()
    payload = {
        "schema": "design_guide_model_diagram_render_reuse_readiness.v1",
        "timestamp": stamp,
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_model_diagram_render_reuse_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_model_diagram_render_reuse_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_model_diagram_render_reuse_readiness {payload['status']}")
    print(f"decision={classification['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
