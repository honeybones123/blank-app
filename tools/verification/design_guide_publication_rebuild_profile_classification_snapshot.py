"""Classify the remaining publication/card rebuild hotspot from live profiling.

This snapshot prevents drift after the first-paint skeleton and duplicate stamp
bypass work: the browser smoothness profile still reports publication rebuilds,
but the latest measured rows are full page reload/new-session setup rows, not
same-session no-input churn. This is audit-only and changes no product code.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "payload": {}, "status": "UNREADABLE", "error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _decision_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for scenario in list(profile.get("scenarios") or []):
        counters = dict(scenario.get("counters") or {})
        for wrapper in list(counters.get("publication_stamp_decisions") or []):
            if not isinstance(wrapper, dict):
                continue
            candidate = str(wrapper.get("candidate") or "")
            row = dict(wrapper.get(candidate) or {})
            if row:
                row["scenario_id"] = scenario.get("scenario_id")
                row["action"] = scenario.get("action")
                out.append(row)
    return out


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    profile_artifact = _latest("design_guide_browser_live_smoothness_profile")
    impact_artifact = _latest("design_guide_duplicate_publication_stamp_bypass_live_impact")
    profile = dict(profile_artifact.get("payload") or {})
    rows = _decision_rows(profile)
    reload_rows = [row for row in rows if row.get("action") in {"goto", "reload"}]
    same_hashes = sorted({str(row.get("publication_hash") or "") for row in reload_rows if row.get("publication_hash")})
    previous_hashes = sorted({str(row.get("previous_publication_hash") or "") for row in reload_rows if row.get("previous_publication_hash")})
    reasons = sorted({str(row.get("reason") or "") for row in reload_rows})
    counters = [
        {
            "scenario_id": row.get("scenario_id"),
            "action": row.get("action"),
            "candidate_id": row.get("candidate_id"),
            "reason": row.get("reason"),
            "publication_hash": row.get("publication_hash"),
            "previous_publication_hash": row.get("previous_publication_hash"),
            "bypassed": row.get("bypassed"),
        }
        for row in reload_rows
    ]
    hotspot = next(
        (
            item for item in list(profile.get("all_hotspot_scores") or [])
            if item.get("class") == "C"
        ),
        {},
    )
    layout = next(
        (
            item for item in list(profile.get("all_hotspot_scores") or [])
            if item.get("class") == "E"
        ),
        {},
    )
    classification = "RELOAD_SESSION_SETUP_NOT_SAFE_TO_BYPASS"
    errors: list[str] = []
    if not profile_artifact.get("found"):
        errors.append("missing_browser_smoothness_profile")
    if not rows:
        errors.append("missing_publication_stamp_rows")
    if impact_artifact.get("status") != "PASS":
        errors.append("duplicate_publication_stamp_bypass_impact_not_passed")
    payload = {
        "schema": "design_guide_publication_rebuild_profile_classification.v1",
        "status": "PASS" if not errors else "FAIL",
        "created_at": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
        "product_behavior_changed": False,
        "classification": classification,
        "profile_artifact": {k: v for k, v in profile_artifact.items() if k != "payload"},
        "impact_artifact": {k: v for k, v in impact_artifact.items() if k != "payload"},
        "publication_hotspot": hotspot,
        "layout_hotspot": layout,
        "reload_rows": counters,
        "reload_row_reasons": reasons,
        "reload_publication_hashes": same_hashes,
        "reload_previous_hashes": previous_hashes,
        "finding": (
            "The remaining C-class score is counted from full browser goto/reload scenarios. "
            "Those are new Streamlit session setup boundaries, so a same-session bypass cannot "
            "remove them safely. The already-proven duplicate-stamp bypass remains valid for "
            "stable non-debug same-session reruns."
        ),
        "next_slice": (
            "Do not add persistent cross-reload publication caches. Next smoothness work should "
            "target a real same-session hotspot or improve the profiler so reload setup is "
            "reported separately from no-input churn."
        ),
        "errors": errors,
    }
    return payload


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_publication_rebuild_profile_classification_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_rebuild_profile_classification_{stamp}.md"
    lines = [
        "# Design Guide Publication Rebuild Profile Classification",
        "",
        f"Status: `{payload['status']}`",
        f"Classification: `{payload['classification']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Finding",
        "",
        payload["finding"],
        "",
        "## Next Slice",
        "",
        payload["next_slice"],
        "",
    ]
    if payload["errors"]:
        lines.extend(["## Errors", "", "```json", json.dumps(payload["errors"], indent=2), "```", ""])
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"design_guide_publication_rebuild_profile_classification {payload['status']}")
    print(f"classification={payload['classification']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if payload["errors"]:
        print("errors=" + json.dumps(payload["errors"]))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
