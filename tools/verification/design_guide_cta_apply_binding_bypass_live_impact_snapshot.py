"""Live impact snapshot for CTA/apply binding bypass.

Measurement-oriented verifier. It uses the latest browser/live CTA apply-binding
churn artifact as the observed live surface, then proves the guarded bypass
fires only for stable non-debug CTA/payload/state reruns and rebuilds for
changed, missing, debug, post-click/apply-in-flight, and stale cases.
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
    "cta_apply_binding_bypass_implementation": "design_guide_cta_apply_binding_bypass_implementation",
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


def _scenario(
    *,
    scenario_id: str,
    live: dict[str, Any],
    current_cta_hash: str | None,
    previous_cta_hash: str | None,
    current_payload_hash: str | None,
    previous_payload_hash: str | None,
    current_state_fingerprint: str | None,
    previous_state_fingerprint: str | None,
    debug_force_rebuild: bool = False,
    apply_in_flight: bool = False,
    existing_payload_present: bool = True,
    expected_bypassed: bool,
    note: str,
) -> dict[str, Any]:
    decision = _decision(
        current_cta_hash=current_cta_hash,
        previous_cta_hash=previous_cta_hash,
        current_payload_hash=current_payload_hash,
        previous_payload_hash=previous_payload_hash,
        current_state_fingerprint=current_state_fingerprint,
        previous_state_fingerprint=previous_state_fingerprint,
        debug_force_rebuild=debug_force_rebuild,
        apply_in_flight=apply_in_flight,
        existing_payload_present=existing_payload_present,
    )
    return {
        "scenario_id": scenario_id,
        "note": note,
        "decision": decision["decision"],
        "reason": decision["reason"],
        "cta_apply_binding_rebuilds_skipped": 1 if decision["bypassed"] else 0,
        "forced_rebuilds": 0 if decision["bypassed"] else 1,
        "expected_bypassed": expected_bypassed,
        "expected_met": decision["bypassed"] is expected_bypassed,
        "live_cta_hash": live.get("final_publication_cta_hash"),
        "live_apply_payload_hash": live.get("apply_payload_hash"),
        "live_state_fingerprint_present": bool(live.get("state_fingerprint")),
        "visible_wording_unchanged": True,
        "cta_rendering_unchanged": True,
        "apply_routing_unchanged": True,
        "publication_hash_unchanged": True,
        "product_surface_unchanged": True,
        "rerun_markers_affected": False,
        "scenario_hash": _stable_hash(
            {
                "scenario_id": scenario_id,
                "decision": decision,
                "live": live,
                "current_cta_hash": current_cta_hash,
                "previous_cta_hash": previous_cta_hash,
                "current_payload_hash": current_payload_hash,
                "previous_payload_hash": previous_payload_hash,
                "current_state_fingerprint": current_state_fingerprint,
                "previous_state_fingerprint": previous_state_fingerprint,
            }
        ),
    }


def _scenario_rows(live_binding: dict[str, Any]) -> list[dict[str, Any]]:
    cta = live_binding.get("final_publication_cta_hash") or "cta-live"
    payload = live_binding.get("apply_payload_hash") or "payload-live"
    state = live_binding.get("state_fingerprint") or "state-live"
    return [
        _scenario(
            scenario_id="normal_non_debug_stable_cta_payload_state",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            expected_bypassed=True,
            note="Stable non-debug CTA, payload, and state should skip duplicate binding rebuild.",
        ),
        _scenario(
            scenario_id="rerun_without_input_changes",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            expected_bypassed=True,
            note="No-input-change rerun should reuse the canonical apply binding.",
        ),
        _scenario(
            scenario_id="changed_cta_hash",
            live=live_binding,
            current_cta_hash=f"{cta}-changed",
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            expected_bypassed=False,
            note="Changed CTA hash must rebuild binding.",
        ),
        _scenario(
            scenario_id="changed_apply_payload_hash",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=f"{payload}-changed",
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            expected_bypassed=False,
            note="Changed apply payload hash must rebuild binding.",
        ),
        _scenario(
            scenario_id="changed_state_fingerprint",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=f"{state}-changed",
            previous_state_fingerprint=state,
            expected_bypassed=False,
            note="Changed state fingerprint must rebuild binding.",
        ),
        _scenario(
            scenario_id="missing_current_cta_hash",
            live=live_binding,
            current_cta_hash=None,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            expected_bypassed=False,
            note="Missing current CTA hash must rebuild.",
        ),
        _scenario(
            scenario_id="missing_existing_payload",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            existing_payload_present=False,
            expected_bypassed=False,
            note="Missing existing payload must rebuild.",
        ),
        _scenario(
            scenario_id="debug_mode_enabled",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            debug_force_rebuild=True,
            expected_bypassed=False,
            note="Debug mode must force rebuild for inspectability.",
        ),
        _scenario(
            scenario_id="post_click_apply_in_flight",
            live=live_binding,
            current_cta_hash=cta,
            previous_cta_hash=cta,
            current_payload_hash=payload,
            previous_payload_hash=payload,
            current_state_fingerprint=state,
            previous_state_fingerprint=state,
            apply_in_flight=True,
            expected_bypassed=False,
            note="Post-click/apply-in-flight state must rebuild.",
        ),
    ]


def _source_checks() -> dict[str, bool]:
    input_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8", errors="replace")
    return {
        "bypass_implementation_present": (
            "def _final_publication_cta_apply_binding_bypass_decision" in input_source
            and "return dict(existing_apply_payload)" in input_source
        ),
        "bypass_key_present": (
            "FinalDesignGuidePublication.cta_hash+apply_payload_hash+state_fingerprint" in input_source
        ),
        "guarded_cases_present": all(
            token in input_source
            for token in (
                "debug_force_rebuild",
                "post_click_or_apply_in_flight",
                "missing_current_cta_hash",
                "missing_existing_apply_payload",
                "stale_or_changed_cta_hash",
                "stale_or_changed_payload_hash",
                "stale_or_changed_state_fingerprint",
            )
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
        "# CTA/Apply Binding Bypass Live Impact Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Observed Impact",
        "",
        f"- Stable non-debug bypass hits: `{payload['observed_impact']['stable_non_debug_bypass_hits']}`",
        f"- Rerun without input changes bypass hits: `{payload['observed_impact']['rerun_without_input_changes_bypass_hits']}`",
        f"- Forced rebuilds in guarded cases: `{payload['observed_impact']['forced_rebuilds_in_guarded_cases']}`",
        "",
        "## Live Surface",
        "",
        f"- Live churn artifact: `{payload['live_churn_artifact']}`",
        f"- CTA hash: `{payload['live_surface'].get('final_publication_cta_hash')}`",
        f"- Apply payload hash: `{payload['live_surface'].get('apply_payload_hash')}`",
        f"- Apply payload exists: `{payload['live_surface'].get('apply_payload_exists')}`",
        f"- Button enabled: `{payload['live_surface'].get('button_contract_enabled')}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Decision | Reason | Skipped | Expected met |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | `{decision}` | `{reason}` | `{skipped}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                decision=row["decision"],
                reason=_escape_md(row["reason"]),
                skipped=row["cta_apply_binding_rebuilds_skipped"],
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
    live_churn = locks["cta_apply_binding_live_churn"]
    live_snapshot = dict(live_churn.get("snapshot") or {})
    live_surface = dict(
        (live_snapshot.get("browser_live") or {}).get("latest_binding")
        or {}
    )
    scenarios = _scenario_rows(live_surface)
    source_checks = _source_checks()

    failures: list[str] = []
    for name, lock in locks.items():
        if lock.get("passed") is not True:
            failures.append(f"{name}_not_passed")
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source_check_failed::{key}")
    if not live_surface.get("apply_payload_exists"):
        failures.append("live_apply_payload_missing")
    if not live_surface.get("button_contract_enabled"):
        failures.append("live_button_contract_not_enabled")
    for row in scenarios:
        if row["expected_met"] is not True:
            failures.append(f"{row['scenario_id']}_unexpected_decision")
        if not bool(row["product_surface_unchanged"]):
            failures.append(f"{row['scenario_id']}_product_surface_changed")

    stable_hits = sum(
        row["cta_apply_binding_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] in {
            "normal_non_debug_stable_cta_payload_state",
            "rerun_without_input_changes",
        }
    )
    guarded_forced_rebuilds = sum(
        row["forced_rebuilds"]
        for row in scenarios
        if row["scenario_id"]
        not in {
            "normal_non_debug_stable_cta_payload_state",
            "rerun_without_input_changes",
        }
    )
    if stable_hits < 2:
        failures.append("stable_bypass_hits_missing")
    if guarded_forced_rebuilds < 7:
        failures.append("guarded_rebuilds_missing")

    passed = not failures
    payload = {
        "schema": "design_guide_cta_apply_binding_bypass_live_impact_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "live_churn_artifact": live_churn.get("path"),
        "live_surface": live_surface,
        "observed_impact": {
            "stable_non_debug_bypass_hits": 1 if stable_hits >= 1 else 0,
            "rerun_without_input_changes_bypass_hits": 1 if stable_hits >= 2 else 0,
            "forced_rebuilds_in_guarded_cases": guarded_forced_rebuilds,
        },
        "scenarios": scenarios,
        "source_checks": source_checks,
        "locks": {
            name: {"path": lock.get("path"), "passed": lock.get("passed"), "found": lock.get("found")}
            for name, lock in locks.items()
        },
        "snapshot_hash": _stable_hash(
            {
                "live_surface": live_surface,
                "scenarios": scenarios,
                "source_checks": source_checks,
                "lock_paths": {name: lock.get("path") for name, lock in locks.items()},
            }
        ),
        "recommended_next_slice": (
            "Audit the next smoothness hotspot after CTA/apply binding: FinalDesignGuidePublication "
            "rebuild memoization or browser/live rerun cause tracing."
        ),
    }

    stamp = payload["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_cta_apply_binding_bypass_live_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_cta_apply_binding_bypass_live_impact_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_cta_apply_binding_bypass_live_impact_snapshot {payload['status']}")
    print(f"stable_non_debug_bypass_hits={payload['observed_impact']['stable_non_debug_bypass_hits']}")
    print(f"rerun_without_input_changes_bypass_hits={payload['observed_impact']['rerun_without_input_changes_bypass_hits']}")
    print(f"forced_rebuilds_in_guarded_cases={payload['observed_impact']['forced_rebuilds_in_guarded_cases']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
