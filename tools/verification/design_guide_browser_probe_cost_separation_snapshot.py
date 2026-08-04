from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROFILE_GLOB = "design_guide_browser_live_smoothness_profile_*.json"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")


def _load_latest_profile() -> tuple[Path, dict[str, Any]]:
    profiles = sorted(VERIFICATION_DIR.glob(PROFILE_GLOB), key=lambda path: path.stat().st_mtime)
    if not profiles:
        raise FileNotFoundError(f"No browser/live smoothness profile found under {VERIFICATION_DIR}")
    latest = profiles[-1]
    with latest.open("r", encoding="utf-8") as handle:
        return latest, json.load(handle)


def _hotspot_by_class(profile: dict[str, Any], class_id: str) -> dict[str, Any]:
    for row in profile.get("all_hotspot_scores") or profile.get("top_hotspots") or []:
        if str(row.get("class") or "") == class_id:
            return dict(row)
    return {}


def _next_non_probe_hotspot(profile: dict[str, Any]) -> dict[str, Any]:
    for row in profile.get("all_hotspot_scores") or profile.get("top_hotspots") or []:
        if str(row.get("class") or "") == "B":
            evidence = dict(row.get("evidence") or {})
            if evidence.get("browser_probe_dominated") and float(evidence.get("product_candidate_total_ms") or 0.0) <= 0.0:
                continue
        return dict(row)
    return {}


def _markdown(payload: dict[str, Any]) -> str:
    b = payload["candidate_hotspot"]
    evidence = dict(b.get("evidence") or {})
    next_target = payload.get("next_product_hotspot") or {}
    lines = [
        "# Design Guide Browser Probe Cost Separation Snapshot",
        "",
        f"- Status: `{payload['status']}`",
        f"- Source profile: `{payload['source_profile']}`",
        f"- Browser probe dominated: `{payload['browser_probe_dominated']}`",
        f"- Product candidate time: `{evidence.get('product_candidate_total_ms')}` ms",
        f"- Candidate cache misses: `{evidence.get('candidate_cache_misses')}`",
        f"- Treat candidate/search as product optimization target: `{payload['candidate_search_is_product_target']}`",
        "",
        "## Candidate/Search Evidence",
        "",
        "```json",
        json.dumps(b, indent=2, sort_keys=True),
        "```",
        "",
        "## Next Product Hotspot",
        "",
        "```json",
        json.dumps(next_target, indent=2, sort_keys=True),
        "```",
        "",
        "## Decision",
        "",
        payload["decision"],
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    source_path, profile = _load_latest_profile()
    candidate = _hotspot_by_class(profile, "B")
    evidence = dict(candidate.get("evidence") or {})
    browser_probe_dominated = bool(evidence.get("browser_probe_dominated"))
    product_candidate_ms = float(evidence.get("product_candidate_total_ms") or 0.0)
    candidate_misses = int(evidence.get("candidate_cache_misses") or 0)
    candidate_search_is_product_target = not (
        browser_probe_dominated and product_candidate_ms <= 0.0 and candidate_misses == 0
    )
    next_product_hotspot = _next_non_probe_hotspot(profile)

    status = "PASS" if candidate and next_product_hotspot else "FAIL"
    if candidate_search_is_product_target:
        decision = (
            "Candidate/search remains a product-path optimization target; use the focused candidate readiness "
            "snapshot before implementing cache or bypass work."
        )
    else:
        decision = (
            "Candidate/search cost is browser-probe overhead in the latest profile, not product candidate churn. "
            "Do not add another product candidate cache for this evidence; target the highest non-probe hotspot next."
        )

    payload = {
        "status": status,
        "source_profile": str(source_path.relative_to(ROOT)),
        "browser_probe_dominated": browser_probe_dominated,
        "candidate_search_is_product_target": candidate_search_is_product_target,
        "candidate_hotspot": candidate,
        "next_product_hotspot": next_product_hotspot,
        "decision": decision,
        "product_behaviour_changed": False,
    }

    stamp = _utc_stamp()
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = VERIFICATION_DIR / f"design_guide_browser_probe_cost_separation_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_browser_probe_cost_separation_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_browser_probe_cost_separation {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
