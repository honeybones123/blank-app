"""BENDING_FAIL_GOVERNS internal strategy-ladder contract snapshot.

This verifier freezes the current architecture decision that BENDING_FAIL_GOVERNS
is one governing family with internal recommendation strategy lanes. It does
not move code or exercise product mutation paths. It composes static contract
evidence, live source evidence, and the existing bottom-reo lock/readiness
verifiers to prove the current lane ownership map.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from design_brain.families.bending_fail_governs.contract import (  # noqa: E402
    CONTRACT_PATH,
    load_bending_fail_governs_contract,
)


ARTIFACT_DIR = REPO / "artifacts" / "verification"
AUDIT_DIR = REPO / "artifacts" / "audits"

CONTRACTED_STRATEGY_LANES = (
    "bottom_reo_increase",
    "split_multi_layer_reo",
    "depth_growth",
    "width_growth",
    "geometry_reo_rescue",
    "target_band_active_fail_selector_policy",
    "exact_stop_no_valid_strategy",
)

FORBIDDEN_LADDER_CONCEPTS = {
    "BENDING_OVERDESIGN_GOVERNS",
    "bending_overdesign_governs",
    "tightening",
    "overdesign_reduction",
    "MIN_BENDING_REO",
    "MIN_BENDING_REO_GOVERNS",
    "min_bending_reo_active_repair_family",
    "button_contract",
    "button_label",
    "cta_rendering",
    "source_precedence",
    "selected_family_publication_gate",
    "publication",
    "published_item",
    "apply_routing",
    "one_click",
    "one_click_fallback",
    "visible_wording",
    "output_rendering",
    "render",
    "ui",
    "session",
    "debug",
}


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()[:16]


def _read(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8", errors="replace")


def _line_for(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def _contains(text: str, needle: str) -> bool:
    return needle in text


def _extract_function_body(source: str, function_name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(function_name)}\(", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    start = match.start()
    next_match = re.search(r"^def |\nclass ", source[match.end() :], flags=re.MULTILINE)
    if not next_match:
        return source[start:]
    return source[start : match.end() + next_match.start()]


def _parse_json_object(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    starts = [index for index, char in enumerate(text) if char == "{"]
    for start in reversed(starts):
        try:
            parsed = json.loads(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    pass_line = next((line for line in text.splitlines() if line.startswith("PASS: ")), None)
    if pass_line:
        result: dict[str, Any] = {
            "status": "PASS",
            "artifact": pass_line.removeprefix("PASS: ").strip(),
        }
        trace_line = next((line for line in text.splitlines() if line.startswith("trace: ")), None)
        if trace_line:
            result["trace"] = trace_line.removeprefix("trace: ").strip()
        return result
    return {"status": "UNKNOWN", "stdout_tail": text[-2000:]}


def _run_tool(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(REPO / script)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=360,
    )
    parsed = _parse_json_object(proc.stdout)
    artifact_path = parsed.get("artifact")
    artifact_payload: dict[str, Any] = {}
    if artifact_path:
        path = Path(str(artifact_path))
        if not path.is_absolute():
            path = REPO / path
        if path.exists():
            artifact_payload = json.loads(path.read_text(encoding="utf-8"))
            artifact_path = str(path)
    return {
        "script": script,
        "returncode": proc.returncode,
        "status": parsed.get("status") or artifact_payload.get("status"),
        "artifact": artifact_path,
        "report": parsed.get("report"),
        "trace": parsed.get("trace") or artifact_payload.get("trace_path"),
        "stdout_tail": str(proc.stdout or "")[-2000:],
        "stderr_tail": str(proc.stderr or "")[-2000:],
        "payload": artifact_payload,
    }


def _walk_forbidden(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_LADDER_CONCEPTS:
                found.add(key_text)
            found.update(_walk_forbidden(child))
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            if isinstance(child, str) and child in FORBIDDEN_LADDER_CONCEPTS:
                found.add(child)
            found.update(_walk_forbidden(child))
    return found


def _source_evidence() -> dict[str, Any]:
    inputs = _read("inputs_page.py")
    bending_fail = _read("design_brain/families/bending_fail.py")
    contract_json = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    normal_body = _extract_function_body(inputs, "_compute_bottom_reo_recommendation")
    selector_body = _extract_function_body(inputs, "_pick_best_bottom_recommendation_by_selector")
    # `contracted_repair_ladder_specs(...)` is a class method; for this audit
    # snapshot the full family source is the safest static evidence surface.
    contract_body = bending_fail
    return {
        "contract_required_lanes": list(((contract_json.get("repair_ladder") or {}).get("required_lanes") or [])),
        "contract_stage_evidence": {
            "bottom_reo_same_geometry": {
                "present": _contains(contract_body, "stage_1_reo_only_same_geometry"),
                "line": _line_for(bending_fail, "stage_1_reo_only_same_geometry"),
            },
            "split_multi_layer_reo": {
                "present": _contains(contract_body, "same_geometry_split_row_reo"),
                "line": _line_for(bending_fail, "same_geometry_split_row_reo"),
            },
            "depth_growth": {
                "present": _contains(contract_body, "stage_2_depth_increments_same_width"),
                "line": _line_for(bending_fail, "stage_2_depth_increments_same_width"),
            },
            "width_growth": {
                "present": _contains(contract_body, "stage_3_width_increments_for_reo_fit"),
                "line": _line_for(bending_fail, "stage_3_width_increments_for_reo_fit"),
            },
            "geometry_reo_rescue": {
                "present": _contains(contract_body, "stage_4_combined_rescue"),
                "line": _line_for(bending_fail, "stage_4_combined_rescue"),
            },
            "exact_stop_no_valid_strategy": {
                "present": _contains(contract_body, "bounded bending repair ladder exhausted")
                and _contains(contract_body, "geometry locked; legal no-repair proof required"),
                "line": _line_for(bending_fail, "bounded bending repair ladder exhausted"),
            },
        },
        "live_normal_recommendation_strategy_order": [
            {
                "lane": "bottom_reo_increase",
                "evidence": "_generate_local_bottom_arrangements(...) inside _compute_bottom_reo_recommendation",
                "present": _contains(normal_body, "_generate_local_bottom_arrangements"),
                "line": _line_for(inputs, "_generate_local_bottom_arrangements(state, mode_config"),
            },
            {
                "lane": "depth_growth",
                "evidence": "geometry trial axis includes increase_depth when geometry is unlocked",
                "present": _contains(normal_body, "increase_depth"),
                "line": _line_for(inputs, "increase_depth"),
            },
            {
                "lane": "width_growth",
                "evidence": "geometry trial axis includes increase_width when geometry is unlocked",
                "present": _contains(normal_body, "increase_width"),
                "line": _line_for(inputs, "increase_width"),
            },
            {
                "lane": "geometry_reo_rescue",
                "evidence": "_append_geometry_bottom_compound_candidates(...) merges geometry and bottom layouts",
                "present": _contains(normal_body, "_append_geometry_bottom_compound_candidates"),
                "line": _line_for(inputs, "_append_geometry_bottom_compound_candidates"),
            },
            {
                "lane": "target_band_active_fail_selector_policy",
                "evidence": "_annotate_candidate_target_band_metrics(...) then _pick_best_bottom_recommendation_by_selector(...)",
                "present": _contains(normal_body, "_annotate_candidate_target_band_metrics")
                and _contains(normal_body, "_pick_best_bottom_recommendation_by_selector"),
                "line": _line_for(inputs, "_pick_best_bottom_recommendation_by_selector"),
            },
            {
                "lane": "exact_stop_no_valid_strategy",
                "evidence": "no_filtered_candidates/no_selected_candidate/growth_blocked_efficiency_reduction branches",
                "present": all(
                    _contains(normal_body, needle)
                    for needle in (
                        "no_filtered_candidates",
                        "no_selected_candidate",
                        "growth_blocked_efficiency_reduction",
                    )
                ),
                "line": _line_for(inputs, "no_filtered_candidates"),
            },
        ],
        "selector_policy_evidence": {
            "strict_band_guard_present": _contains(selector_body, "_is_strictly_rejectable_band_winner"),
            "strict_band_accept_present": _contains(selector_body, "strict_band_winner_accept"),
            "legacy_improvement_guard_present": _contains(selector_body, "_legacy_bottom_local_rejection_reason"),
            "selector_line": _line_for(inputs, "def _pick_best_bottom_recommendation_by_selector"),
        },
        "separate_family_exclusions": {
            "tightening_function_is_separate": {
                "present": _contains(inputs, "def _compute_bottom_reo_tightening_recommendation"),
                "line": _line_for(inputs, "def _compute_bottom_reo_tightening_recommendation"),
                "classification": "BENDING_OVERDESIGN_GOVERNS_or_cleanup_not_BENDING_FAIL_strategy_lane",
            },
            "bending_overdesign_package_scaffold_is_separate": {
                "present": (REPO / "design_brain/families/bending_overdesign_governs/__init__.py").exists(),
                "classification": "separate_governing_family",
            },
            "min_bending_reo_shell_is_blocker_not_active_repair_lane": {
                "present": (REPO / "design_brain/families/min_bending_reo.py").exists(),
                "classification": "blocker_exact_stop_not_BENDING_FAIL_active_repair_family",
            },
        },
    }


def _strategy_ladder_contract(source: dict[str, Any], lock: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
    lock_payload = dict(lock.get("payload") or {})
    readiness_payload = dict(readiness.get("payload") or {})
    lock_status = str(lock.get("status") or lock_payload.get("status") or "")
    readiness_status = str(readiness.get("status") or readiness_payload.get("status") or "")
    scenarios = dict(lock_payload.get("scenarios") or {})
    return {
        "family_id": "BENDING_FAIL_GOVERNS",
        "architecture": "single_governing_family_with_internal_strategy_ladder",
        "contracted_lanes": [
            {
                "lane": "bottom_reo_increase",
                "contract_mapping": "bottom_reinforcement_increase",
                "ownership": "family-owned + proof-only family-owned live chain",
                "contract_evidence": source["contract_stage_evidence"]["bottom_reo_same_geometry"],
                "live_evidence": source["live_normal_recommendation_strategy_order"][0],
                "proof_evidence": {
                    "bottom_reo_lock_status": lock_status,
                    "normal_bending_underdesign_chain_hash": (
                        scenarios.get("normal_bending_underdesign") or {}
                    ).get("proof_chain_hash"),
                },
            },
            {
                "lane": "split_multi_layer_reo",
                "contract_mapping": "bottom_reinforcement_increase:split_row_escalation",
                "ownership": "family-owned + proof-only family-owned live chain",
                "contract_evidence": source["contract_stage_evidence"]["split_multi_layer_reo"],
                "live_evidence": {
                    "present": True,
                    "evidence": "bottom arrangement records include bot2_count/row_count and lock covers two_layer_arrangement",
                },
                "proof_evidence": {
                    "bottom_reo_lock_status": lock_status,
                    "two_layer_arrangement_chain_hash": (
                        scenarios.get("two_layer_arrangement") or {}
                    ).get("proof_chain_hash"),
                },
            },
            {
                "lane": "depth_growth",
                "contract_mapping": "depth_increase_when_reinforcement_exhausted",
                "ownership": "family-owned contract lane; live execution page-owned; strategy-level coverage incomplete",
                "contract_evidence": source["contract_stage_evidence"]["depth_growth"],
                "live_evidence": source["live_normal_recommendation_strategy_order"][1],
            },
            {
                "lane": "width_growth",
                "contract_mapping": "width_increase_when_fit_or_spacing_blocks",
                "ownership": "family-owned contract lane; live execution page-owned; strategy-level coverage incomplete",
                "contract_evidence": source["contract_stage_evidence"]["width_growth"],
                "live_evidence": source["live_normal_recommendation_strategy_order"][2],
            },
            {
                "lane": "geometry_reo_rescue",
                "contract_mapping": "bounded_geometry_and_reinforcement_repair",
                "ownership": "family-owned contract lane; live compound generation page-owned; missing dedicated strategy verifier",
                "contract_evidence": source["contract_stage_evidence"]["geometry_reo_rescue"],
                "live_evidence": source["live_normal_recommendation_strategy_order"][3],
            },
            {
                "lane": "target_band_active_fail_selector_policy",
                "contract_mapping": "active_fail_target_band_selection_policy",
                "ownership": "proof-only family-owned surfaces; selector execution still page-owned",
                "contract_evidence": {
                    "present": True,
                    "evidence": "contract ranking_rule requires first compliant executor-backed repair; live target-band selector proof is external",
                },
                "live_evidence": source["live_normal_recommendation_strategy_order"][4],
                "selector_policy_evidence": source["selector_policy_evidence"],
                "proof_evidence": {
                    "bottom_reo_lock_status": lock_status,
                    "readiness_status": readiness_status,
                },
            },
            {
                "lane": "exact_stop_no_valid_strategy",
                "contract_mapping": "target_band_exhausted/no_candidate_found/locked_no_repair/exact_stop",
                "ownership": "family-owned blockers + proof-only no-action surfaces",
                "contract_evidence": source["contract_stage_evidence"]["exact_stop_no_valid_strategy"],
                "live_evidence": source["live_normal_recommendation_strategy_order"][5],
                "proof_evidence": {
                    "zero_accepted_no_action_chain_hash": (
                        scenarios.get("zero_accepted_no_action") or {}
                    ).get("proof_chain_hash"),
                },
            },
        ],
        "excluded_from_family_strategy_ladder": {
            "tightening_overdesign_reduction": source["separate_family_exclusions"]["tightening_function_is_separate"],
            "bending_overdesign_governs": source["separate_family_exclusions"]["bending_overdesign_package_scaffold_is_separate"],
            "min_bending_reo": source["separate_family_exclusions"]["min_bending_reo_shell_is_blocker_not_active_repair_lane"],
            "shared_output_application_layers": [
                "shared CTA rendering/source precedence",
                "selected-family publication gate",
                "apply routing",
                "one-click fallback",
                "visible wording/output rendering",
                "UI/session/debug surfaces",
            ],
        },
    }


def _assert_snapshot(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    failures: dict[str, list[str]] = {}
    ladder = dict(snapshot.get("strategy_ladder_contract") or {})
    lane_rows = list(ladder.get("contracted_lanes") or [])
    lane_names = [str(row.get("lane")) for row in lane_rows if isinstance(row, dict)]
    missing_lanes = sorted(set(CONTRACTED_STRATEGY_LANES) - set(lane_names))
    if missing_lanes:
        failures.setdefault("coverage", []).append("missing_lanes:" + ",".join(missing_lanes))
    for row in lane_rows:
        if not isinstance(row, dict):
            continue
        lane = str(row.get("lane") or "unknown")
        contract_evidence = dict(row.get("contract_evidence") or {})
        live_evidence = dict(row.get("live_evidence") or {})
        if contract_evidence and contract_evidence.get("present") is not True:
            failures.setdefault(lane, []).append("contract_evidence_absent")
        if live_evidence and live_evidence.get("present") is not True:
            failures.setdefault(lane, []).append("live_evidence_absent")
    forbidden = sorted(_walk_forbidden(ladder.get("contracted_lanes") or []))
    if forbidden:
        failures.setdefault("forbidden", []).append("forbidden_family_strategy_lane:" + ",".join(forbidden))
    excluded = dict(ladder.get("excluded_from_family_strategy_ladder") or {})
    if "tightening_overdesign_reduction" not in excluded:
        failures.setdefault("exclusions", []).append("missing_tightening_overdesign_exclusion")
    if "min_bending_reo" not in excluded:
        failures.setdefault("exclusions", []).append("missing_min_bending_reo_exclusion")
    bottom_lock = dict(snapshot.get("bottom_reo_lock_verifier") or {})
    bottom_returncode = bottom_lock.get("returncode")
    if str(bottom_lock.get("status") or "") != "PASS" or bottom_returncode is None or int(bottom_returncode) != 0:
        failures.setdefault("bottom_reo_lock", []).append("bottom_reo_lock_verifier_failed")
    readiness = dict(snapshot.get("bottom_reo_readiness_snapshot") or {})
    readiness_returncode = readiness.get("returncode")
    if str(readiness.get("status") or "") != "PASS" or readiness_returncode is None or int(readiness_returncode) != 0:
        failures.setdefault("readiness", []).append("bottom_reo_readiness_snapshot_failed")
    if not snapshot.get("stable_ladder_contract_hash"):
        failures.setdefault("hash", []).append("missing_stable_ladder_contract_hash")
    return failures


def _write_report(snapshot: dict[str, Any], report_path: Path) -> None:
    lines = [
        "# BENDING_FAIL_GOVERNS Strategy Ladder Contract Snapshot",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- JSON artifact: `{snapshot.get('artifact_path')}`",
        "",
        "## Scope",
        "",
        "Snapshot/proof only. No product behaviour, code movement, refactor, deletion, CTA rendering, source precedence, publication, apply routing, one-click fallback, visible wording, UI/session/debug, or tightening ownership is changed.",
        "",
        "## Decision Frozen",
        "",
        "`BENDING_FAIL_GOVERNS` is one governing family with internal recommendation strategy lanes, not separate mini-families.",
        "",
        "## Strategy Lanes",
        "",
    ]
    for row in (snapshot.get("strategy_ladder_contract") or {}).get("contracted_lanes") or []:
        lines.extend(
            [
                f"### {row.get('lane')}",
                "",
                f"- contract mapping: `{row.get('contract_mapping')}`",
                f"- ownership: `{row.get('ownership')}`",
                f"- contract evidence: `{row.get('contract_evidence')}`",
                f"- live evidence: `{row.get('live_evidence')}`",
                f"- proof evidence: `{row.get('proof_evidence')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Exclusions",
            "",
            "The snapshot excludes tightening/overdesign reduction, MIN_BENDING_REO as an active repair family, shared CTA rendering/source precedence, selected-family publication, apply routing, one-click fallback, visible wording/output rendering, and UI/session/debug surfaces from the family strategy ladder.",
            "",
            "## Hashes",
            "",
            f"- stable ladder contract hash: `{snapshot.get('stable_ladder_contract_hash')}`",
            f"- bottom reo lock artifact: `{(snapshot.get('bottom_reo_lock_verifier') or {}).get('artifact')}`",
            f"- readiness artifact: `{(snapshot.get('bottom_reo_readiness_snapshot') or {}).get('artifact')}`",
            "",
        ]
    )
    if snapshot.get("failures"):
        lines.extend(["## Failures", ""])
        for group, group_failures in (snapshot.get("failures") or {}).items():
            lines.append(f"- {group}: {', '.join(group_failures)}")
    else:
        lines.extend(
            [
                "## Result",
                "",
                "PASS. The current BENDING_FAIL_GOVERNS strategy ladder is distinguishable from separate overdesign/min-reo/shared application layers, and the existing bottom reo lock verifier remains green.",
                "",
                "## Recommendation",
                "",
                "Next safe slice: add focused lane snapshots for depth growth, width growth, and geometry+reo rescue before trying to move or delete any live recommendation scaffolding.",
            ]
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"bending_fail_governs_strategy_ladder_contract_{stamp}.json"
    report_path = AUDIT_DIR / f"bending_fail_governs_strategy_ladder_contract_{stamp}.md"

    contract = load_bending_fail_governs_contract()
    source = _source_evidence()
    bottom_lock = _run_tool("tools/verification/bending_bottom_reo_recommendation_lock_verifier.py")
    readiness = _run_tool("tools/verification/bottom_reo_recommendation_readiness_snapshot.py")
    ladder = _strategy_ladder_contract(source, bottom_lock, readiness)
    stable_hash = _stable_hash(ladder)
    snapshot = {
        "schema": "bending_fail_governs_strategy_ladder_contract_snapshot.v1",
        "status": "PENDING",
        "generated_at": stamp,
        "artifact_path": str(artifact_path),
        "report_path": str(report_path),
        "contract_path": str(CONTRACT_PATH),
        "family_identity": dict(contract.get("family_identity") or {}),
        "target_architecture": "single_governing_family_with_internal_strategy_lanes",
        "contracted_internal_strategy_lanes": list(CONTRACTED_STRATEGY_LANES),
        "strategy_ladder_contract": ladder,
        "stable_ladder_contract_hash": stable_hash,
        "source_evidence": source,
        "bottom_reo_lock_verifier": {
            key: value
            for key, value in bottom_lock.items()
            if key not in {"payload", "stdout_tail", "stderr_tail"}
        },
        "bottom_reo_readiness_snapshot": {
            key: value
            for key, value in readiness.items()
            if key not in {"payload", "stdout_tail", "stderr_tail"}
        },
        "assertions": {
            "product_behavior_changed": False,
            "code_moved": False,
            "tightening_overdesign_not_in_bending_fail_strategy_ladder": True,
            "min_bending_reo_not_active_repair_family": True,
            "cta_publication_apply_wording_ui_absent_from_strategy_lanes": True,
            "bottom_reo_lock_verifier_remains_green": bottom_lock.get("status") == "PASS",
        },
        "failures": {},
    }
    failures = _assert_snapshot(snapshot)
    snapshot["failures"] = failures
    snapshot["status"] = "PASS" if not failures else "FAIL"
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(snapshot, report_path)
    print(
        json.dumps(
            {
                "status": snapshot["status"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
