"""BENDING_FAIL_GOVERNS larger bar lane snapshot.

Proof-only verifier for the contract-defined LARGER_BAR lane. It loads the
lane definition from the BENDING_FAIL_GOVERNS contract and evaluates normalized
larger-bar evidence without changing product behaviour or live ladder order.
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
    bending_util_before: float,
    bending_util_after: float,
    bar_size_before: str,
    bar_size_after: str,
    bar_count_before: int,
    bar_count_after: int,
    spacing_before: float,
    spacing_after: float,
    single_layer_precondition: str,
    reinforcement_locked: bool = False,
    width_locked: bool = False,
    geometry_locked: bool = False,
    anchorage_detailing_status: str = "PASS",
    congestion_status: str = "ACCEPTABLE",
) -> dict[str, Any]:
    target_status = _target_band_status(float(bending_util_after))
    detailing_blocked = str(anchorage_detailing_status).upper() not in {"PASS", "ACCEPTABLE"}
    congestion_blocked = str(congestion_status).upper() in {"BLOCKED", "CONGESTION_BLOCKED", "SPACING_LIMIT"}
    single_layer_exhausted = str(single_layer_precondition).upper() in {
        "BLOCKED",
        "INSUFFICIENT",
        "SPACING_LIMIT",
        "CONGESTION_LIMIT",
    }

    if reinforcement_locked:
        result = "REO_LOCKED"
    elif detailing_blocked:
        result = "DETAILING_BLOCKED"
    elif congestion_blocked:
        result = "CONGESTION_BLOCKED"
    elif target_status == "TARGET_REACHED":
        result = "TARGET_REACHED"
    elif float(bending_util_after) < float(bending_util_before):
        result = "ACCEPTED"
    else:
        result = "INSUFFICIENT"

    if result == "TARGET_REACHED":
        transition = "EXACT_STOP"
    elif result in {"ACCEPTED", "INSUFFICIENT", "DETAILING_BLOCKED", "CONGESTION_BLOCKED"}:
        transition = "MULTI_LAYER_REO" if bool(width_locked or geometry_locked) else "WIDTH_INCREASE"
    elif result == "REO_LOCKED":
        transition = "NO_VALID_STRATEGY" if bool(width_locked or geometry_locked) else "WIDTH_INCREASE"
    else:
        transition = "NO_VALID_STRATEGY"

    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "starting_bending_utilisation": float(bending_util_before),
        "proposed_bending_utilisation": float(bending_util_after),
        "bar_size_before": str(bar_size_before),
        "bar_size_after": str(bar_size_after),
        "bar_count_before": int(bar_count_before),
        "bar_count_after": int(bar_count_after),
        "spacing_before_mm": float(spacing_before),
        "spacing_after_mm": float(spacing_after),
        "single_layer_precondition": str(single_layer_precondition),
        "single_layer_add_bar_or_spacing_options_exhausted": bool(single_layer_exhausted),
        "reinforcement_locked": bool(reinforcement_locked),
        "width_locked": bool(width_locked),
        "geometry_locked": bool(geometry_locked),
        "anchorage_detailing_status": str(anchorage_detailing_status),
        "congestion_status": str(congestion_status),
        "target_band_status": target_status,
        "larger_bar_used_after_single_layer_exhausted": bool(single_layer_exhausted),
        "larger_bar_result": result,
        "transition": transition,
        "transition_evidence": {
            "to_WIDTH_INCREASE": transition == "WIDTH_INCREASE",
            "to_MULTI_LAYER_REO": transition == "MULTI_LAYER_REO",
            "to_EXACT_STOP": transition == "EXACT_STOP",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "multilayer_only_if_width_blocked_or_locked": transition != "MULTI_LAYER_REO"
            or bool(width_locked or geometry_locked),
            "width_not_skipped": transition != "MULTI_LAYER_REO",
            "detailing_blocked": bool(detailing_blocked),
            "congestion_blocked": bool(congestion_blocked),
            "reinforcement_blocked_by_lock": bool(reinforcement_locked),
        },
    }
    evidence["larger_bar_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ladder_order = list(snapshot.get("contract_ladder_order") or [])
    lane = dict(snapshot.get("larger_bar_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "larger_bars":
        failures.append("larger_bar_lane_missing")
    if "SINGLE_LAYER_BOTTOM_REO" not in ladder_order or "LARGER_BAR" not in ladder_order:
        failures.append("single_layer_or_larger_bar_missing_from_ladder_order")
    elif ladder_order.index("LARGER_BAR") != ladder_order.index("SINGLE_LAYER_BOTTOM_REO") + 1:
        failures.append("larger_bar_not_after_single_layer_bottom_reo")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    accepted = cases.get("larger_bar_accepted_still_failing") or {}
    if accepted.get("larger_bar_result") != "ACCEPTED":
        failures.append("accepted_still_failing_case_not_accepted")
    if accepted.get("transition") != "WIDTH_INCREASE":
        failures.append("accepted_still_failing_case_not_transition_width")

    target = cases.get("larger_bar_reaches_target") or {}
    if target.get("larger_bar_result") != "TARGET_REACHED":
        failures.append("target_case_not_target_reached")
    if target.get("transition") != "EXACT_STOP":
        failures.append("target_case_not_exact_stop")

    detailing = cases.get("larger_bar_detailing_blocked") or {}
    if detailing.get("larger_bar_result") != "DETAILING_BLOCKED":
        failures.append("detailing_case_not_detailing_blocked")
    if detailing.get("transition") != "WIDTH_INCREASE":
        failures.append("detailing_case_not_transition_width")

    congestion = cases.get("larger_bar_congestion_blocked") or {}
    if congestion.get("larger_bar_result") != "CONGESTION_BLOCKED":
        failures.append("congestion_case_not_congestion_blocked")
    if congestion.get("transition") != "WIDTH_INCREASE":
        failures.append("congestion_case_not_transition_width")

    locked = cases.get("reinforcement_locked") or {}
    if locked.get("larger_bar_result") != "REO_LOCKED":
        failures.append("locked_case_not_reo_locked")
    if locked.get("transition") not in {"WIDTH_INCREASE", "NO_VALID_STRATEGY"}:
        failures.append("locked_case_bad_transition")

    width_locked = cases.get("larger_bar_blocked_width_locked") or {}
    if width_locked.get("transition") != "MULTI_LAYER_REO":
        failures.append("width_locked_case_not_transition_multilayer")
    if width_locked.get("transition_evidence", {}).get("multilayer_only_if_width_blocked_or_locked") is not True:
        failures.append("multilayer_used_before_width_blocked")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("larger_bar_hash"):
            failures.append(f"{case.get('case')}:missing_larger_bar_hash")
        if case.get("larger_bar_used_after_single_layer_exhausted") is not True:
            failures.append(f"{case.get('case')}:larger_bar_before_single_layer_exhausted")
        if case.get("transition") == "MULTI_LAYER_REO" and not (
            case.get("width_locked") or case.get("geometry_locked")
        ):
            failures.append(f"{case.get('case')}:multilayer_before_width_blocked")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Larger Bar Lane Snapshot",
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
        f"- larger_bar_lane_definition: `{snapshot.get('larger_bar_lane_definition')}`",
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
                f"- bar size before/after: `{case.get('bar_size_before')}` -> `{case.get('bar_size_after')}`",
                f"- bar count before/after: `{case.get('bar_count_before')}` -> `{case.get('bar_count_after')}`",
                f"- spacing before/after: `{case.get('spacing_before_mm')}` -> `{case.get('spacing_after_mm')}`",
                f"- single-layer precondition: `{case.get('single_layer_precondition')}`",
                f"- locked states: reo=`{case.get('reinforcement_locked')}`, width=`{case.get('width_locked')}`, geometry=`{case.get('geometry_locked')}`",
                f"- anchorage/detailing status: `{case.get('anchorage_detailing_status')}`",
                f"- congestion status: `{case.get('congestion_status')}`",
                f"- target-band status: `{case.get('target_band_status')}`",
                f"- result: `{case.get('larger_bar_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('larger_bar_hash')}`",
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
                "PASS: LARGER_BAR is contract-defined, follows SINGLE_LAYER_BOTTOM_REO, and the normalized larger-bar proof is isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: LARGER_BAR lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_larger_bar_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_larger_bar_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _lane_definition("larger_bars")
    cases = [
        _case(
            name="larger_bar_accepted_still_failing",
            bending_util_before=1.14,
            bending_util_after=1.05,
            bar_size_before="N20",
            bar_size_after="N24",
            bar_count_before=4,
            bar_count_after=4,
            spacing_before=118.0,
            spacing_after=118.0,
            single_layer_precondition="INSUFFICIENT",
        ),
        _case(
            name="larger_bar_reaches_target",
            bending_util_before=1.07,
            bending_util_after=0.96,
            bar_size_before="N20",
            bar_size_after="N24",
            bar_count_before=4,
            bar_count_after=4,
            spacing_before=118.0,
            spacing_after=118.0,
            single_layer_precondition="INSUFFICIENT",
        ),
        _case(
            name="larger_bar_detailing_blocked",
            bending_util_before=1.16,
            bending_util_after=1.16,
            bar_size_before="N24",
            bar_size_after="N28",
            bar_count_before=4,
            bar_count_after=4,
            spacing_before=108.0,
            spacing_after=108.0,
            single_layer_precondition="SPACING_LIMIT",
            anchorage_detailing_status="DETAILING_BLOCKED",
        ),
        _case(
            name="larger_bar_congestion_blocked",
            bending_util_before=1.18,
            bending_util_after=1.18,
            bar_size_before="N24",
            bar_size_after="N28",
            bar_count_before=5,
            bar_count_after=5,
            spacing_before=104.0,
            spacing_after=104.0,
            single_layer_precondition="CONGESTION_LIMIT",
            congestion_status="CONGESTION_BLOCKED",
        ),
        _case(
            name="reinforcement_locked",
            bending_util_before=1.18,
            bending_util_after=1.18,
            bar_size_before="N24",
            bar_size_after="N24",
            bar_count_before=4,
            bar_count_after=4,
            spacing_before=118.0,
            spacing_after=118.0,
            single_layer_precondition="BLOCKED",
            reinforcement_locked=True,
        ),
        _case(
            name="larger_bar_blocked_width_locked",
            bending_util_before=1.18,
            bending_util_after=1.18,
            bar_size_before="N24",
            bar_size_after="N28",
            bar_count_before=5,
            bar_count_after=5,
            spacing_before=104.0,
            spacing_after=104.0,
            single_layer_precondition="CONGESTION_LIMIT",
            width_locked=True,
            congestion_status="CONGESTION_BLOCKED",
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_larger_bar_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "larger_bar_lane_definition": lane,
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
            "larger_bar_lane_definition": snapshot["larger_bar_lane_definition"],
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
