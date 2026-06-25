"""BENDING_FAIL_GOVERNS depth increase lane snapshot.

Proof-only verifier for the contract-defined DEPTH_INCREASE lane. It loads the
depth increment rule and D/b limit from the BENDING_FAIL_GOVERNS contract and
evaluates normalized lane evidence without changing product behaviour or live
ladder order.
"""

from __future__ import annotations

import json
import re
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
    depth_width_rule,
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


def _depth_step_from_contract(lane: dict[str, Any]) -> dict[str, Any]:
    for rule in list(lane.get("rules") or []):
        text = str(rule)
        match = re.search(r"(\d+(?:\.\d+)?)\s*mm\s+increments", text)
        if match:
            return {
                "depth_step_mm": float(match.group(1)),
                "source_rule": text,
                "source": str(CONTRACT_PATH),
            }
    return {
        "depth_step_mm": None,
        "source_rule": None,
        "source": str(CONTRACT_PATH),
    }


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
    beam_depth_before: float,
    beam_width: float,
    bending_util_before: float,
    bending_util_after: float,
    depth_locked: bool = False,
    width_locked: bool = False,
    geometry_locked: bool = False,
    shear_util_before: float | None = 0.70,
    shear_util_after: float | None = 0.68,
    serviceability_before: str = "PASS",
    serviceability_after: str = "PASS",
) -> dict[str, Any]:
    lane = _lane_definition("depth_increase")
    step = _depth_step_from_contract(lane)
    depth_step_mm = float(step.get("depth_step_mm") or 0.0)
    ratio_rule = depth_width_rule()
    max_ratio = float(ratio_rule.get("maximum_preferred_ratio") or 0.0)
    beam_depth_after = float(beam_depth_before) + depth_step_mm
    ratio_before = float(beam_depth_before) / float(beam_width) if float(beam_width) else None
    ratio_after = float(beam_depth_after) / float(beam_width) if float(beam_width) else None
    ratio_blocked = ratio_after is None or ratio_after > max_ratio
    depth_growth_allowed = not bool(geometry_locked or depth_locked or ratio_blocked)
    width_growth_allowed = not bool(geometry_locked or width_locked)

    target_status = _target_band_status(float(bending_util_after))
    if geometry_locked:
        result = "GEOMETRY_LOCKED"
    elif depth_locked:
        result = "DEPTH_LOCKED"
    elif ratio_blocked:
        result = "RATIO_BLOCKED"
    elif target_status == "TARGET_REACHED":
        result = "TARGET_REACHED"
    elif float(bending_util_after) < float(bending_util_before):
        result = "ACCEPTED"
    else:
        result = "INSUFFICIENT"

    if result == "TARGET_REACHED":
        transition = "EXACT_STOP"
    elif result in {"ACCEPTED", "INSUFFICIENT"}:
        transition = "SINGLE_LAYER_BOTTOM_REO"
    elif result in {"RATIO_BLOCKED", "DEPTH_LOCKED"} and width_growth_allowed:
        transition = "WIDTH_INCREASE"
    else:
        transition = "NO_VALID_STRATEGY"

    shear_status = (
        "NOT_EVALUATED_DEPTH_BLOCKED"
        if result in {"RATIO_BLOCKED", "DEPTH_LOCKED", "GEOMETRY_LOCKED"}
        else "PASS"
        if shear_util_after is not None and float(shear_util_after) <= 1.0
        else "FAIL"
    )
    serviceability_status = (
        "NOT_EVALUATED_DEPTH_BLOCKED"
        if result in {"RATIO_BLOCKED", "DEPTH_LOCKED", "GEOMETRY_LOCKED"}
        else "PASS"
        if str(serviceability_after).upper() in {"PASS", "NOT_RUN", "NA"}
        else str(serviceability_after).upper()
    )
    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "beam_depth_before": float(beam_depth_before),
        "beam_depth_after": float(beam_depth_after),
        "beam_width": float(beam_width),
        "depth_step_from_contract": step,
        "depth_width_ratio_before": round(float(ratio_before), 6) if ratio_before is not None else None,
        "depth_width_ratio_after": round(float(ratio_after), 6) if ratio_after is not None else None,
        "max_allowed_ratio_from_contract": max_ratio,
        "depth_locked": bool(depth_locked),
        "width_locked": bool(width_locked),
        "geometry_locked": bool(geometry_locked),
        "depth_growth_allowed": bool(depth_growth_allowed),
        "width_growth_allowed": bool(width_growth_allowed),
        "bending_utilisation_before": float(bending_util_before),
        "bending_utilisation_after": float(bending_util_after),
        "shear_impact_check": {
            "utilisation_before": shear_util_before,
            "utilisation_after": shear_util_after,
            "status": shear_status,
        },
        "serviceability_impact_check": {
            "status_before": serviceability_before,
            "status_after": serviceability_after,
            "status": serviceability_status,
        },
        "target_band_status": target_status,
        "depth_increase_result": result,
        "transition": transition,
        "transition_evidence": {
            "to_SINGLE_LAYER_BOTTOM_REO": transition == "SINGLE_LAYER_BOTTOM_REO",
            "to_WIDTH_INCREASE": transition == "WIDTH_INCREASE",
            "to_EXACT_STOP": transition == "EXACT_STOP",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "does_not_transition_directly_to_MULTI_LAYER_REO": transition != "MULTI_LAYER_REO",
            "depth_blocked_by_ratio": bool(ratio_blocked),
            "depth_blocked_by_lock": bool(depth_locked or geometry_locked),
        },
    }
    evidence["depth_increase_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    lane = dict(snapshot.get("depth_increase_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "depth_increase":
        failures.append("depth_increase_lane_missing")
    if "GEOMETRY_SANITY" not in ladder_order or "DEPTH_INCREASE" not in ladder_order:
        failures.append("geometry_or_depth_lane_missing_from_ladder_order")
    elif ladder_order.index("DEPTH_INCREASE") != ladder_order.index("GEOMETRY_SANITY") + 1:
        failures.append("depth_increase_not_after_geometry_sanity")
    step = dict(snapshot.get("depth_step_from_contract") or {})
    if step.get("depth_step_mm") != 25.0 or not step.get("source_rule"):
        failures.append("depth_step_not_loaded_from_contract")
    ratio_rule = dict(snapshot.get("depth_width_rule") or {})
    if float(ratio_rule.get("maximum_preferred_ratio") or 0.0) != 2.0:
        failures.append("ratio_limit_not_loaded_from_contract")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    accepted = cases.get("depth_accepted_still_failing") or {}
    if accepted.get("depth_increase_result") != "ACCEPTED":
        failures.append("accepted_still_failing_case_not_accepted")
    if accepted.get("transition") != "SINGLE_LAYER_BOTTOM_REO":
        failures.append("accepted_still_failing_case_not_transition_single_layer")
    if accepted.get("transition_evidence", {}).get("does_not_transition_directly_to_MULTI_LAYER_REO") is not True:
        failures.append("accepted_still_failing_case_transitions_to_multilayer")

    target = cases.get("depth_reaches_target") or {}
    if target.get("depth_increase_result") != "TARGET_REACHED":
        failures.append("target_case_not_target_reached")
    if target.get("transition") != "EXACT_STOP":
        failures.append("target_case_not_exact_stop")

    ratio = cases.get("ratio_blocked") or {}
    if ratio.get("depth_increase_result") != "RATIO_BLOCKED":
        failures.append("ratio_case_not_ratio_blocked")
    if ratio.get("depth_growth_allowed") is not False:
        failures.append("ratio_case_depth_growth_allowed")
    if ratio.get("transition") != "WIDTH_INCREASE":
        failures.append("ratio_case_not_transition_width")

    depth_locked = cases.get("depth_locked") or {}
    if depth_locked.get("depth_increase_result") != "DEPTH_LOCKED":
        failures.append("depth_locked_case_not_depth_locked")
    if depth_locked.get("depth_growth_allowed") is not False:
        failures.append("depth_locked_case_depth_growth_allowed")
    if depth_locked.get("transition") != "WIDTH_INCREASE":
        failures.append("depth_locked_case_not_transition_width")

    geometry_locked = cases.get("geometry_locked") or {}
    if geometry_locked.get("depth_increase_result") != "GEOMETRY_LOCKED":
        failures.append("geometry_locked_case_not_geometry_locked")
    if geometry_locked.get("transition") != "NO_VALID_STRATEGY":
        failures.append("geometry_locked_case_not_no_valid_strategy")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("depth_increase_hash"):
            failures.append(f"{case.get('case')}:missing_depth_increase_hash")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Depth Increase Lane Snapshot",
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
        f"- depth_increase_lane_definition: `{snapshot.get('depth_increase_lane_definition')}`",
        f"- depth_step_from_contract: `{snapshot.get('depth_step_from_contract')}`",
        f"- depth_width_rule: `{snapshot.get('depth_width_rule')}`",
        "",
        "## Cases",
        "",
    ]
    for case in snapshot.get("cases") or []:
        lines.extend(
            [
                f"### {case.get('case')}",
                "",
                f"- depth before/after: `{case.get('beam_depth_before')}` -> `{case.get('beam_depth_after')}`",
                f"- width: `{case.get('beam_width')}`",
                f"- D/b before/after: `{case.get('depth_width_ratio_before')}` -> `{case.get('depth_width_ratio_after')}`",
                f"- locked states: geometry=`{case.get('geometry_locked')}`, depth=`{case.get('depth_locked')}`, width=`{case.get('width_locked')}`",
                f"- bending util before/after: `{case.get('bending_utilisation_before')}` -> `{case.get('bending_utilisation_after')}`",
                f"- shear impact: `{case.get('shear_impact_check')}`",
                f"- serviceability impact: `{case.get('serviceability_impact_check')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- result: `{case.get('depth_increase_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('depth_increase_hash')}`",
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
                "PASS: DEPTH_INCREASE is contract-defined, follows GEOMETRY_SANITY, and the normalized depth lane proof is isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: DEPTH_INCREASE lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_depth_increase_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_depth_increase_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _lane_definition("depth_increase")
    depth_step = _depth_step_from_contract(lane)
    ratio_rule = depth_width_rule()
    cases = [
        _case(
            name="depth_accepted_still_failing",
            beam_depth_before=500.0,
            beam_width=300.0,
            bending_util_before=1.20,
            bending_util_after=1.08,
        ),
        _case(
            name="depth_reaches_target",
            beam_depth_before=500.0,
            beam_width=300.0,
            bending_util_before=1.04,
            bending_util_after=0.95,
        ),
        _case(
            name="ratio_blocked",
            beam_depth_before=590.0,
            beam_width=300.0,
            bending_util_before=1.20,
            bending_util_after=1.05,
        ),
        _case(
            name="depth_locked",
            beam_depth_before=500.0,
            beam_width=300.0,
            bending_util_before=1.20,
            bending_util_after=1.10,
            depth_locked=True,
        ),
        _case(
            name="geometry_locked",
            beam_depth_before=500.0,
            beam_width=300.0,
            bending_util_before=1.20,
            bending_util_after=1.10,
            geometry_locked=True,
            depth_locked=True,
            width_locked=True,
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_depth_increase_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "depth_increase_lane_definition": lane,
        "depth_step_from_contract": depth_step,
        "depth_width_rule": ratio_rule,
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
            "depth_increase_lane_definition": snapshot["depth_increase_lane_definition"],
            "depth_step_from_contract": snapshot["depth_step_from_contract"],
            "depth_width_rule": snapshot["depth_width_rule"],
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
