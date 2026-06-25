"""BENDING_FAIL_GOVERNS width increase lane snapshot.

Proof-only verifier for the contract-defined WIDTH_INCREASE lane. It loads
the width increment options and lane definition from the BENDING_FAIL_GOVERNS
contract and evaluates normalized width-lane evidence without changing product
behaviour or live ladder order.
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


def _width_increment_options_from_contract(lane: dict[str, Any]) -> dict[str, Any]:
    for rule in list(lane.get("rules") or []):
        text = str(rule)
        if "increase width" not in text.lower():
            continue
        matches = re.findall(r"(\d+(?:\.\d+)?)\s*mm", text)
        if matches:
            return {
                "width_increment_options_mm": [float(value) for value in matches],
                "source_rule": text,
                "source": str(CONTRACT_PATH),
            }
    return {
        "width_increment_options_mm": [],
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
    beam_width_before: float,
    width_increment_mm: float,
    beam_depth: float,
    bending_util_before: float,
    bending_util_after: float,
    spacing_before: float,
    spacing_after: float,
    congestion_before: str,
    congestion_after: str,
    width_locked: bool = False,
    geometry_locked: bool = False,
    width_effective: bool = True,
) -> dict[str, Any]:
    lane = _lane_definition("width_increase")
    increment_options = _width_increment_options_from_contract(lane)
    beam_width_after = float(beam_width_before) + (0.0 if width_locked or geometry_locked else float(width_increment_mm))
    ratio_before = float(beam_depth) / float(beam_width_before) if float(beam_width_before) else None
    ratio_after = float(beam_depth) / float(beam_width_after) if float(beam_width_after) else None
    target_status = _target_band_status(float(bending_util_after))
    spacing_improved = float(spacing_after) > float(spacing_before)
    congestion_improved = str(congestion_after).upper() not in {"BLOCKED", "CONGESTION_BLOCKED", "SPACING_LIMIT"}
    effective = bool(width_effective and (spacing_improved or congestion_improved))

    if geometry_locked:
        result = "GEOMETRY_LOCKED"
    elif width_locked:
        result = "WIDTH_LOCKED"
    elif target_status == "TARGET_REACHED":
        result = "TARGET_REACHED"
    elif not effective:
        result = "INEFFECTIVE"
    elif float(bending_util_after) < float(bending_util_before):
        result = "ACCEPTED"
    else:
        result = "INSUFFICIENT"

    if result == "TARGET_REACHED":
        transition = "EXACT_STOP"
    elif result == "ACCEPTED":
        transition = "SINGLE_LAYER_BOTTOM_REO"
    elif result in {"WIDTH_LOCKED", "GEOMETRY_LOCKED", "INEFFECTIVE", "INSUFFICIENT"}:
        transition = "MULTI_LAYER_REO" if result in {"WIDTH_LOCKED", "INEFFECTIVE"} else "NO_VALID_STRATEGY"
    else:
        transition = "NO_VALID_STRATEGY"

    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "width_increment_options_from_contract": increment_options,
        "chosen_width_increment_mm": float(width_increment_mm),
        "beam_width_before": float(beam_width_before),
        "beam_width_after": float(beam_width_after),
        "beam_depth": float(beam_depth),
        "depth_width_ratio_before": round(float(ratio_before), 6) if ratio_before is not None else None,
        "depth_width_ratio_after": round(float(ratio_after), 6) if ratio_after is not None else None,
        "starting_bending_utilisation": float(bending_util_before),
        "proposed_bending_utilisation": float(bending_util_after),
        "spacing_congestion_effect": {
            "spacing_before_mm": float(spacing_before),
            "spacing_after_mm": float(spacing_after),
            "spacing_improved": bool(spacing_improved),
            "congestion_before": str(congestion_before),
            "congestion_after": str(congestion_after),
            "congestion_improved": bool(congestion_improved),
            "width_effective": bool(effective),
        },
        "width_locked": bool(width_locked),
        "geometry_locked": bool(geometry_locked),
        "target_band_status": target_status,
        "width_increase_result": result,
        "transition": transition,
        "transition_evidence": {
            "back_to_SINGLE_LAYER_BOTTOM_REO": transition == "SINGLE_LAYER_BOTTOM_REO",
            "to_MULTI_LAYER_REO": transition == "MULTI_LAYER_REO",
            "to_EXACT_STOP": transition == "EXACT_STOP",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "multilayer_only_if_width_blocked_locked_or_ineffective": transition != "MULTI_LAYER_REO"
            or result in {"WIDTH_LOCKED", "GEOMETRY_LOCKED", "INEFFECTIVE"},
            "geometry_change_rechecks_reinforcement": transition == "SINGLE_LAYER_BOTTOM_REO",
        },
    }
    evidence["width_increase_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    lane = dict(snapshot.get("width_increase_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "width_increase":
        failures.append("width_increase_lane_missing")
    if "LARGER_BAR" not in ladder_order or "WIDTH_INCREASE" not in ladder_order:
        failures.append("larger_bar_or_width_missing_from_ladder_order")
    elif ladder_order.index("WIDTH_INCREASE") != ladder_order.index("LARGER_BAR") + 1:
        failures.append("width_increase_not_after_larger_bar")
    increments = dict(snapshot.get("width_increment_options_from_contract") or {})
    if increments.get("width_increment_options_mm") != [25.0, 50.0] or not increments.get("source_rule"):
        failures.append("width_increment_options_not_loaded_from_contract")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    accepted = cases.get("width_increase_accepted_still_failing") or {}
    if accepted.get("width_increase_result") != "ACCEPTED":
        failures.append("accepted_still_failing_case_not_accepted")
    if accepted.get("transition") != "SINGLE_LAYER_BOTTOM_REO":
        failures.append("accepted_still_failing_case_not_reenter_single_layer")
    if accepted.get("transition_evidence", {}).get("geometry_change_rechecks_reinforcement") is not True:
        failures.append("accepted_still_failing_case_does_not_recheck_reo")

    target = cases.get("width_increase_reaches_target") or {}
    if target.get("width_increase_result") != "TARGET_REACHED":
        failures.append("target_case_not_target_reached")
    if target.get("transition") != "EXACT_STOP":
        failures.append("target_case_not_exact_stop")

    locked = cases.get("width_locked") or {}
    if locked.get("width_increase_result") != "WIDTH_LOCKED":
        failures.append("width_locked_case_not_width_locked")
    if locked.get("transition") not in {"MULTI_LAYER_REO", "NO_VALID_STRATEGY"}:
        failures.append("width_locked_case_bad_transition")

    ineffective = cases.get("width_ineffective") or {}
    if ineffective.get("width_increase_result") != "INEFFECTIVE":
        failures.append("ineffective_case_not_ineffective")
    if ineffective.get("transition") not in {"MULTI_LAYER_REO", "NO_VALID_STRATEGY"}:
        failures.append("ineffective_case_bad_transition")

    geometry_locked = cases.get("geometry_locked") or {}
    if geometry_locked.get("width_increase_result") != "GEOMETRY_LOCKED":
        failures.append("geometry_locked_case_not_geometry_locked")
    if geometry_locked.get("transition") != "NO_VALID_STRATEGY":
        failures.append("geometry_locked_case_not_no_valid_strategy")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("width_increase_hash"):
            failures.append(f"{case.get('case')}:missing_width_increase_hash")
        if case.get("transition") == "MULTI_LAYER_REO" and case.get("width_increase_result") not in {
            "WIDTH_LOCKED",
            "GEOMETRY_LOCKED",
            "INEFFECTIVE",
        }:
            failures.append(f"{case.get('case')}:multilayer_before_width_blocked_locked_or_ineffective")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Width Increase Lane Snapshot",
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
        f"- width_increase_lane_definition: `{snapshot.get('width_increase_lane_definition')}`",
        f"- width_increment_options_from_contract: `{snapshot.get('width_increment_options_from_contract')}`",
        "",
        "## Cases",
        "",
    ]
    for case in snapshot.get("cases") or []:
        effect = case.get("spacing_congestion_effect") or {}
        lines.extend(
            [
                f"### {case.get('case')}",
                "",
                f"- width before/after: `{case.get('beam_width_before')}` -> `{case.get('beam_width_after')}`",
                f"- chosen increment: `{case.get('chosen_width_increment_mm')}`",
                f"- depth: `{case.get('beam_depth')}`",
                f"- D/b before/after: `{case.get('depth_width_ratio_before')}` -> `{case.get('depth_width_ratio_after')}`",
                f"- bending util before/after: `{case.get('starting_bending_utilisation')}` -> `{case.get('proposed_bending_utilisation')}`",
                f"- spacing before/after: `{effect.get('spacing_before_mm')}` -> `{effect.get('spacing_after_mm')}`",
                f"- congestion before/after: `{effect.get('congestion_before')}` -> `{effect.get('congestion_after')}`",
                f"- locked states: width=`{case.get('width_locked')}`, geometry=`{case.get('geometry_locked')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- result: `{case.get('width_increase_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('width_increase_hash')}`",
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
                "PASS: WIDTH_INCREASE is contract-defined, follows LARGER_BAR, and the normalized width proof cycles back to SINGLE_LAYER_BOTTOM_REO while remaining isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: WIDTH_INCREASE lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_width_increase_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_width_increase_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _lane_definition("width_increase")
    increments = _width_increment_options_from_contract(lane)
    cases = [
        _case(
            name="width_increase_accepted_still_failing",
            beam_width_before=300.0,
            width_increment_mm=25.0,
            beam_depth=550.0,
            bending_util_before=1.14,
            bending_util_after=1.06,
            spacing_before=96.0,
            spacing_after=122.0,
            congestion_before="SPACING_LIMIT",
            congestion_after="ACCEPTABLE",
        ),
        _case(
            name="width_increase_reaches_target",
            beam_width_before=300.0,
            width_increment_mm=50.0,
            beam_depth=550.0,
            bending_util_before=1.05,
            bending_util_after=0.96,
            spacing_before=98.0,
            spacing_after=140.0,
            congestion_before="SPACING_LIMIT",
            congestion_after="ACCEPTABLE",
        ),
        _case(
            name="width_locked",
            beam_width_before=300.0,
            width_increment_mm=25.0,
            beam_depth=550.0,
            bending_util_before=1.14,
            bending_util_after=1.14,
            spacing_before=96.0,
            spacing_after=96.0,
            congestion_before="SPACING_LIMIT",
            congestion_after="SPACING_LIMIT",
            width_locked=True,
        ),
        _case(
            name="width_ineffective",
            beam_width_before=300.0,
            width_increment_mm=25.0,
            beam_depth=550.0,
            bending_util_before=1.14,
            bending_util_after=1.14,
            spacing_before=96.0,
            spacing_after=98.0,
            congestion_before="SPACING_LIMIT",
            congestion_after="SPACING_LIMIT",
            width_effective=False,
        ),
        _case(
            name="geometry_locked",
            beam_width_before=300.0,
            width_increment_mm=25.0,
            beam_depth=550.0,
            bending_util_before=1.14,
            bending_util_after=1.14,
            spacing_before=96.0,
            spacing_after=96.0,
            congestion_before="SPACING_LIMIT",
            congestion_after="SPACING_LIMIT",
            geometry_locked=True,
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_width_increase_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "width_increase_lane_definition": lane,
        "width_increment_options_from_contract": increments,
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
            "width_increase_lane_definition": snapshot["width_increase_lane_definition"],
            "width_increment_options_from_contract": snapshot["width_increment_options_from_contract"],
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
