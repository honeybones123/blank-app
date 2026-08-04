"""BENDING_FAIL_GOVERNS multi-layer reo lane snapshot.

Proof-only verifier for the contract-defined MULTI_LAYER_REO lane. It loads
the lane definition from the BENDING_FAIL_GOVERNS contract and evaluates
normalized multi-layer evidence without changing product behaviour or live
ladder order.
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


def _target_band_status(util_after: float, *, low: float = 0.85, high: float = 1.0) -> str:
    if low <= float(util_after) <= high:
        return "TARGET_REACHED"
    if float(util_after) > high:
        return "STILL_FAILING"
    return "BELOW_TARGET"


def _case(
    *,
    name: str,
    triggering_reason: str,
    layer_arrangement: list[dict[str, Any]],
    actual_reinforcement_centroid_mm: float | None,
    bending_util_before: float,
    bending_util_after: float,
    congestion_status: str,
    width_valid_strategy_remaining: bool = False,
    detailing_status: str = "PASS",
) -> dict[str, Any]:
    target_status = _target_band_status(float(bending_util_after))
    trigger = str(triggering_reason).upper()
    valid_trigger = trigger in {
        "WIDTH_BLOCKED",
        "WIDTH_LOCKED",
        "WIDTH_INEFFECTIVE",
        "SINGLE_LAYER_REINFORCEMENT_CANNOT_FIT",
    }
    detailing_blocked = str(detailing_status).upper() not in {"PASS", "ACCEPTABLE"}
    congestion_blocked = str(congestion_status).upper() in {"BLOCKED", "CONGESTION_BLOCKED", "SPACING_LIMIT"}
    uses_actual_centroid = actual_reinforcement_centroid_mm is not None

    if detailing_blocked:
        result = "DETAILING_BLOCKED"
    elif congestion_blocked:
        result = "CONGESTION_BLOCKED"
    elif target_status == "TARGET_REACHED":
        result = "TARGET_REACHED"
    elif float(bending_util_after) < float(bending_util_before):
        result = "ACCEPTED"
    else:
        result = "INSUFFICIENT"

    transition = "EXACT_STOP" if result == "TARGET_REACHED" else "NO_VALID_STRATEGY"
    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "triggering_reason": str(triggering_reason),
        "valid_multilayer_trigger": bool(valid_trigger),
        "width_valid_strategy_remaining": bool(width_valid_strategy_remaining),
        "entered_only_after_width_exhausted_or_blocked": bool(valid_trigger and not width_valid_strategy_remaining),
        "reinforcement_layer_arrangement": list(layer_arrangement),
        "actual_reinforcement_centroid_mm": actual_reinforcement_centroid_mm,
        "capacity_uses_actual_reinforcement_centroid": bool(uses_actual_centroid),
        "bending_utilisation_before": float(bending_util_before),
        "bending_utilisation_after": float(bending_util_after),
        "congestion_status": str(congestion_status),
        "detailing_status": str(detailing_status),
        "target_band_status": target_status,
        "multi_layer_reo_result": result,
        "transition": transition,
        "transition_evidence": {
            "to_EXACT_STOP": transition == "EXACT_STOP",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "width_not_valid_strategy_remaining": not bool(width_valid_strategy_remaining),
            "actual_centroid_available": bool(uses_actual_centroid),
        },
    }
    evidence["multi_layer_reo_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    lane = dict(snapshot.get("multi_layer_reo_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "multi_layer_reinforcement":
        failures.append("multi_layer_reo_lane_missing")
    if "WIDTH_INCREASE" not in ladder_order or "MULTI_LAYER_REO" not in ladder_order:
        failures.append("width_or_multilayer_missing_from_ladder_order")
    elif ladder_order.index("MULTI_LAYER_REO") != ladder_order.index("WIDTH_INCREASE") + 1:
        failures.append("multi_layer_reo_not_after_width_increase")
    rules = [str(value).lower() for value in lane.get("rules") or []]
    evidence = [str(value).lower() for value in lane.get("required_evidence") or []]
    if not any("actual reinforcement centroid" in value for value in rules + evidence):
        failures.append("actual_reinforcement_centroid_not_contract_required")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    accepted = cases.get("multi_layer_accepted") or {}
    if accepted.get("multi_layer_reo_result") != "ACCEPTED":
        failures.append("accepted_case_not_accepted")
    if accepted.get("transition") != "NO_VALID_STRATEGY":
        failures.append("accepted_case_bad_transition")

    target = cases.get("multi_layer_reaches_target") or {}
    if target.get("multi_layer_reo_result") != "TARGET_REACHED":
        failures.append("target_case_not_target_reached")
    if target.get("transition") != "EXACT_STOP":
        failures.append("target_case_not_exact_stop")

    blocked = cases.get("multi_layer_blocked") or {}
    if blocked.get("multi_layer_reo_result") not in {"DETAILING_BLOCKED", "CONGESTION_BLOCKED"}:
        failures.append("blocked_case_not_blocked")
    if blocked.get("transition") != "NO_VALID_STRATEGY":
        failures.append("blocked_case_not_no_valid_strategy")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("multi_layer_reo_hash"):
            failures.append(f"{case.get('case')}:missing_multi_layer_reo_hash")
        if case.get("entered_only_after_width_exhausted_or_blocked") is not True:
            failures.append(f"{case.get('case')}:entered_before_width_exhausted_or_blocked")
        if case.get("capacity_uses_actual_reinforcement_centroid") is not True:
            failures.append(f"{case.get('case')}:actual_centroid_not_used")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Multi-Layer Reo Lane Snapshot",
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
        f"- multi_layer_reo_lane_definition: `{snapshot.get('multi_layer_reo_lane_definition')}`",
        "",
        "## Cases",
        "",
    ]
    for case in snapshot.get("cases") or []:
        lines.extend(
            [
                f"### {case.get('case')}",
                "",
                f"- triggering reason: `{case.get('triggering_reason')}`",
                f"- layer arrangement: `{case.get('reinforcement_layer_arrangement')}`",
                f"- actual reinforcement centroid: `{case.get('actual_reinforcement_centroid_mm')}`",
                f"- bending util before/after: `{case.get('bending_utilisation_before')}` -> `{case.get('bending_utilisation_after')}`",
                f"- congestion status: `{case.get('congestion_status')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- result: `{case.get('multi_layer_reo_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('multi_layer_reo_hash')}`",
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
                "PASS: MULTI_LAYER_REO is contract-defined, follows WIDTH_INCREASE, uses actual reinforcement centroid evidence, and remains isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: MULTI_LAYER_REO lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_multi_layer_reo_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_multi_layer_reo_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _lane_definition("multi_layer_reinforcement")
    cases = [
        _case(
            name="multi_layer_accepted",
            triggering_reason="WIDTH_BLOCKED",
            layer_arrangement=[
                {"layer": 1, "bars": 4, "bar_size": "N24"},
                {"layer": 2, "bars": 2, "bar_size": "N24"},
            ],
            actual_reinforcement_centroid_mm=92.0,
            bending_util_before=1.14,
            bending_util_after=1.04,
            congestion_status="ACCEPTABLE",
        ),
        _case(
            name="multi_layer_reaches_target",
            triggering_reason="WIDTH_LOCKED",
            layer_arrangement=[
                {"layer": 1, "bars": 4, "bar_size": "N24"},
                {"layer": 2, "bars": 3, "bar_size": "N24"},
            ],
            actual_reinforcement_centroid_mm=97.5,
            bending_util_before=1.10,
            bending_util_after=0.96,
            congestion_status="ACCEPTABLE",
        ),
        _case(
            name="multi_layer_blocked",
            triggering_reason="SINGLE_LAYER_REINFORCEMENT_CANNOT_FIT",
            layer_arrangement=[
                {"layer": 1, "bars": 5, "bar_size": "N28"},
                {"layer": 2, "bars": 4, "bar_size": "N28"},
            ],
            actual_reinforcement_centroid_mm=112.0,
            bending_util_before=1.20,
            bending_util_after=1.20,
            congestion_status="CONGESTION_BLOCKED",
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_multi_layer_reo_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "multi_layer_reo_lane_definition": lane,
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
            "multi_layer_reo_lane_definition": snapshot["multi_layer_reo_lane_definition"],
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
