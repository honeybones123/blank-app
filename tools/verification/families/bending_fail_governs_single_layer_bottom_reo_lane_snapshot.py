"""BENDING_FAIL_GOVERNS single-layer bottom reo lane snapshot.

Proof-only verifier for the contract-defined SINGLE_LAYER_BOTTOM_REO lane. It
loads the clear-spacing limit and ladder lane definition from the
BENDING_FAIL_GOVERNS contract and evaluates normalized lane evidence without
changing product behaviour or live ladder order.
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


def _clear_spacing_limit_from_contract(lane: dict[str, Any]) -> dict[str, Any]:
    for limit in list(lane.get("limits") or []):
        text = str(limit)
        match = re.search(r"approximately\s+(\d+(?:\.\d+)?)\s*mm", text, flags=re.IGNORECASE)
        if match:
            return {
                "clear_spacing_limit_mm": float(match.group(1)),
                "source_limit": text,
                "source": str(CONTRACT_PATH),
            }
    return {
        "clear_spacing_limit_mm": None,
        "source_limit": None,
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
    bending_util_before: float,
    bending_util_after: float,
    bar_count_before: int,
    bar_count_after: int,
    bar_size_before: str,
    bar_size_after: str,
    spacing_before: float,
    spacing_after: float,
    reinforcement_locked: bool = False,
    geometry_locked: bool = False,
    width_locked: bool = False,
    geometry_state: str = "VALID",
    congestion_status: str = "ACCEPTABLE",
    after_width_increase_reentry: bool = False,
) -> dict[str, Any]:
    lane = _lane_definition("single_layer_bottom_reinforcement")
    spacing_limit = _clear_spacing_limit_from_contract(lane)
    limit_mm = float(spacing_limit.get("clear_spacing_limit_mm") or 0.0)
    target_status = _target_band_status(float(bending_util_after))
    spacing_blocked = float(spacing_after) <= limit_mm
    geometry_blocked = bool(geometry_locked or str(geometry_state).upper() not in {"VALID", "WIDTH_INCREASED_VALID"})
    reo_option_attempted = not bool(reinforcement_locked or geometry_blocked)
    valid_single_layer_option_remains = bool(
        reo_option_attempted and not spacing_blocked and float(bending_util_after) > 1.0
    )

    if geometry_blocked:
        result = "GEOMETRY_BLOCKED"
    elif reinforcement_locked:
        result = "REO_LOCKED"
    elif target_status == "TARGET_REACHED":
        result = "TARGET_REACHED"
    elif spacing_blocked:
        result = "SPACING_BLOCKED"
    elif float(bending_util_after) < float(bending_util_before):
        result = "ACCEPTED"
    else:
        result = "INSUFFICIENT"

    if result == "TARGET_REACHED":
        transition = "EXACT_STOP"
    elif result == "ACCEPTED":
        transition = "LARGER_BAR"
    elif result in {"SPACING_BLOCKED", "INSUFFICIENT"}:
        transition = "WIDTH_INCREASE" if not bool(width_locked or geometry_locked) else "MULTI_LAYER_REO"
    elif result in {"REO_LOCKED", "GEOMETRY_BLOCKED"}:
        transition = "WIDTH_INCREASE" if not bool(width_locked or geometry_locked) else "NO_VALID_STRATEGY"
    else:
        transition = "NO_VALID_STRATEGY"

    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "starting_bending_utilisation": float(bending_util_before),
        "proposed_bending_utilisation": float(bending_util_after),
        "bar_count_before": int(bar_count_before),
        "bar_count_after": int(bar_count_after),
        "bar_size_before": str(bar_size_before),
        "bar_size_after": str(bar_size_after),
        "spacing_before_mm": float(spacing_before),
        "spacing_after_mm": float(spacing_after),
        "clear_spacing_limit_from_contract": spacing_limit,
        "reinforcement_locked": bool(reinforcement_locked),
        "geometry_locked": bool(geometry_locked),
        "width_locked": bool(width_locked),
        "geometry_state": str(geometry_state),
        "congestion_status": str(congestion_status),
        "target_band_status": target_status,
        "single_layer_option_attempted": bool(reo_option_attempted),
        "valid_single_layer_option_remains": bool(valid_single_layer_option_remains),
        "larger_bar_considered_only_after_single_layer_attempt": bool(
            transition != "LARGER_BAR" or reo_option_attempted
        ),
        "width_precedes_multilayer_unless_width_blocked": bool(
            transition != "MULTI_LAYER_REO" or width_locked or geometry_locked
        ),
        "after_width_increase_reentry": bool(after_width_increase_reentry),
        "reentered_after_width_increase": bool(
            after_width_increase_reentry and str(geometry_state).upper() == "WIDTH_INCREASED_VALID"
        ),
        "single_layer_bottom_reo_result": result,
        "transition": transition,
        "transition_evidence": {
            "to_LARGER_BAR": transition == "LARGER_BAR",
            "to_WIDTH_INCREASE": transition == "WIDTH_INCREASE",
            "to_MULTI_LAYER_REO": transition == "MULTI_LAYER_REO",
            "to_EXACT_STOP": transition == "EXACT_STOP",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "multilayer_only_if_width_blocked_or_locked": transition != "MULTI_LAYER_REO"
            or bool(width_locked or geometry_locked),
            "spacing_blocked_by_contract_limit": bool(spacing_blocked),
            "reinforcement_blocked_by_lock": bool(reinforcement_locked),
        },
    }
    evidence["single_layer_bottom_reo_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    lane = dict(snapshot.get("single_layer_bottom_reo_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "single_layer_bottom_reinforcement":
        failures.append("single_layer_bottom_reo_lane_missing")
    if "DEPTH_INCREASE" not in ladder_order or "SINGLE_LAYER_BOTTOM_REO" not in ladder_order:
        failures.append("depth_or_single_layer_lane_missing_from_ladder_order")
    elif ladder_order.index("SINGLE_LAYER_BOTTOM_REO") != ladder_order.index("DEPTH_INCREASE") + 1:
        failures.append("single_layer_bottom_reo_not_after_depth_increase")
    spacing_limit = dict(snapshot.get("clear_spacing_limit_from_contract") or {})
    if spacing_limit.get("clear_spacing_limit_mm") != 100.0 or not spacing_limit.get("source_limit"):
        failures.append("clear_spacing_limit_not_loaded_from_contract")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    accepted = cases.get("single_layer_accepted_still_failing") or {}
    if accepted.get("single_layer_bottom_reo_result") != "ACCEPTED":
        failures.append("accepted_still_failing_case_not_accepted")
    if accepted.get("transition") != "LARGER_BAR":
        failures.append("accepted_still_failing_case_not_transition_larger_bar")
    if accepted.get("larger_bar_considered_only_after_single_layer_attempt") is not True:
        failures.append("larger_bar_used_before_single_layer_attempt")

    target = cases.get("single_layer_reaches_target") or {}
    if target.get("single_layer_bottom_reo_result") != "TARGET_REACHED":
        failures.append("target_case_not_target_reached")
    if target.get("transition") != "EXACT_STOP":
        failures.append("target_case_not_exact_stop")

    spacing = cases.get("spacing_blocked") or {}
    if spacing.get("single_layer_bottom_reo_result") != "SPACING_BLOCKED":
        failures.append("spacing_case_not_spacing_blocked")
    if spacing.get("transition") not in {"LARGER_BAR", "WIDTH_INCREASE"}:
        failures.append("spacing_case_bad_transition")

    locked = cases.get("reo_locked") or {}
    if locked.get("single_layer_bottom_reo_result") != "REO_LOCKED":
        failures.append("reo_locked_case_not_reo_locked")
    if locked.get("transition") not in {"WIDTH_INCREASE", "NO_VALID_STRATEGY"}:
        failures.append("reo_locked_case_bad_transition")

    blocked_width = cases.get("spacing_blocked_width_locked") or {}
    if blocked_width.get("transition") != "MULTI_LAYER_REO":
        failures.append("width_locked_case_not_transition_multilayer")
    if blocked_width.get("transition_evidence", {}).get("multilayer_only_if_width_blocked_or_locked") is not True:
        failures.append("multilayer_used_before_width_blocked")

    reentry = cases.get("after_width_increase_reentry") or {}
    if reentry.get("reentered_after_width_increase") is not True:
        failures.append("width_reentry_case_not_proven")
    if reentry.get("single_layer_option_attempted") is not True:
        failures.append("width_reentry_case_single_layer_not_attempted")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("single_layer_bottom_reo_hash"):
            failures.append(f"{case.get('case')}:missing_single_layer_bottom_reo_hash")
        if case.get("transition") == "MULTI_LAYER_REO" and not (
            case.get("width_locked") or case.get("geometry_locked")
        ):
            failures.append(f"{case.get('case')}:multilayer_before_width_blocked")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Single-Layer Bottom Reo Lane Snapshot",
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
        f"- single_layer_bottom_reo_lane_definition: `{snapshot.get('single_layer_bottom_reo_lane_definition')}`",
        f"- clear_spacing_limit_from_contract: `{snapshot.get('clear_spacing_limit_from_contract')}`",
        "",
        "## Cases",
        "",
    ]
    for case in snapshot.get("cases") or []:
        lines.extend(
            [
                f"### {case.get('case')}",
                "",
                f"- bending util before/after: `{case.get('starting_bending_utilisation')}` -> `{case.get('proposed_bending_utilisation')}`",
                f"- bar count before/after: `{case.get('bar_count_before')}` -> `{case.get('bar_count_after')}`",
                f"- bar size before/after: `{case.get('bar_size_before')}` -> `{case.get('bar_size_after')}`",
                f"- spacing before/after: `{case.get('spacing_before_mm')}` -> `{case.get('spacing_after_mm')}`",
                f"- locked states: geometry=`{case.get('geometry_locked')}`, reo=`{case.get('reinforcement_locked')}`, width=`{case.get('width_locked')}`",
                f"- congestion status: `{case.get('congestion_status')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- result: `{case.get('single_layer_bottom_reo_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('single_layer_bottom_reo_hash')}`",
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
                "PASS: SINGLE_LAYER_BOTTOM_REO is contract-defined, follows DEPTH_INCREASE, and the normalized single-layer proof is isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: SINGLE_LAYER_BOTTOM_REO lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_single_layer_bottom_reo_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_single_layer_bottom_reo_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _lane_definition("single_layer_bottom_reinforcement")
    spacing_limit = _clear_spacing_limit_from_contract(lane)
    cases = [
        _case(
            name="single_layer_accepted_still_failing",
            bending_util_before=1.18,
            bending_util_after=1.06,
            bar_count_before=3,
            bar_count_after=4,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=160.0,
            spacing_after=120.0,
        ),
        _case(
            name="single_layer_reaches_target",
            bending_util_before=1.05,
            bending_util_after=0.96,
            bar_count_before=3,
            bar_count_after=4,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=160.0,
            spacing_after=125.0,
        ),
        _case(
            name="spacing_blocked",
            bending_util_before=1.22,
            bending_util_after=1.10,
            bar_count_before=4,
            bar_count_after=5,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=120.0,
            spacing_after=95.0,
            congestion_status="SPACING_LIMIT",
        ),
        _case(
            name="reo_locked",
            bending_util_before=1.22,
            bending_util_after=1.22,
            bar_count_before=4,
            bar_count_after=4,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=145.0,
            spacing_after=145.0,
            reinforcement_locked=True,
        ),
        _case(
            name="spacing_blocked_width_locked",
            bending_util_before=1.22,
            bending_util_after=1.10,
            bar_count_before=4,
            bar_count_after=5,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=120.0,
            spacing_after=95.0,
            width_locked=True,
            congestion_status="SPACING_LIMIT_WIDTH_LOCKED",
        ),
        _case(
            name="after_width_increase_reentry",
            bending_util_before=1.18,
            bending_util_after=1.04,
            bar_count_before=4,
            bar_count_after=5,
            bar_size_before="N20",
            bar_size_after="N20",
            spacing_before=150.0,
            spacing_after=118.0,
            geometry_state="WIDTH_INCREASED_VALID",
            after_width_increase_reentry=True,
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_single_layer_bottom_reo_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "single_layer_bottom_reo_lane_definition": lane,
        "clear_spacing_limit_from_contract": spacing_limit,
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
            "single_layer_bottom_reo_lane_definition": snapshot["single_layer_bottom_reo_lane_definition"],
            "clear_spacing_limit_from_contract": snapshot["clear_spacing_limit_from_contract"],
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
