"""BENDING_FAIL_GOVERNS geometry sanity lane snapshot.

Proof-only verifier for the contract-defined GEOMETRY_SANITY lane. It loads
the ratio limit and ladder lane definition from the BENDING_FAIL_GOVERNS
contract and evaluates normalized geometry evidence without touching product
behaviour, CTA, publication, apply routing, rendering, wording, UI, session, or
debug state.
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


def _geometry_lane_definition() -> dict[str, Any]:
    for lane in internal_strategy_lanes():
        if str(lane.get("lane_id") or "") == "geometry_sanity":
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


def _case(
    *,
    name: str,
    beam_depth: float,
    beam_width: float,
    geometry_locked: bool = False,
    depth_locked: bool = False,
    width_locked: bool = False,
    bending_still_fails: bool = True,
) -> dict[str, Any]:
    ratio_rule = depth_width_rule()
    max_ratio = float(ratio_rule.get("maximum_preferred_ratio") or 0.0)
    ratio = float(beam_depth) / float(beam_width) if float(beam_width) else None
    ratio_blocked = ratio is None or ratio > max_ratio
    depth_growth_allowed = not bool(geometry_locked or depth_locked or ratio_blocked)
    width_growth_allowed = not bool(geometry_locked or width_locked)
    if geometry_locked:
        result = "GEOMETRY_LOCKED"
    elif depth_locked:
        result = "DEPTH_LOCKED"
    elif width_locked and not depth_growth_allowed:
        result = "WIDTH_LOCKED"
    elif ratio_blocked:
        result = "RATIO_BLOCKED"
    else:
        result = "PASS"

    if depth_growth_allowed:
        transition = "DEPTH_INCREASE"
    elif width_growth_allowed:
        transition = "WIDTH_INCREASE"
    elif bending_still_fails:
        transition = "NO_VALID_STRATEGY"
    else:
        transition = "GEOMETRY_SANITY_TERMINAL_PASS"

    evidence = {
        "case": name,
        "family_id": str(family_identity().get("family_id") or ""),
        "beam_depth": float(beam_depth),
        "beam_width": float(beam_width),
        "depth_width_ratio": round(float(ratio), 6) if ratio is not None else None,
        "max_allowed_ratio_from_contract": max_ratio,
        "ratio_rule_source": str(CONTRACT_PATH),
        "geometry_locked": bool(geometry_locked),
        "depth_locked": bool(depth_locked),
        "width_locked": bool(width_locked),
        "bending_still_fails": bool(bending_still_fails),
        "depth_growth_allowed": bool(depth_growth_allowed),
        "width_growth_allowed": bool(width_growth_allowed),
        "geometry_sanity_result": result,
        "transition": transition,
        "transition_evidence": {
            "to_DEPTH_INCREASE": transition == "DEPTH_INCREASE",
            "to_WIDTH_INCREASE": transition == "WIDTH_INCREASE",
            "to_NO_VALID_STRATEGY": transition == "NO_VALID_STRATEGY",
            "depth_blocked_by_ratio": bool(ratio_blocked),
            "depth_blocked_by_lock": bool(depth_locked or geometry_locked),
            "width_blocked_by_lock": bool(width_locked or geometry_locked),
        },
    }
    evidence["geometry_sanity_hash"] = _stable_hash(evidence)
    evidence["forbidden_fields_present"] = sorted(_walk_forbidden(evidence))
    return evidence


def _assert_snapshot(snapshot: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    lane = dict(snapshot.get("geometry_sanity_lane_definition") or {})
    if str(lane.get("lane_id") or "") != "geometry_sanity":
        failures.append("geometry_sanity_lane_missing")
    if int(lane.get("lane_index") if lane.get("lane_index") is not None else -1) != 0:
        failures.append("geometry_sanity_not_first_lane")
    if not snapshot.get("contract_loaded_ratio_rule"):
        failures.append("ratio_rule_not_loaded_from_contract")
    ratio_rule = dict(snapshot.get("depth_width_rule") or {})
    if float(ratio_rule.get("maximum_preferred_ratio") or 0.0) != 2.0:
        failures.append("max_ratio_not_2_0_from_contract")

    cases = {str(case.get("case") or ""): dict(case) for case in snapshot.get("cases") or []}
    valid = cases.get("geometry_valid") or {}
    if valid.get("geometry_sanity_result") != "PASS":
        failures.append("geometry_valid_case_not_pass")
    if valid.get("transition") != "DEPTH_INCREASE":
        failures.append("geometry_valid_case_not_transition_depth")
    if valid.get("depth_growth_allowed") is not True:
        failures.append("geometry_valid_case_depth_growth_not_allowed")

    ratio_blocked = cases.get("ratio_blocked") or {}
    if ratio_blocked.get("geometry_sanity_result") != "RATIO_BLOCKED":
        failures.append("ratio_blocked_case_not_ratio_blocked")
    if ratio_blocked.get("depth_growth_allowed") is not False:
        failures.append("ratio_blocked_case_depth_growth_allowed")
    if ratio_blocked.get("transition") != "WIDTH_INCREASE":
        failures.append("ratio_blocked_case_not_transition_width")

    locked = cases.get("geometry_locked") or {}
    if locked.get("geometry_sanity_result") != "GEOMETRY_LOCKED":
        failures.append("geometry_locked_case_not_locked")
    if locked.get("transition") != "NO_VALID_STRATEGY":
        failures.append("geometry_locked_case_not_transition_no_valid")
    if locked.get("depth_growth_allowed") is not False or locked.get("width_growth_allowed") is not False:
        failures.append("geometry_locked_case_growth_allowed")

    for case in cases.values():
        if case.get("forbidden_fields_present"):
            failures.append(
                f"{case.get('case')}:forbidden_fields_present:{','.join(case.get('forbidden_fields_present') or [])}"
            )
        if not case.get("geometry_sanity_hash"):
            failures.append(f"{case.get('case')}:missing_geometry_sanity_hash")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Geometry Sanity Lane Snapshot",
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
        f"- geometry_sanity_lane_definition: `{snapshot.get('geometry_sanity_lane_definition')}`",
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
                f"- depth: `{case.get('beam_depth')}`",
                f"- width: `{case.get('beam_width')}`",
                f"- D/b: `{case.get('depth_width_ratio')}`",
                f"- locked states: geometry=`{case.get('geometry_locked')}`, depth=`{case.get('depth_locked')}`, width=`{case.get('width_locked')}`",
                f"- depth growth allowed: `{case.get('depth_growth_allowed')}`",
                f"- width growth allowed: `{case.get('width_growth_allowed')}`",
                f"- result: `{case.get('geometry_sanity_result')}`",
                f"- transition: `{case.get('transition')}`",
                f"- hash: `{case.get('geometry_sanity_hash')}`",
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
                "PASS: GEOMETRY_SANITY is contract-defined, first in the ladder, and the ratio/lock transition proof is isolated from shared CTA/publication/UI layers."
                if snapshot.get("status") == "PASS"
                else "FAIL: GEOMETRY_SANITY lane proof is not sufficient for migration."
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
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_geometry_sanity_lane_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_geometry_sanity_lane_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    lane = _geometry_lane_definition()
    ratio_rule = depth_width_rule()
    cases = [
        _case(
            name="geometry_valid",
            beam_depth=500.0,
            beam_width=300.0,
            geometry_locked=False,
            depth_locked=False,
            width_locked=False,
        ),
        _case(
            name="ratio_blocked",
            beam_depth=650.0,
            beam_width=300.0,
            geometry_locked=False,
            depth_locked=False,
            width_locked=False,
        ),
        _case(
            name="geometry_locked",
            beam_depth=650.0,
            beam_width=300.0,
            geometry_locked=True,
            depth_locked=True,
            width_locked=True,
        ),
    ]
    snapshot = {
        "schema": "bending_fail_governs_geometry_sanity_lane_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_id": str(family_identity().get("family_id") or ""),
        "contract_ladder_order": _contract_ladder_order(),
        "contract_loaded_ratio_rule": bool(ratio_rule),
        "depth_width_rule": ratio_rule,
        "geometry_sanity_lane_definition": lane,
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
            "depth_width_rule": snapshot["depth_width_rule"],
            "geometry_sanity_lane_definition": snapshot["geometry_sanity_lane_definition"],
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
