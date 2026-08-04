"""FinalDesignGuidePublication memo implementation snapshot.

Verifies the guarded DesignGuideController memo cache is keyed by request_hash,
hits for identical publication-authority requests, and rebuilds for changed,
debug, post-click/apply-in-flight, or missing-publication states.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    DesignGuideControllerRequest,
    run_design_guide_controller_publication_authority,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_LOCKS = {
    "memo_readiness": "design_guide_final_publication_rebuild_memo_readiness",
    "request_key_live_stability": "design_guide_controller_request_key_live_stability",
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "path": None, "snapshot": {}, "passed": False}
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "snapshot": {}, "passed": False, "error": str(exc)}
    return {
        "found": True,
        "path": str(path),
        "snapshot": snapshot,
        "passed": snapshot.get("status") == "PASS",
    }


def _request(**overrides: Any) -> DesignGuideControllerRequest:
    item = {
        "title": "Shear capacity is low",
        "title_main": "Shear capacity is low",
        "status": "FAIL",
        "bucket": "fail",
        "selected_family_id": "SHEAR_FAIL_GOVERNS",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "action_type": "apply_resolved_candidate",
            "label": "Apply repair",
            "updates": {"D": 450, "s_lig": 100},
        },
    }
    debug = {
        "final_publication_cta_hash": "cta-a",
        "final_publication_display_hash": "display-a",
        "final_publication_verifier_payload": {"publication_hash": "publication-a"},
    }
    values = {
        "item": item,
        "debug": debug,
        "design_brain_result": {"selected_family": "SHEAR_FAIL_GOVERNS"},
        "verifier_payload": {"publication_hash": "publication-a"},
                "final_visible_resolution": {},
        "guidance_debug": dict(debug),
        "publication_reason": "sample_publication_reason",
        "source": "memo_implementation_snapshot",
    }
    values.update(overrides)
    return DesignGuideControllerRequest(**values)


def _scenario_rows() -> list[dict[str, Any]]:
    stable = _request()
    first = run_design_guide_controller_publication_authority(stable)
    second = run_design_guide_controller_publication_authority(stable)

    changed_item = dict(stable.item)
    changed_item["title"] = "Bending capacity is low"
    changed_item["title_main"] = "Bending capacity is low"
    changed = run_design_guide_controller_publication_authority(
        _request(item=changed_item)
    )

    debug = dict(stable.debug)
    debug["final_publication_memo_debug_force_rebuild"] = True
    debug_guard = run_design_guide_controller_publication_authority(
        _request(debug=debug, guidance_debug=debug)
    )

    inflight = dict(stable.debug)
    inflight["design_guide_component_apply_in_flight"] = True
    inflight_guard = run_design_guide_controller_publication_authority(
        _request(debug=inflight, guidance_debug=inflight)
    )

    missing = run_design_guide_controller_publication_authority(_request(item={}))

    return [
        {
            "scenario_id": "first_stable_request",
            "memo_cache_hit": first.memo_cache_hit,
            "memo_cache_reason": first.memo_cache_reason,
            "request_hash": first.request_hash,
            "publication_hash": first.publication_hash,
            "expected_hit": False,
            "expected_met": first.memo_cache_hit is False and first.memo_cache_reason == "rebuilt",
        },
        {
            "scenario_id": "second_identical_stable_request",
            "memo_cache_hit": second.memo_cache_hit,
            "memo_cache_reason": second.memo_cache_reason,
            "request_hash": second.request_hash,
            "publication_hash": second.publication_hash,
            "expected_hit": True,
            "expected_met": (
                second.memo_cache_hit is True
                and second.memo_cache_reason == "request_hash_unchanged"
                and second.request_hash == first.request_hash
                and second.publication_hash == first.publication_hash
            ),
        },
        {
            "scenario_id": "changed_request_rebuilds",
            "memo_cache_hit": changed.memo_cache_hit,
            "memo_cache_reason": changed.memo_cache_reason,
            "request_hash": changed.request_hash,
            "publication_hash": changed.publication_hash,
            "expected_hit": False,
            "expected_met": changed.memo_cache_hit is False and changed.request_hash != first.request_hash,
        },
        {
            "scenario_id": "debug_force_rebuild",
            "memo_cache_hit": debug_guard.memo_cache_hit,
            "memo_cache_reason": debug_guard.memo_cache_reason,
            "request_hash": debug_guard.request_hash,
            "publication_hash": debug_guard.publication_hash,
            "expected_hit": False,
            "expected_met": (
                debug_guard.memo_cache_hit is False
                and debug_guard.memo_cache_reason == "debug_force_rebuild"
            ),
        },
        {
            "scenario_id": "post_click_apply_in_flight_rebuild",
            "memo_cache_hit": inflight_guard.memo_cache_hit,
            "memo_cache_reason": inflight_guard.memo_cache_reason,
            "request_hash": inflight_guard.request_hash,
            "publication_hash": inflight_guard.publication_hash,
            "expected_hit": False,
            "expected_met": (
                inflight_guard.memo_cache_hit is False
                and inflight_guard.memo_cache_reason == "post_click_or_apply_in_flight"
            ),
        },
        {
            "scenario_id": "missing_publication_item_rebuild",
            "memo_cache_hit": missing.memo_cache_hit,
            "memo_cache_reason": missing.memo_cache_reason,
            "request_hash": missing.request_hash,
            "publication_hash": missing.publication_hash,
            "expected_hit": False,
            "expected_met": (
                missing.memo_cache_hit is False
                and missing.memo_cache_reason == "missing_publication_item"
            ),
        },
    ]


def _source_checks() -> dict[str, bool]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    return {
        "memo_cache_exists_in_controller": all(
            token in controller_source
            for token in (
                "_final_publication_memo_cache",
                "_FINAL_PUBLICATION_MEMO_CACHE_MAX",
                "_design_guide_controller_memo_disabled_reason",
                "stable_design_guide_controller_request_hash",
                "_memo_key_payload",
                "_MEMO_DEBUG_PRODUCT_KEYS",
                "product_relevant_request_without_derived_stamps_v2",
                "request_hash_unchanged",
            )
        ),
        "memo_key_is_request_hash": (
            "memo_cache_key=request_hash" in controller_source
            and "_final_publication_memo_cache[request_hash]" in controller_source
        ),
        "debug_post_click_missing_guards_exist": all(
            token in controller_source
            for token in (
                "debug_force_rebuild",
                "post_click_or_apply_in_flight",
                "missing_publication_item",
            )
        ),
        "inputs_stamps_memo_diagnostics": all(
            token in input_source
            for token in (
                "design_guide_controller_trace_only_memo_cache_hit",
                "design_guide_controller_publication_authority_memo_cache_hit",
                "collapsed_guidance_replacement_controller_memo_cache_hit",
            )
        ),
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
        "apply_routing_still_page_owned": (
            "_consume_design_guide_component_cta_value" in input_source
            and "_consume_design_guide_component_cta_value" not in final_source
        ),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Final Publication Memo Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Hit | Reason | Expected met |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | `{hit}` | `{reason}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                hit=row["memo_cache_hit"],
                reason=_escape_md(row["memo_cache_reason"]),
                expected=row["expected_met"],
            )
        )
    lines.extend(["", "## Source Checks", "", "| Check | PASS |", "| --- | --- |"])
    for key, value in payload["source_checks"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Failures", ""])
    if payload["failures"]:
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendation", "", payload["recommended_next_slice"]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    scenarios = _scenario_rows()
    source_checks = _source_checks()

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source_check_failed::{key}")
    for row in scenarios:
        if row["expected_met"] is not True:
            failures.append(f"{row['scenario_id']}_unexpected_memo_result")

    passed = not failures
    payload = {
        "schema": "design_guide_final_publication_memo_implementation_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_live_memo_impact_snapshot": passed,
        "scenarios": scenarios,
        "source_checks": source_checks,
        "locks": {
            name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
            for name, lock in locks.items()
        },
        "snapshot_hash": _stable_hash(
            {
                "scenarios": scenarios,
                "source_checks": source_checks,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
            }
        ),
        "recommended_next_slice": (
            "Rerun browser/live controller request-key stability to prove live stable reruns report memo hits, "
            "then rerun Design Guide locks."
        ),
    }

    stamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_final_publication_memo_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_publication_memo_implementation_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_final_publication_memo_implementation_snapshot {payload['status']}")
    print(f"ready_for_live_memo_impact_snapshot={payload['ready_for_live_memo_impact_snapshot']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

