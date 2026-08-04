from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFICATION_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _item_for(family_id: str, title: str, family: str) -> dict[str, Any]:
    return {
        "title_main": title,
        "title": title,
        "family": family,
        "check_key": family,
        "selected_family_id": family_id,
        "published_family_id": family_id,
        "cta_family_id": family_id,
        "guidance_intent": "optional_cleanup",
        "status": "PASS",
        "primary_action": "Run one-click auto design",
        "reasoning": f"Stale {family} fail text exists but current overview is authoritative.",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": family,
            "updates": {"proof_update": family},
            "preview_pass": True,
        },
    }


def _overview(*, bending: str = "PASS", bending_util: float = 0.92, shear: str = "PASS", shear_util: float = 0.93) -> dict[str, Any]:
    return {
        "statuses": {"bending": bending, "shear": shear},
        "utils": {"bending": bending_util, "shear": shear_util},
        "any_fail": bending == "FAIL" or shear == "FAIL",
    }


def _payload(
    *,
    family_id: str,
    title: str,
    family: str,
    current_overview: dict[str, Any],
    stale_failures: list[str],
    explicit_payload_active: bool,
) -> dict[str, Any]:
    payload = {
        "guidance_items": [_item_for(family_id, title, family)],
        "debug_trace": {
            "active_failures": list(stale_failures),
            "overview": {
                "statuses": {failure: "FAIL" for failure in stale_failures},
                "utils": {failure: 1.25 for failure in stale_failures},
                "any_fail": bool(stale_failures),
            },
            "current_overview": dict(current_overview),
            "family_status_current": {
                failure: {"status": "FAIL", "util": 1.25}
                for failure in stale_failures
            },
        },
        "overview": dict(current_overview),
        "family_status_current": {
            "bending": {
                "status": dict(current_overview.get("statuses") or {}).get("bending"),
                "util": dict(current_overview.get("utils") or {}).get("bending"),
            },
            "shear": {
                "status": dict(current_overview.get("statuses") or {}).get("shear"),
                "util": dict(current_overview.get("utils") or {}).get("shear"),
            },
        },
    }
    if explicit_payload_active:
        payload["active_failures"] = list(stale_failures)
    return payload


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    from design_brain.publication import enforce_underdesign_repair_publication_boundary

    result = enforce_underdesign_repair_publication_boundary(dict(case["payload"]))
    items = list(result.get("guidance_items") or [])
    primary = dict(items[0] if items else {})
    debug = dict(result.get("debug_trace") or {})
    forbidden_title = case["forbidden_title"]
    return {
        "family_id": case["family_id"],
        "name": case["name"],
        "title": primary.get("title_main") or primary.get("title"),
        "forbidden_title": forbidden_title,
        "active_failures_after_reconciliation": list(debug.get("active_failures") or []),
        "contract_boundary_passed": debug.get("contract_boundary_passed"),
        "blocked": bool(primary.get("contract_boundary_blocked_publication")),
        "passed": bool(
            (primary.get("title_main") or primary.get("title")) != forbidden_title
            and not bool(primary.get("contract_boundary_blocked_publication"))
            and not list(debug.get("active_failures") or [])
            and debug.get("contract_boundary_passed") is True
        ),
    }


def main() -> int:
    pass_overview = _overview()
    cases = [
        {
            "name": "bending_fail_governs_stale_explicit_and_debug_failure",
            "family_id": "BENDING_FAIL_GOVERNS",
            "forbidden_title": "Bending capacity is low",
            "payload": _payload(
                family_id="BENDING_FAIL_GOVERNS",
                title="Bending cleanup - further reduction reaches target range",
                family="bending",
                current_overview=pass_overview,
                stale_failures=["bending"],
                explicit_payload_active=True,
            ),
        },
        {
            "name": "shear_fail_governs_stale_explicit_and_debug_failure",
            "family_id": "SHEAR_FAIL_GOVERNS",
            "forbidden_title": "Shear capacity is low",
            "payload": _payload(
                family_id="SHEAR_FAIL_GOVERNS",
                title="Shear cleanup - one-click reduction",
                family="shear",
                current_overview=pass_overview,
                stale_failures=["shear"],
                explicit_payload_active=True,
            ),
        },
        {
            "name": "combined_bending_shear_fail_stale_explicit_and_debug_failure",
            "family_id": "COMBINED_BENDING_SHEAR_FAIL",
            "forbidden_title": "Bending and shear capacity are low",
            "payload": _payload(
                family_id="COMBINED_BENDING_SHEAR_FAIL",
                title="Combined cleanup - best safe result",
                family="combined",
                current_overview=pass_overview,
                stale_failures=["bending", "shear"],
                explicit_payload_active=True,
            ),
        },
        {
            "name": "bending_fail_governs_stale_debug_only_failure",
            "family_id": "BENDING_FAIL_GOVERNS",
            "forbidden_title": "Bending capacity is low",
            "payload": _payload(
                family_id="BENDING_FAIL_GOVERNS",
                title="Bending cleanup - further reduction reaches target range",
                family="bending",
                current_overview=pass_overview,
                stale_failures=["bending"],
                explicit_payload_active=False,
            ),
        },
    ]
    results = [_run_case(case) for case in cases]
    status = "PASS" if all(row["passed"] for row in results) else "FAIL"
    payload = {
        "status": status,
        "families_covered": sorted({row["family_id"] for row in results}),
        "results": results,
        "product_behaviour_intent": (
            "Family publication must use current overview truth. Stale active-failure evidence "
            "from explicit payload, debug, old overview, or old family-status rows must not "
            "publish an underdesign advisory card after the family/result is no longer failing."
        ),
    }

    stamp = _utc_stamp()
    VERIFICATION_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    verification_path = (
        VERIFICATION_DIR
        / f"design_guide_family_publication_stale_failure_regression_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_family_publication_stale_failure_regression_{stamp}.md"
    )
    verification_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(
        "\n".join(
            [
                "# Design Guide family publication stale-failure regression",
                "",
                f"Result: **{status}**",
                "",
                "Family cases:",
                *[
                    f"- {row['name']}: {'PASS' if row['passed'] else 'FAIL'} "
                    f"(title={row['title']!r}, active={row['active_failures_after_reconciliation']})"
                    for row in results
                ],
                "",
                "This is family-level coverage for stale active-failure publication bugs.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design guide family publication stale-failure regression {status}")
    print(f"verification: {verification_path}")
    print(f"audit: {audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
