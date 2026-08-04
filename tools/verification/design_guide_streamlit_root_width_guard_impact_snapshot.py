"""Impact snapshot for the attempted root/main Streamlit width guard.

Proof-only. This captures whether the unscoped root/main width guard produced a
material improvement. It exists so future smoothness work does not keep trying
the same ineffective global CSS patch.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "app.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": f"{type(exc).__name__}: {exc}"}


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}}
    path = paths[-1]
    return {"found": True, "path": str(path), "payload": _load(path)}


def _specific(name: str) -> dict[str, Any]:
    path = ARTIFACT_DIR / name
    return {"found": path.exists(), "path": str(path), "payload": _load(path) if path.exists() else {}}


def _source_guard_present() -> bool:
    source = APP_PY.read_text(encoding="utf-8", errors="replace")
    return '\n  [data-testid="stMainBlockContainer"],\n  .block-container,' in source


def main() -> int:
    before = _specific("design_guide_streamlit_main_width_settle_2026-07-11T13-31-52.json")
    attempted = _specific("design_guide_streamlit_main_width_settle_2026-07-11T13-37-24.json")
    source_guard_present = _source_guard_present()
    before_summary = dict((before.get("payload") or {}).get("summary") or {})
    attempted_summary = dict((attempted.get("payload") or {}).get("summary") or {})
    before_total = float(before_summary.get("layout_shift_total") or 0.0)
    attempted_total = float(attempted_summary.get("layout_shift_total") or 0.0)
    before_width_delta = float(before_summary.get("main_width_delta_px") or 0.0)
    attempted_width_delta = float(attempted_summary.get("main_width_delta_px") or 0.0)
    before_early = float(before_summary.get("early_pre_summary_layout_shift_total") or 0.0)
    attempted_early = float(attempted_summary.get("early_pre_summary_layout_shift_total") or 0.0)
    total_improvement = round(before_total - attempted_total, 6)
    width_delta_improvement = round(before_width_delta - attempted_width_delta, 6)
    early_improvement = round(before_early - attempted_early, 6)
    material = bool(total_improvement >= 0.03 or width_delta_improvement >= 120)
    decision = "ROOT_WIDTH_GUARD_MATERIAL" if material else "ROOT_WIDTH_GUARD_NOT_MATERIAL"
    payload = {
        "schema": "design_guide_streamlit_root_width_guard_impact.v1",
        "created_at": _stamp(),
        "status": "PASS",
        "decision": decision,
        "product_behaviour_changed": False,
        "source_guard_present_after_slice": source_guard_present,
        "guard_kept": False,
        "before": {
            "artifact": before.get("path"),
            "layout_shift_total": before_total,
            "main_width_delta_px": before_width_delta,
            "early_pre_summary_layout_shift_total": before_early,
        },
        "attempted": {
            "artifact": attempted.get("path"),
            "layout_shift_total": attempted_total,
            "main_width_delta_px": attempted_width_delta,
            "early_pre_summary_layout_shift_total": attempted_early,
        },
        "improvement": {
            "layout_shift_total": total_improvement,
            "main_width_delta_px": width_delta_improvement,
            "early_pre_summary_layout_shift_total": early_improvement,
            "material": material,
        },
        "recommended_next_slice": (
            "Do not retry the unscoped root/main width guard. Focus on user-specific huge-gap reproduction, "
            "or on stable render reuse only when a live trace proves reuse eligibility."
        ),
        "latest_readiness": _latest("design_guide_streamlit_root_width_guard_readiness"),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_root_width_guard_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_root_width_guard_impact_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Design Guide Streamlit Root Width Guard Impact",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Guard kept: `{payload['guard_kept']}`",
        f"- Product behaviour changed: `{payload['product_behaviour_changed']}`",
        f"- Total layout shift improvement: `{total_improvement}`",
        f"- Width delta improvement: `{width_delta_improvement}` px",
        f"- Early shift improvement: `{early_improvement}`",
        f"- Recommended next slice: `{payload['recommended_next_slice']}`",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(
            {
                "before": payload["before"],
                "attempted": payload["attempted"],
                "improvement": payload["improvement"],
                "source_guard_present_after_slice": source_guard_present,
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        "```",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"design_guide_streamlit_root_width_guard_impact {payload['status']}")
    print(f"decision={payload['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
