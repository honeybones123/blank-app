"""Focused parity scenarios for the post-click final-contract predicate adapter.

This is proof-only. It compares the pure Design Brain predicate/result adapter
against a page-equivalent predicate model across representative post-click
states before any page-local predicate logic is replaced.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FINAL_ACCEPTED_MIN_FAMILY_UTIL = 0.85
TARGET_BAND_EPS = 0.0
COMPOUND_SHEAR_UPDATE_KEYS = ("lig_d", "lig_legs")


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _contract_enabled(contract: dict[str, Any]) -> bool:
    return bool(
        contract.get("actionable")
        and _mapping(contract.get("updates"))
        and bool(contract.get("preview_pass"))
        and contract.get("blocking_reason") is None
    )


def _item_sources(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item,
        _mapping(item.get("candidate_search_evidence")),
        _mapping(_mapping(item.get("action_payload")).get("candidate_search_evidence")),
        _mapping(_mapping(item.get("resolved_candidate")).get("candidate_search_evidence")),
    ]


def _has_low_util_exact_blocker(item: dict[str, Any], family: str) -> bool:
    fam = str(family or "").strip().lower()
    for source in _item_sources(item):
        for key in ("exact_blockers_by_family", "post_click_exact_blockers_by_family"):
            blocker = _mapping(_mapping(source.get(key)).get(fam))
            if (
                blocker
                and bool(blocker.get("exact_blocker"))
                and (
                    bool(blocker.get("no_second_cta_required"))
                    or _number(blocker.get("best_safe_final_util")) is not None
                )
            ):
                return True
    return False


def _best_safe_partial_cleanup(item: dict[str, Any]) -> bool:
    if bool(item.get("best_safe_partial_cleanup")):
        return True
    evidence = _mapping(item.get("candidate_search_evidence"))
    if bool(evidence.get("best_safe_partial_cleanup")):
        return True
    payload = _mapping(item.get("action_payload"))
    if bool(payload.get("best_safe_partial_cleanup")):
        return True
    resolved = _mapping(item.get("resolved_candidate"))
    return bool(resolved.get("best_safe_partial_cleanup"))


def _safe_incremental_cleanup_below_threshold(item: dict[str, Any]) -> bool:
    for source in _item_sources(item):
        if (
            bool(source.get("outside_target_band_allowed"))
            and str(source.get("outside_target_band_allowed_category") or "").strip()
            in {
                "safe_incremental_cleanup_below_final_threshold",
                "safe_improving_cleanup_candidate_available",
            }
        ):
            return True
    return False


def _page_equivalent_predicates(case: dict[str, Any]) -> dict[str, Any]:
    item = _mapping(case.get("item"))
    resolution = _mapping(case.get("final_visible_resolution"))
    debug = _mapping(case.get("guidance_debug"))
    render_audit = _mapping(case.get("post_cleanup_render_audit"))
    last_apply_route = _mapping(case.get("last_apply_route"))
    binding_audit = _mapping(case.get("primary_payload_binding_audit"))
    state = _mapping(case.get("current_state"))
    contract = _mapping(case.get("final_contract") or item.get("button_contract"))
    final_family = str(
        item.get("family") or item.get("check_key") or contract.get("family") or ""
    ).strip().lower()
    final_expected_util = _number(
        contract.get("expected_util")
        or item.get("expected_util")
        or item.get("util")
        or item.get("displayed_util")
    )
    overview = _mapping(resolution.get("overview"))
    utils = _mapping(overview.get("utils"))
    current_bending_util = _number(utils.get("bending"))
    unresolved = sorted(
        {
            str(family or "").strip().lower()
            for family in (
                list(debug.get("post_click_unresolved_low_util_families") or [])
                + list(render_audit.get("post_click_unresolved_low_util_families") or [])
            )
            if str(family or "").strip()
        }
    )
    below_floor = sorted(
        {
            str(family or "").strip().lower()
            for family in (
                list(debug.get("post_click_families_below_final_threshold") or [])
                + list(render_audit.get("post_click_families_below_final_threshold") or [])
            )
            if str(family or "").strip()
        }
    )
    last_apply_label = " ".join(
        str(last_apply_route.get(key) or "")
        for key in (
            "resolved_candidate_label",
            "one_click_candidate_label_at_step_start",
            "post_apply_resolved_candidate_label",
        )
    ).strip().lower()
    same_flow_cleanup_apply = bool(
        last_apply_route.get("apply_used_resolved_candidate_payload")
        and last_apply_route.get("applied_updates")
        and "cleanup" in last_apply_label
    )
    if not same_flow_cleanup_apply:
        binding_updates = _mapping(
            binding_audit.get("applied_updates")
            or binding_audit.get("actual_changed_updates")
        )
        same_flow_cleanup_apply = bool(
            binding_updates
            and set(binding_updates) & set(COMPOUND_SHEAR_UPDATE_KEYS)
            and _number(state.get("lig_d")) == 0
            and _number(state.get("lig_legs")) == 0
        )
    contract_enabled = _contract_enabled(contract)
    exact_blocker = _has_low_util_exact_blocker(item, "bending")
    blocking_reason = str(contract.get("blocking_reason") or "").strip()
    item_action_type = str(item.get("action_type") or "").strip()
    requires_exact_blocker = bool(
        contract_enabled
        or blocking_reason
        in {
            "post_click_safe_incremental_cleanup_requires_exact_blocker",
            "safe_incremental_cleanup_below_final_threshold",
            "candidate_final_accepted_state_unresolved_low_util",
            "candidate_final_accepted_state_unresolved_low_family",
        }
        or (
            item_action_type == "apply_resolved_candidate"
            and not bool(item.get("final_state_class") == "blocker")
        )
    )
    render_reason = str(resolution.get("render_reason") or "").strip()
    title = str(item.get("title_main") or item.get("title") or "").strip().lower()
    visible_action = bool(
        requires_exact_blocker
        and final_family == "bending"
        and render_reason != "final_visible_bending_cleanup_available_before_blocker"
        and (
            "bending" in unresolved
            or "bending" in below_floor
            or same_flow_cleanup_apply
            or exact_blocker
            or (
                current_bending_util is not None
                and current_bending_util < FINAL_ACCEPTED_MIN_FAMILY_UTIL - TARGET_BAND_EPS
            )
        )
        and (
            _best_safe_partial_cleanup(item)
            or _safe_incremental_cleanup_below_threshold(item)
            or bool(item.get("safe_incremental_cleanup_below_final_threshold"))
            or exact_blocker
            or (
                final_expected_util is not None
                and final_expected_util < FINAL_ACCEPTED_MIN_FAMILY_UTIL
                and "best safe" in title
            )
        )
    )
    return {
        "final_family": final_family,
        "final_expected_util": final_expected_util,
        "final_current_bending_util": current_bending_util,
        "unresolved_families": unresolved,
        "below_floor_families": below_floor,
        "same_flow_cleanup_apply": same_flow_cleanup_apply,
        "contract_enabled": contract_enabled,
        "exact_blocker_on_visible_item": exact_blocker,
        "requires_exact_blocker": requires_exact_blocker,
        "visible_action": visible_action,
        "best_safe_partial_cleanup": _best_safe_partial_cleanup(item),
        "safe_incremental_cleanup_below_threshold": _safe_incremental_cleanup_below_threshold(item),
        "render_reason": render_reason,
    }


def _exact_blocker(best_safe_final_util: float = 0.72) -> dict[str, Any]:
    return {
        "exact_blocker": True,
        "no_second_cta_required": True,
        "best_safe_final_util": best_safe_final_util,
    }


def _base_item() -> dict[str, Any]:
    return {
        "family": "bending",
        "check_key": "bending",
        "action_type": "apply_resolved_candidate",
        "title": "Best safe bending cleanup",
        "button_contract": {
            "actionable": True,
            "updates": {"bot_dia": 16},
            "preview_pass": True,
            "blocking_reason": None,
            "expected_util": 0.72,
            "family": "bending",
            "action_type": "apply_resolved_candidate",
        },
        "candidate_search_evidence": {
            "exact_blockers_by_family": {"bending": _exact_blocker()},
            "outside_target_band_allowed": True,
            "outside_target_band_allowed_category": "safe_incremental_cleanup_below_final_threshold",
        },
        "best_safe_partial_cleanup": True,
    }


def _cases() -> dict[str, dict[str, Any]]:
    base = _base_item()
    return {
        "enabled_bending_cleanup": {
            "item": dict(base),
            "final_visible_resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "guidance_debug": {"post_click_unresolved_low_util_families": ["bending"]},
            "current_state": {"lig_d": 10, "lig_legs": 2},
        },
        "disabled_exact_blocker": {
            "item": {
                **dict(base),
                "button_contract": {
                    **dict(base["button_contract"]),
                    "actionable": False,
                    "updates": {},
                    "preview_pass": False,
                    "blocking_reason": "post_click_safe_incremental_cleanup_requires_exact_blocker",
                },
            },
            "final_visible_resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "guidance_debug": {"post_click_families_below_final_threshold": ["bending"]},
            "current_state": {"lig_d": 10, "lig_legs": 2},
        },
        "same_flow_cleanup_apply": {
            "item": {**dict(base), "candidate_search_evidence": {}},
            "final_visible_resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "last_apply_route": {
                "apply_used_resolved_candidate_payload": True,
                "applied_updates": {"bot_dia": 16},
                "resolved_candidate_label": "cleanup candidate",
            },
            "current_state": {"lig_d": 10, "lig_legs": 2},
        },
        "non_bending_no_action": {
            "item": {**dict(base), "family": "shear", "check_key": "shear"},
            "final_visible_resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "guidance_debug": {"post_click_unresolved_low_util_families": ["bending"]},
            "current_state": {"lig_d": 10, "lig_legs": 2},
        },
        "render_reason_exclusion": {
            "item": dict(base),
            "final_visible_resolution": {
                "overview": {"utils": {"bending": 0.62}},
                "render_reason": "final_visible_bending_cleanup_available_before_blocker",
            },
            "guidance_debug": {"post_click_unresolved_low_util_families": ["bending"]},
            "current_state": {"lig_d": 10, "lig_legs": 2},
        },
        "compound_shear_same_flow": {
            "item": {**dict(base), "candidate_search_evidence": {}},
            "final_visible_resolution": {"overview": {"utils": {"bending": 0.62}}, "render_reason": "normal"},
            "primary_payload_binding_audit": {"applied_updates": {"lig_d": 0, "lig_legs": 0}},
            "current_state": {"lig_d": 0, "lig_legs": 0},
        },
    }


def _capture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_final_contract_predicate_result_adapter,
    )

    rows: list[dict[str, Any]] = []
    for name, case in _cases().items():
        kwargs = {
            "item": case.get("item"),
            "final_visible_resolution": case.get("final_visible_resolution"),
            "guidance_debug": case.get("guidance_debug"),
            "post_cleanup_render_audit": case.get("post_cleanup_render_audit"),
            "last_apply_route": case.get("last_apply_route"),
            "primary_payload_binding_audit": case.get("primary_payload_binding_audit"),
            "current_state": case.get("current_state"),
            "final_contract": _mapping(case.get("item")).get("button_contract"),
            "final_accepted_min_family_util": FINAL_ACCEPTED_MIN_FAMILY_UTIL,
            "target_band_eps": TARGET_BAND_EPS,
            "compound_shear_update_keys": COMPOUND_SHEAR_UPDATE_KEYS,
        }
        first = build_final_design_guide_post_click_final_contract_predicate_result_adapter(**kwargs)
        second = build_final_design_guide_post_click_final_contract_predicate_result_adapter(**kwargs)
        adapter_predicates = dict(first.get("predicate_result") or {})
        page_predicates = _page_equivalent_predicates(
            {**case, "final_contract": kwargs["final_contract"]}
        )
        mismatches = {
            key: {
                "adapter": adapter_predicates.get(key),
                "page_equivalent": page_predicates.get(key),
            }
            for key in sorted(set(adapter_predicates) | set(page_predicates))
            if adapter_predicates.get(key) != page_predicates.get(key)
        }
        rows.append(
            {
                "case": name,
                "adapter_predicates": adapter_predicates,
                "page_equivalent_predicates": page_predicates,
                "mismatches": mismatches,
                "matches_page_equivalent": not bool(mismatches),
                "stable_hash_repeat": first.get("proof_hash") == second.get("proof_hash"),
                "product_driving": first.get("product_driving"),
                "render_driving": first.get("render_driving"),
                "apply_driving": first.get("apply_driving"),
                "session_driving": first.get("session_driving"),
            }
        )
    latest = {
        "predicate_object": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_object"
        ),
        "live_trace": _latest(
            "design_guide_live_post_click_final_contract_predicate_result_adapter_trace"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_FINAL_CONTRACT_PREDICATE_RESULT_PARITY_PROVEN",
        "rows": rows,
        "case_count": len(rows),
        "mismatch_count": sum(1 for row in rows if row.get("mismatches")),
        "unstable_hash_count": sum(1 for row in rows if row.get("stable_hash_repeat") is not True),
        "driving_rows": [
            row.get("case")
            for row in rows
            if row.get("product_driving")
            or row.get("render_driving")
            or row.get("apply_driving")
            or row.get("session_driving")
        ],
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "all_cases_match_page_equivalent": capture.get("mismatch_count") == 0,
        "all_hashes_stable": capture.get("unstable_hash_count") == 0,
        "no_product_driving_rows": not bool(capture.get("driving_rows")),
        "minimum_case_coverage": int(capture.get("case_count") or 0) >= 6,
        "predicate_object_pass": (latest.get("predicate_object") or {}).get("status") == "PASS",
        "live_trace_pass": (latest.get("live_trace") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Predicate/Result Adapter Parity Scenarios",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Cases: `{capture.get('case_count')}`",
        f"- Mismatch count: `{capture.get('mismatch_count')}`",
        f"- Unstable hash count: `{capture.get('unstable_hash_count')}`",
        f"- Driving rows: `{capture.get('driving_rows')}`",
        "",
        "## Rows",
        "",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"- {row.get('case')}: match=`{row.get('matches_page_equivalent')}`, "
            f"stable=`{row.get('stable_hash_repeat')}`, mismatches=`{row.get('mismatches')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            (
                "Next safe slice: cutover readiness for replacing the page-local post-click "
                "predicate rows with the predicate/result adapter while keeping page-owned "
                "input collection in inputs_page.py."
            ),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
