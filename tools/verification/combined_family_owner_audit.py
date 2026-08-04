"""Diagnostic audit for COMBINED_BENDING_SHEAR_FAIL family ownership."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ARTIFACT_DIR = REPO / "artifacts" / "verification"


def _write(report: dict[str, Any]) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"combined_family_owner_audit_{time.strftime('%Y-%m-%dT%H-%M-%S')}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    from design_brain.families.base import FamilyStrategyContext
    from design_brain.families.registry import GOVERNING_FAMILY_REGISTRY, family_strategy_for

    strategy = family_strategy_for("COMBINED_BENDING_SHEAR_FAIL")
    required_methods = (
        "classify",
        "generate_candidates",
        "rank_candidates",
        "build_evidence",
        "publish",
        "get_cta_rule",
        "route_existing_decision",
    )
    synthetic_primary = {
        "title": "Old visible item",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "family": "combined",
            "updates": {"bot1_n": 4, "lig_d": 10, "lig_legs": 2, "s_lig": 100},
            "preview_pass": True,
            "candidate_id": "synthetic_combined_repair",
        },
        "candidate_search_evidence": {
            "selected_candidate_id": "synthetic_combined_repair",
            "safe_repair_candidate_count": 1,
        },
    }
    context = FamilyStrategyContext(
        governing_state="COMBINED_BENDING_SHEAR_FAIL",
        primary=synthetic_primary,
        summary={
            "statuses": {"bending": "FAIL", "shear": "FAIL"},
            "utils": {"bending": 1.12, "shear": 1.4},
            "fail_keys": ["bending", "shear"],
        },
        evidence=dict(synthetic_primary["candidate_search_evidence"]),
        classifier={"governing_state": "COMBINED_BENDING_SHEAR_FAIL", "active_failures": ["bending", "shear"]},
    )
    decision = {
        "card": {"intent": "required_fix"},
        "presentation": {},
        "button_contract": dict(synthetic_primary["button_contract"]),
        "candidate_search_evidence": dict(synthetic_primary["candidate_search_evidence"]),
        "debug": {},
    }
    method_checks = {name: callable(getattr(strategy, name, None)) for name in required_methods}
    route = (
        strategy.route_existing_decision(
            context,
            decision=decision,
            primary_item=synthetic_primary,
            active_strength_failures={"bending", "shear"},
        )
        if strategy is not None and all(method_checks.values())
        else {}
    )
    routed_decision = dict(route.get("decision") or {})
    routed_primary = dict(route.get("primary_item") or {})
    routed_button = dict(routed_decision.get("button_contract") or {})
    failures = []
    if "COMBINED_BENDING_SHEAR_FAIL" not in GOVERNING_FAMILY_REGISTRY:
        failures.append("registry_missing_combined_family")
    if len(GOVERNING_FAMILY_REGISTRY) != 13:
        failures.append(f"registry_count_expected_13_got_{len(GOVERNING_FAMILY_REGISTRY)}")
    for name, ok in method_checks.items():
        if not ok:
            failures.append(f"missing_method:{name}")
    if not route.get("used"):
        failures.append("synthetic_route_not_used")
    if routed_button.get("family") != "combined":
        failures.append("routed_button_family_not_combined")
    if routed_primary.get("selected_family_id") != "COMBINED_BENDING_SHEAR_FAIL":
        failures.append("routed_primary_missing_selected_family_id")
    if "combined_bending_shear_fail" not in str(dict(route.get("diagnostics") or {}).get("owner") or "").lower():
        failures.append("route_owner_not_combined_family_module")

    report = {
        "schema": "combined_family_owner_audit.v1",
        "status": "PASS" if not failures else "FAIL",
        "family": "COMBINED_BENDING_SHEAR_FAIL",
        "registry_count": len(GOVERNING_FAMILY_REGISTRY),
        "method_checks": method_checks,
        "metadata": getattr(strategy, "metadata", None).__dict__ if strategy is not None else None,
        "route_used": bool(route.get("used")),
        "route_diagnostics": dict(route.get("diagnostics") or {}),
        "routed_button": routed_button,
        "routed_primary_family_ids": {
            "selected_family_id": routed_primary.get("selected_family_id"),
            "published_family_id": routed_primary.get("published_family_id"),
            "cta_family_id": routed_primary.get("cta_family_id"),
        },
        "failures": failures,
    }
    output = _write(report)
    print(f"{report['status']}: {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
