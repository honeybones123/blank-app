from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"
UI_DIR = ROOT / "ui"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status_from_payload(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if isinstance(value, str):
            upper = value.upper()
            if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
                return "PASS"
            if "PARTIAL" in upper:
                return "PARTIAL"
            if "FAIL" in upper or "BLOCKED" in upper:
                return "FAIL"
            return upper
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest_payload(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": "MISSING", "mtime": 0.0}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "path": str(path),
            "payload": {},
            "status": "UNREADABLE",
            "mtime": path.stat().st_mtime,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "path": str(path),
        "payload": payload,
        "status": _status_from_payload(payload),
        "mtime": path.stat().st_mtime,
    }


def _source_checks() -> dict[str, bool]:
    inputs_source = _read(INPUTS_PAGE)
    page_source = _read(DESIGN_GUIDE_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    ui_sources = "\n".join(_read(path) for path in sorted(UI_DIR.glob("*.py")))
    return {
        "design_guide_page_render_final_panel_exists": "def render_final_panel(" in page_source,
        "final_publication_display_authority_live": '_FINAL_PUBLICATION_DISPLAY_AUTHORITY = "FinalDesignGuidePublication.display"' in inputs_source,
        "final_publication_cta_authority_live": '_FINAL_PUBLICATION_CTA_AUTHORITY = "FinalDesignGuidePublication.cta"' in inputs_source,
        "card_view_model_builder_exists": "def build_design_guide_card_view_model(" in inputs_source,
        "render_model_bypass_uses_display_hash": "final_publication_display_hash" in inputs_source
        and "card_render_model_bypassed" in inputs_source,
        "renderer_has_no_final_publication_mutation": "FinalDesignGuidePublication(" not in page_source
        and "FinalDesignGuidePublication(" not in ui_sources,
        "renderer_has_no_family_runtime_calls": "run_bending_fail_governs_ladder_runtime" not in page_source
        and "run_shear_fail_governs_ladder_runtime" not in page_source
        and "run_bending_fail_governs_ladder_runtime" not in ui_sources
        and "run_shear_fail_governs_ladder_runtime" not in ui_sources,
        "final_publication_has_no_ui_or_streamlit_imports": "streamlit" not in final_source
        and "design_guide_page" not in final_source
        and "ui." not in final_source,
    }


def _visual_summary(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row.get("payload") or {})
    scenarios = payload.get("scenarios") or []
    first = scenarios[0] if isinstance(scenarios, list) and scenarios else {}
    failures: list[str] = []
    if isinstance(first, dict):
        checks = dict(first.get("checks") or {})
        failures.extend(str(item) for item in checks.get("hard_failures") or [])
        failures.extend(str(item) for item in first.get("hard_failures") or [])
    failures.extend(str(item) for item in payload.get("hard_failures") or [])
    return {
        "status": row.get("status"),
        "path": row.get("path"),
        "scenario_count": len(scenarios) if isinstance(scenarios, list) else 0,
        "recommendation": payload.get("recommendation"),
        "hard_failures": sorted(dict.fromkeys(failures)),
        "errors": payload.get("errors") or [],
    }


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    latest_visual = dict(snapshot.get("latest_visual_consistency") or {})
    latest_family_visual = dict(snapshot.get("latest_family_visual_consistency") or {})
    lines = [
        "# Design Brain Shared Renderer / View Model Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This lock covers the render bridge and view-model/render-only layer. It checks that renderer/view-model code passes through FinalDesignGuidePublication display/CTA truth and that browser-visible output agrees with publication truth.",
        "",
        "## Ownership",
        "",
        "- Design Brain/families own engineering truth.",
        "- FinalDesignGuidePublication owns display and CTA truth.",
        "- Render bridge and UI render view models only; they must not reinterpret family outcome, CTA, blocker, or publication identity.",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in snapshot.get("source_checks", {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Latest Evidence",
            "",
            f"- render bridge lock: `{snapshot['latest_render_bridge_lock'].get('status')}` at `{snapshot['latest_render_bridge_lock'].get('path')}`",
            f"- browser visual consistency: `{latest_visual.get('status')}` at `{latest_visual.get('path')}`",
            f"- family browser visual consistency: `{latest_family_visual.get('status')}` at `{latest_family_visual.get('path')}`",
            "",
            "## Blockers",
            "",
        ]
    )
    if snapshot.get("blockers"):
        lines.extend(f"- {blocker}" for blocker in snapshot["blockers"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            "Refresh browser/live visual consistency after the current shared locks. The proof must show visible Design Guide card, CTA/action state, summary-card relationship, no stale/fallback shell marker, no raw status leak, and publication hash availability.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    render_bridge = _latest_payload("design_guide_render_bridge_lock")
    visual = _latest_payload("design_guide_browser_live_visual_consistency")
    family_visual = _latest_payload("design_guide_family_browser_live_visual_consistency")
    source_checks = _source_checks()

    blockers: list[str] = []
    for key, passed in source_checks.items():
        if not passed:
            blockers.append(f"source check failed: {key}")
    if render_bridge.get("status") != "PASS":
        blockers.append("render bridge lock is not PASS")
    if visual.get("status") != "PASS":
        blockers.append("latest browser/live visual consistency proof is not PASS")
    if family_visual.get("status") not in {"PASS", "MISSING"}:
        blockers.append("latest family browser/live visual consistency proof is not PASS")

    render_mtime = float(render_bridge.get("mtime") or 0.0)
    visual_mtime = float(visual.get("mtime") or 0.0)
    family_visual_mtime = float(family_visual.get("mtime") or 0.0)
    if visual_mtime and render_mtime and visual_mtime < render_mtime:
        blockers.append("browser/live visual consistency proof is older than the latest render bridge lock")
    if family_visual_mtime and render_mtime and family_visual_mtime < render_mtime:
        blockers.append("family browser/live visual consistency proof is older than the latest render bridge lock")

    status = "LOCKED" if not blockers else "DEFERRED_WITH_BLOCKER"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"design_brain_shared_renderer_view_model_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_shared_renderer_view_model_lock_{stamp}.md"
    snapshot = {
        "schema": "design_brain_shared_renderer_view_model_lock.v1",
        "status": status,
        "lock_status": status,
        "component": "renderer/view models",
        "source_checks": source_checks,
        "latest_render_bridge_lock": {
            "status": render_bridge.get("status"),
            "path": render_bridge.get("path"),
        },
        "latest_visual_consistency": _visual_summary(visual),
        "latest_family_visual_consistency": _visual_summary(family_visual),
        "blockers": list(dict.fromkeys(blockers)),
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"design_brain_shared_renderer_view_model_lock {status}")
    print(f"json={artifact_path}")
    print(f"report={report_path}")
    if blockers:
        print("blockers=" + "; ".join(snapshot["blockers"]))
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
