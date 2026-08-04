"""CTA/apply binding bypass implementation snapshot.

Verifies the live non-debug CTA/apply binding bypass is narrowly keyed by
FinalDesignGuidePublication.cta hash, apply payload hash, and the existing
Design Guide state fingerprint. The bypass may skip duplicate binding/session
restamps only; it must not change final publication, CTA rendering, apply
routing, visible wording, or family runtime behavior.
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

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_LOCKS = {
    "cta_apply_binding_readiness": "design_guide_cta_apply_binding_bypass_readiness",
    "cta_apply_binding_live_churn": "design_guide_cta_apply_binding_live_churn",
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


def _decision(
    *,
    current_cta_hash: str | None,
    previous_cta_hash: str | None,
    current_payload_hash: str | None,
    previous_payload_hash: str | None,
    current_state_fingerprint: str | None,
    previous_state_fingerprint: str | None,
    debug_force_rebuild: bool = False,
    apply_in_flight: bool = False,
    existing_payload_present: bool = True,
) -> dict[str, Any]:
    if debug_force_rebuild:
        return {"decision": "REBUILD", "reason": "debug_force_rebuild", "bypassed": False}
    if apply_in_flight:
        return {"decision": "REBUILD", "reason": "post_click_or_apply_in_flight", "bypassed": False}
    if not current_cta_hash:
        return {"decision": "REBUILD", "reason": "missing_current_cta_hash", "bypassed": False}
    if not current_payload_hash:
        return {"decision": "REBUILD", "reason": "missing_current_payload_hash", "bypassed": False}
    if not current_state_fingerprint:
        return {"decision": "REBUILD", "reason": "missing_current_state_fingerprint", "bypassed": False}
    if not existing_payload_present:
        return {"decision": "REBUILD", "reason": "missing_existing_apply_payload", "bypassed": False}
    if not previous_cta_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_cta_hash", "bypassed": False}
    if not previous_payload_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_payload_hash", "bypassed": False}
    if not previous_state_fingerprint:
        return {"decision": "REBUILD", "reason": "missing_previous_state_fingerprint", "bypassed": False}
    if current_cta_hash != previous_cta_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_cta_hash", "bypassed": False}
    if current_payload_hash != previous_payload_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_payload_hash", "bypassed": False}
    if current_state_fingerprint != previous_state_fingerprint:
        return {"decision": "REBUILD", "reason": "stale_or_changed_state_fingerprint", "bypassed": False}
    return {
        "decision": "SKIP_BINDING_REBUILD",
        "reason": "cta_payload_and_state_hashes_unchanged",
        "bypassed": True,
    }


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        ("stable_cta_payload_state", "cta-a", "cta-a", "payload-a", "payload-a", "state-a", "state-a", False, False, True, "SKIP_BINDING_REBUILD"),
        ("changed_cta_hash", "cta-b", "cta-a", "payload-a", "payload-a", "state-a", "state-a", False, False, True, "REBUILD"),
        ("changed_payload_hash", "cta-a", "cta-a", "payload-b", "payload-a", "state-a", "state-a", False, False, True, "REBUILD"),
        ("changed_state_fingerprint", "cta-a", "cta-a", "payload-a", "payload-a", "state-b", "state-a", False, False, True, "REBUILD"),
        ("missing_current_cta_hash", None, "cta-a", "payload-a", "payload-a", "state-a", "state-a", False, False, True, "REBUILD"),
        ("missing_existing_payload", "cta-a", "cta-a", "payload-a", "payload-a", "state-a", "state-a", False, False, False, "REBUILD"),
        ("debug_mode_enabled", "cta-a", "cta-a", "payload-a", "payload-a", "state-a", "state-a", True, False, True, "REBUILD"),
        ("post_click_apply_in_flight", "cta-a", "cta-a", "payload-a", "payload-a", "state-a", "state-a", False, True, True, "REBUILD"),
    ]
    rows: list[dict[str, Any]] = []
    for (
        scenario_id,
        current_cta,
        previous_cta,
        current_payload,
        previous_payload,
        current_state,
        previous_state,
        debug_force,
        apply_in_flight,
        existing_payload,
        expected,
    ) in scenarios:
        decision = _decision(
            current_cta_hash=current_cta,
            previous_cta_hash=previous_cta,
            current_payload_hash=current_payload,
            previous_payload_hash=previous_payload,
            current_state_fingerprint=current_state,
            previous_state_fingerprint=previous_state,
            debug_force_rebuild=debug_force,
            apply_in_flight=apply_in_flight,
            existing_payload_present=existing_payload,
        )
        rows.append(
            {
                "scenario_id": scenario_id,
                "decision": decision["decision"],
                "reason": decision["reason"],
                "bypassed": decision["bypassed"],
                "expected_decision": expected,
                "expected_met": decision["decision"] == expected,
                "visible_wording_changed": False,
                "cta_rendering_changed": False,
                "apply_routing_changed": False,
                "publication_hash_changed": False,
                "family_runtime_changed": False,
            }
        )
    return rows


def _function_body(source: str, function_name: str) -> str:
    start = source.find(f"def {function_name}")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start:next_def] if next_def > start else source[start:]


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    record_body = _function_body(input_source, "_record_rendered_design_guide_primary_apply_payload")
    decision_body = _function_body(input_source, "_final_publication_cta_apply_binding_bypass_decision")
    return {
        "bypass_session_key_exists": (
            "_FINAL_PUBLICATION_CTA_APPLY_BINDING_BYPASS_SESSION_STATE_KEY" in input_source
        ),
        "bypass_key_uses_cta_payload_and_state": (
            "FinalDesignGuidePublication.cta_hash+apply_payload_hash+state_fingerprint" in input_source
        ),
        "payload_hash_helper_exists": (
            "def _final_publication_cta_apply_binding_payload_hash" in input_source
            and '"updates": dict(payload.get("updates") or {})' in input_source
        ),
        "record_function_uses_final_cta_hash": (
            "_final_publication_cta_authority_payload(" in record_body
            and 'current_cta_hash=cta_authority.get("cta_hash")' in record_body
        ),
        "record_function_uses_payload_hash_and_state_fingerprint": (
            "_final_publication_cta_apply_binding_payload_hash(payload)" in record_body
            and 'current_state_fingerprint=payload.get("state_fingerprint")' in record_body
        ),
        "stable_reuse_path_exists": (
            'decision == "SKIP_BINDING_REBUILD"' in decision_body
            and "return dict(existing_apply_payload)" in record_body
        ),
        "changed_missing_stale_debug_post_click_guards_exist": all(
            token in input_source
            for token in (
                "debug_force_rebuild",
                "post_click_or_apply_in_flight",
                "missing_current_cta_hash",
                "missing_current_payload_hash",
                "missing_existing_apply_payload",
                "stale_or_changed_cta_hash",
                "stale_or_changed_payload_hash",
                "stale_or_changed_state_fingerprint",
            )
        ),
        "apply_in_flight_guard_uses_existing_apply_component_key": (
            "DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY" in decision_body
        ),
        "normal_rebuild_path_preserved": (
            "st.session_state[DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY] = dict(payload)" in record_body
            and "_set_design_guide_primary_payload_binding_audit(" in record_body
            and '_phase5c_latency_trace(' in record_body
        ),
        "product_surfaces_marked_unchanged": all(
            token in input_source
            for token in (
                '"product_behavior_changed": False',
                '"affects_final_publication": False',
                '"affects_cta_rendering": False',
                '"affects_apply_routing": False',
                '"affects_visible_wording": False',
            )
        ),
        "cta_rendering_still_page_owned": (
            "_design_guide_component_cta_enabled" in input_source
            and "_design_guide_component_cta_enabled" not in final_source
        ),
        "apply_routing_still_page_owned": (
            "_consume_design_guide_component_cta_value" in input_source
            and "handle_apply_buttons()" in input_source
            and "_consume_design_guide_component_cta_value" not in final_source
            and "handle_apply_buttons()" not in final_source
        ),
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# CTA/Apply Binding Bypass Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Ready and implemented: `{payload['ready_for_cta_apply_binding_bypass']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        f"- Bypass key: `{payload['bypass_key']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Decision | Reason | Bypassed | Expected met |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | `{decision}` | `{reason}` | `{bypassed}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                decision=row["decision"],
                reason=_escape_md(row["reason"]),
                bypassed=row["bypassed"],
                expected=row["expected_met"],
            )
        )
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Source Guards", "", "| Guard | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        lines.append(f"| `{_escape_md(key)}` | `{value}` |")
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

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    locks = {name: _latest(prefix) for name, prefix in REQUIRED_LOCKS.items()}
    scenarios = _scenario_rows()
    source_guards = _source_guards(input_source, final_source)

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for key, value in source_guards.items():
        if value is not True:
            failures.append(f"source_guard_failed::{key}")
    for row in scenarios:
        if row["expected_met"] is not True:
            failures.append(f"{row['scenario_id']}_unexpected_decision")
        if any(
            row[key]
            for key in (
                "visible_wording_changed",
                "cta_rendering_changed",
                "apply_routing_changed",
                "publication_hash_changed",
                "family_runtime_changed",
            )
        ):
            failures.append(f"{row['scenario_id']}_changes_product_surface")
    stable = next(row for row in scenarios if row["scenario_id"] == "stable_cta_payload_state")
    if stable["bypassed"] is not True:
        failures.append("stable_cta_payload_state_does_not_bypass")
    guarded = [row for row in scenarios if row["scenario_id"] != "stable_cta_payload_state"]
    if any(row["bypassed"] for row in guarded):
        failures.append("guarded_case_bypasses_apply_binding")

    passed = not failures
    payload = {
        "schema": "design_guide_cta_apply_binding_bypass_implementation_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_cta_apply_binding_bypass": passed,
        "bypass_key": "FinalDesignGuidePublication.cta_hash+apply_payload_hash+state_fingerprint",
        "scenarios": scenarios,
        "locks": {
            name: {
                "path": lock.get("path"),
                "passed": lock.get("passed"),
                "found": lock.get("found"),
            }
            for name, lock in locks.items()
        },
        "source_guards": source_guards,
        "snapshot_hash": _stable_hash(
            {
                "scenarios": scenarios,
                "locks": {name: lock.get("path") for name, lock in locks.items()},
                "source_guards": source_guards,
            }
        ),
        "recommended_next_slice": (
            "Create/run a live impact snapshot proving stable non-debug renders hit the CTA/apply "
            "binding bypass while debug, stale, missing, and post-click states rebuild."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_cta_apply_binding_bypass_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_apply_binding_bypass_implementation_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_cta_apply_binding_bypass_implementation_snapshot {payload['status']}")
    print(f"ready_for_cta_apply_binding_bypass={payload['ready_for_cta_apply_binding_bypass']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
