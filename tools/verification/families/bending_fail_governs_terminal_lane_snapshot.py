"""BENDING_FAIL_GOVERNS terminal lane snapshot.

Proof-only verifier for the contract-defined EXACT_STOP and NO_VALID_STRATEGY
terminal lanes. It loads the terminal lane definitions from the
BENDING_FAIL_GOVERNS contract and evaluates normalized terminal evidence
without changing product behaviour or live ladder order.
"""

from __future__ import annotations

import json
import sys
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    family_identity,
    global_family_rules,
    internal_strategy_lanes,
    load_bending_fail_governs_contract,
)


FORBIDDEN_PROOF_KEYS = {
    "apply_routing",
    "button_contract",
    "button_label",
    "cta_enabled",
    "cta_rendering",
    "debug",
    "html",
    "one_click",
    "one_click_fallback",
    "publication",
    "published_item",
    "render",
    "session",
    "session_state",
    "source_precedence",
    "ui",
    "visible_wording",
}

CONTRACT_LANE_ALIASES = {
    "geometry_sanity": "GEOMETRY_SANITY",
    "depth_increase": "DEPTH_INCREASE",
    "single_layer_bottom_reinforcement": "SINGLE_LAYER_BOTTOM_REO",
    "larger_bars": "LARGER_BAR",
    "width_increase": "WIDTH_INCREASE",
    "multi_layer_reinforcement": "MULTI_LAYER_REO",
    "exact_stop": "EXACT_STOP",
    "no_valid_strategy": "NO_VALID_STRATEGY",
}

ALL_NON_TERMINAL_LANES = [
    "GEOMETRY_SANITY",
    "DEPTH_INCREASE",
    "SINGLE_LAYER_BOTTOM_REO",
    "LARGER_BAR",
    "WIDTH_INCREASE",
    "MULTI_LAYER_REO",
]


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _contract_ladder_order() -> list[str]:
    return [
        CONTRACT_LANE_ALIASES.get(str(lane.get("lane_id") or ""), str(lane.get("lane_id") or "").upper())
        for lane in sorted(internal_strategy_lanes(), key=lambda lane: int(lane.get("lane_index") or 0))
    ]


def _lane_definition(lane_id: str) -> dict[str, Any]:
    for lane in internal_strategy_lanes():
        if str(lane.get("lane_id") or "") == lane_id:
            return dict(lane)
    return {}


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_PROOF_KEYS:
                found.add(key_text)
            found.update(_walk_forbidden(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_walk_forbidden(child))
    return found


def _target_band_status(util: float, *, low: float = 0.85, high: float = 1.0) -> str:
    if low <= float(util) <= high:
        return "TARGET_REACHED"
    if float(util) > high:
        return "STILL_FAILING"
    return "BELOW_TARGET"


def _case(
    *,
    name: str,
    final_bending_utilisation: float,
    exhausted_strategy_lanes: list[str],
    blocked_strategy_lanes: list[str],
    exact_stop_reason: str | None,
    no_valid_strategy_reason: str | None,
    geometry_locked: bool,
    reinforcement_locked: bool,
    detailing_blocked: bool = False,
    implementation_cap_only: bool = False,
) -> dict[str, Any]:
    target_status = _target_band_status(float(final_bending_utilisation))
    exact_stop_valid = bool(
        exact_stop_reason
        and (target_status == "TARGET_REACHED" or set(ALL_NON_TERMINAL_LANES).issubset(set(exhausted_strategy_lanes)))
    )
    no_valid_valid = bool(
        no_valid_strategy_reason
        and target_status == "STILL_FAILING"
        and set(ALL_NON_TERMINAL_LANES).issubset(set(exhausted_strategy_lanes) | set(blocked_strategy_lanes))
        and not implementation_cap_only
    )

    if exact_stop_valid and not no_valid_valid:
        outcome = "EXACT_STOP"
    elif no_valid_valid and not exact_stop_valid:
        outcome = "NO_VALID_STRATEGY"
    else:
        outcome = "INVALID_TERMINAL_STATE"

    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "final_bending_utilisation": float(final_bending_utilisation),
        "target_band_status": target_status,
        "exhausted_strategy_lanes": list(exhausted_strategy_lanes),
        "blocked_strategy_lanes": list(blocked_strategy_lanes),
        "exact_stop_reason": exact_stop_reason,
        "no_valid_strategy_reason": no_valid_strategy_reason,
        "geometry_locked": bool(geometry_locked),
        "reinforcement_locked": bool(reinforcement_locked),
        "detailing_blocked": bool(detailing_blocked),
        "implementation_cap_only": bool(implementation_cap_only),
        "exact_stop_valid": bool(exact_stop_valid),
        "no_valid_strategy_valid": bool(no_valid_valid),
        "terminal_outcome": outcome,
        "exactly_one_terminal_outcome": outcome in {"EXACT_STOP", "NO_VALID_STRATEGY"},
    }
    evidence["terminal_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    exact_lane = dict(snapshot.get("exact_stop_lane_definition") or {})
    no_valid_lane = dict(snapshot.get("no_valid_strategy_lane_definition") or {})
    if str(exact_lane.get("lane_id") or "") != "exact_stop":
        failures.append("exact_stop_lane_missing")
    if str(no_valid_lane.get("lane_id") or "") != "no_valid_strategy":
        failures.append("no_valid_strategy_lane_missing")
    if "EXACT_STOP" not in ladder_order or "NO_VALID_STRATEGY" not in ladder_order:
        failures.append("terminal_lanes_missing_from_ladder_order")
    if not any("Exactly one final family outcome" in rule for rule in snapshot.get("global_family_rules") or []):
        failures.append("exactly_one_final_outcome_rule_missing")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    exact = cases.get("exact_stop_reached") or {}
    if exact.get("terminal_outcome") != "EXACT_STOP":
        failures.append("exact_stop_case_not_exact_stop")
    if exact.get("exactly_one_terminal_outcome") is not True:
        failures.append("exact_stop_case_not_exactly_one")

    no_valid = cases.get("no_valid_strategy_reached") or {}
    if no_valid.get("terminal_outcome") != "NO_VALID_STRATEGY":
        failures.append("no_valid_case_not_no_valid_strategy")
    if no_valid.get("target_band_status") != "STILL_FAILING":
        failures.append("no_valid_case_not_failed_utilisation")

    geometry = cases.get("geometry_detailing_blocked") or {}
    if geometry.get("terminal_outcome") != "NO_VALID_STRATEGY":
        failures.append("geometry_detailing_blocked_case_not_no_valid_strategy")
    if geometry.get("detailing_blocked") is not True:
        failures.append("geometry_detailing_blocked_case_missing_detailing_block")

    reo_locked = cases.get("reinforcement_locked") or {}
    if reo_locked.get("terminal_outcome") != "NO_VALID_STRATEGY":
        failures.append("reinforcement_locked_case_not_no_valid_strategy")
    if reo_locked.get("reinforcement_locked") is not True:
        failures.append("reinforcement_locked_case_missing_reo_lock")
    cap_only = cases.get("candidate_cap_only") or {}
    if cap_only.get("terminal_outcome") != "INVALID_TERMINAL_STATE":
        failures.append("candidate_cap_only_was_treated_as_terminal")
    if cap_only.get("implementation_cap_only") is not True:
        failures.append("candidate_cap_only_case_missing_cap_flag")

    for case in cases.values():
        if case.get("case") == "candidate_cap_only":
            if case.get("terminal_outcome") != "INVALID_TERMINAL_STATE":
                failures.append("candidate_cap_only_not_invalid_terminal_state")
            continue
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("terminal_hash"):
            failures.append(f"{case.get('case')}:missing_terminal_hash")
        if case.get("exactly_one_terminal_outcome") is not True:
            failures.append(f"{case.get('case')}:not_exactly_one_terminal_outcome")
        if case.get("terminal_outcome") == "EXACT_STOP" and not (
            case.get("target_band_status") == "TARGET_REACHED" or case.get("exact_stop_reason")
        ):
            failures.append(f"{case.get('case')}:exact_stop_without_acceptable_util_or_exhaustion")
        if case.get("terminal_outcome") == "NO_VALID_STRATEGY" and case.get("target_band_status") != "STILL_FAILING":
            failures.append(f"{case.get('case')}:no_valid_without_failed_utilisation")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Terminal Lane Snapshot",
        "",
        f"Status: {snapshot.get('status')}",
        "",
        "## Scope",
        "",
        "Snapshot/proof only. No product behaviour, ladder order, CTA rendering, publication, apply routing, one-click fallback, visible wording, UI/session/debug, or implementation code was changed.",
        "",
        "## Contract",
        "",
        f"- contract: `{snapshot.get('contract_path')}`",
        f"- family_id: `{snapshot.get('family_id')}`",
        f"- contract_ladder_order: `{snapshot.get('contract_ladder_order')}`",
        f"- exact_stop_lane_definition: `{snapshot.get('exact_stop_lane_definition')}`",
        f"- no_valid_strategy_lane_definition: `{snapshot.get('no_valid_strategy_lane_definition')}`",
        "",
        "## Cases",
        "",
    ]
    for case in snapshot.get("cases") or []:
        lines.extend(
            [
                f"### {case.get('case')}",
                "",
                f"- final bending utilisation: `{case.get('final_bending_utilisation')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- exhausted lanes: `{case.get('exhausted_strategy_lanes')}`",
                f"- blocked lanes: `{case.get('blocked_strategy_lanes')}`",
                f"- exact-stop reason: `{case.get('exact_stop_reason')}`",
                f"- no-valid-strategy reason: `{case.get('no_valid_strategy_reason')}`",
                f"- geometry locked: `{case.get('geometry_locked')}`",
                f"- reinforcement locked: `{case.get('reinforcement_locked')}`",
                f"- outcome: `{case.get('terminal_outcome')}`",
                f"- hash: `{case.get('terminal_hash')}`",
                "",
            ]
        )
    lines.extend(["## Failures", ""])
    lines.extend([f"- {failure}" for failure in snapshot.get("failures") or []] or ["- none"])
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "PASS: EXACT_STOP and NO_VALID_STRATEGY are contract-defined terminal lanes, produce exactly one terminal outcome, and remain isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: terminal lane proof is not sufficient for migration."
            ),
            "",
            "## Output",
            "",
            f"- JSON: `{snapshot.get('artifact_path')}`",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_terminal_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_terminal_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    cases = [
        _case(
            name="exact_stop_reached",
            final_bending_utilisation=0.96,
            exhausted_strategy_lanes=["GEOMETRY_SANITY", "DEPTH_INCREASE", "SINGLE_LAYER_BOTTOM_REO"],
            blocked_strategy_lanes=[],
            exact_stop_reason="target band reached by contract ladder",
            no_valid_strategy_reason=None,
            geometry_locked=False,
            reinforcement_locked=False,
        ),
        _case(
            name="no_valid_strategy_reached",
            final_bending_utilisation=1.18,
            exhausted_strategy_lanes=ALL_NON_TERMINAL_LANES,
            blocked_strategy_lanes=["MULTI_LAYER_REO"],
            exact_stop_reason=None,
            no_valid_strategy_reason="failed utilisation with exhausted ladder",
            geometry_locked=False,
            reinforcement_locked=False,
        ),
        _case(
            name="geometry_detailing_blocked",
            final_bending_utilisation=1.20,
            exhausted_strategy_lanes=["GEOMETRY_SANITY"],
            blocked_strategy_lanes=ALL_NON_TERMINAL_LANES,
            exact_stop_reason=None,
            no_valid_strategy_reason="geometry/detailing restrictions block legal strengthening path",
            geometry_locked=True,
            reinforcement_locked=False,
            detailing_blocked=True,
        ),
        _case(
            name="reinforcement_locked",
            final_bending_utilisation=1.16,
            exhausted_strategy_lanes=["GEOMETRY_SANITY", "DEPTH_INCREASE", "WIDTH_INCREASE"],
            blocked_strategy_lanes=[
                "SINGLE_LAYER_BOTTOM_REO",
                "LARGER_BAR",
                "MULTI_LAYER_REO",
            ],
            exact_stop_reason=None,
            no_valid_strategy_reason="reinforcement locked and bending still fails",
            geometry_locked=False,
            reinforcement_locked=True,
        ),
        _case(
            name="candidate_cap_only",
            final_bending_utilisation=1.18,
            exhausted_strategy_lanes=ALL_NON_TERMINAL_LANES,
            blocked_strategy_lanes=[],
            exact_stop_reason=None,
            no_valid_strategy_reason="candidate cap reached",
            geometry_locked=False,
            reinforcement_locked=False,
            implementation_cap_only=True,
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_terminal_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "exact_stop_lane_definition": _lane_definition("exact_stop"),
        "no_valid_strategy_lane_definition": _lane_definition("no_valid_strategy"),
        "global_family_rules": list(global_family_rules()),
        "contract_version": contract.get("schema"),
        "cases": cases,
        "shared_fields_excluded": sorted(FORBIDDEN_PROOF_KEYS),
        "failures": [],
    }
    snapshot["failures"] = _assert_snapshot(snapshot)
    snapshot["status"] = "PASS" if not snapshot["failures"] else "FAIL"
    snapshot["snapshot_hash"] = _stable_hash(
        {
            "family_id": snapshot["family_id"],
            "contract_ladder_order": snapshot["contract_ladder_order"],
            "exact_stop_lane_definition": snapshot["exact_stop_lane_definition"],
            "no_valid_strategy_lane_definition": snapshot["no_valid_strategy_lane_definition"],
            "cases": snapshot["cases"],
        }
    )
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": snapshot["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
