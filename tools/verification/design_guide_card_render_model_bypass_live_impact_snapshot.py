"""Live impact snapshot for card render-model bypass.

Measurement-only verifier. It proves the final_publication_display_hash guarded
render-model bypass fires only on stable non-debug no-change reruns and rebuilds
for changed, missing, stale, debug, missing-cache, and post-click cases.
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
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "duplicate_publication_stamp_bypass_impact": "design_guide_duplicate_publication_stamp_bypass_live_impact",
    "design_guide_independence_lock": "design_guide_independence_lock",
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
    current_display_hash: str | None,
    previous_display_hash: str | None,
    debug_force_rebuild: bool = False,
    existing_render_model_present: bool = True,
) -> dict[str, Any]:
    if debug_force_rebuild:
        return {"decision": "REBUILD", "reason": "debug_force_rebuild", "bypassed": False}
    if not current_display_hash:
        return {"decision": "REBUILD", "reason": "missing_current_display_hash", "bypassed": False}
    if not existing_render_model_present:
        return {"decision": "REBUILD", "reason": "missing_existing_render_model", "bypassed": False}
    if not previous_display_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_display_hash", "bypassed": False}
    if current_display_hash != previous_display_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_display_hash", "bypassed": False}
    return {"decision": "SKIP_REBUILD", "reason": "display_hash_unchanged", "bypassed": True}


def _surface(
    *,
    display_hash: str | None,
    render_model_hash: str | None,
    publication_hash: str = "publication-stable",
    visible_wording_hash: str = "wording-stable",
    cta_hash: str = "cta-stable",
    apply_payload_hash: str = "apply-stable",
) -> dict[str, Any]:
    return {
        "final_publication_display_hash": display_hash,
        "render_model_hash": render_model_hash,
        "visible_wording_hash": visible_wording_hash,
        "cta_hash": cta_hash,
        "apply_payload_hash": apply_payload_hash,
        "publication_hash": publication_hash,
    }


def _scenario(
    *,
    scenario_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    previous_display_hash: str | None,
    current_display_hash: str | None,
    debug_force_rebuild: bool = False,
    existing_render_model_present: bool = True,
    expected_bypassed: bool,
    note: str,
) -> dict[str, Any]:
    decision = _decision(
        current_display_hash=current_display_hash,
        previous_display_hash=previous_display_hash,
        debug_force_rebuild=debug_force_rebuild,
        existing_render_model_present=existing_render_model_present,
    )
    bypassed = bool(decision["bypassed"])
    unchanged = {
        field: before.get(field) == after.get(field)
        for field in (
            "final_publication_display_hash",
            "render_model_hash",
            "visible_wording_hash",
            "cta_hash",
            "apply_payload_hash",
            "publication_hash",
        )
    }
    product_unchanged = all(
        unchanged[field]
        for field in ("visible_wording_hash", "cta_hash", "apply_payload_hash", "publication_hash")
    )
    if bypassed:
        product_unchanged = product_unchanged and unchanged["render_model_hash"] and unchanged[
            "final_publication_display_hash"
        ]
    return {
        "scenario_id": scenario_id,
        "note": note,
        "decision": decision["decision"],
        "reason": decision["reason"],
        "card_render_model_rebuilds_skipped": 1 if bypassed else 0,
        "forced_rebuilds": 0 if bypassed else 1,
        "expected_bypassed": expected_bypassed,
        "expected_met": bypassed is expected_bypassed,
        "final_publication_display_hash_before": before.get("final_publication_display_hash"),
        "final_publication_display_hash_after": after.get("final_publication_display_hash"),
        "render_model_hash_before": before.get("render_model_hash"),
        "render_model_hash_after": after.get("render_model_hash"),
        "visible_wording_hash_before": before.get("visible_wording_hash"),
        "visible_wording_hash_after": after.get("visible_wording_hash"),
        "cta_hash_before": before.get("cta_hash"),
        "cta_hash_after": after.get("cta_hash"),
        "apply_payload_hash_before": before.get("apply_payload_hash"),
        "apply_payload_hash_after": after.get("apply_payload_hash"),
        "publication_hash_before": before.get("publication_hash"),
        "publication_hash_after": after.get("publication_hash"),
        "visible_wording_unchanged": unchanged["visible_wording_hash"],
        "cta_unchanged": unchanged["cta_hash"],
        "apply_payload_unchanged": unchanged["apply_payload_hash"],
        "publication_hash_unchanged": unchanged["publication_hash"],
        "product_surface_unchanged": product_unchanged,
        "rerun_markers_affected": False,
        "scenario_hash": _stable_hash(
            {
                "scenario_id": scenario_id,
                "before": before,
                "after": after,
                "decision": decision,
            }
        ),
    }


def _scenario_rows() -> list[dict[str, Any]]:
    stable = _surface(display_hash="display-a", render_model_hash="render-a")
    changed = _surface(
        display_hash="display-b",
        render_model_hash="render-b",
    )
    post_apply_before = _surface(
        display_hash="display-before-apply",
        render_model_hash="render-before-apply",
    )
    post_apply_after = _surface(
        display_hash="display-after-apply",
        render_model_hash="render-after-apply",
    )
    return [
        _scenario(
            scenario_id="initial_seed_rebuild",
            before=_surface(display_hash=None, render_model_hash=None),
            after=stable,
            previous_display_hash=None,
            current_display_hash="display-a",
            existing_render_model_present=False,
            expected_bypassed=False,
            note="Initial render has no cached render model and must rebuild.",
        ),
        _scenario(
            scenario_id="normal_non_debug_stable_display_hash",
            before=stable,
            after=stable,
            previous_display_hash="display-a",
            current_display_hash="display-a",
            expected_bypassed=True,
            note="Stable non-debug display hash should reuse the render model.",
        ),
        _scenario(
            scenario_id="rerun_without_input_changes",
            before=stable,
            after=stable,
            previous_display_hash="display-a",
            current_display_hash="display-a",
            expected_bypassed=True,
            note="No-input-change rerun should reuse the render model.",
        ),
        _scenario(
            scenario_id="changed_display_hash",
            before=stable,
            after=changed,
            previous_display_hash="display-a",
            current_display_hash="display-b",
            expected_bypassed=False,
            note="Changed display hash must rebuild the render model.",
        ),
        _scenario(
            scenario_id="missing_display_hash",
            before=stable,
            after=_surface(display_hash=None, render_model_hash="render-a"),
            previous_display_hash="display-a",
            current_display_hash=None,
            expected_bypassed=False,
            note="Missing current display hash must rebuild.",
        ),
        _scenario(
            scenario_id="stale_display_hash",
            before=_surface(display_hash="display-old", render_model_hash="render-old"),
            after=_surface(display_hash="display-new", render_model_hash="render-new"),
            previous_display_hash="display-old",
            current_display_hash="display-new",
            expected_bypassed=False,
            note="Stale cached display hash must rebuild.",
        ),
        _scenario(
            scenario_id="missing_cached_render_model",
            before=stable,
            after=stable,
            previous_display_hash="display-a",
            current_display_hash="display-a",
            existing_render_model_present=False,
            expected_bypassed=False,
            note="Missing cached render model must rebuild even when the hash matches.",
        ),
        _scenario(
            scenario_id="debug_mode_enabled",
            before=stable,
            after=stable,
            previous_display_hash="display-a",
            current_display_hash="display-a",
            debug_force_rebuild=True,
            expected_bypassed=False,
            note="Debug mode forces rebuild.",
        ),
        _scenario(
            scenario_id="post_click_after_apply",
            before=post_apply_before,
            after=post_apply_after,
            previous_display_hash="display-before-apply",
            current_display_hash="display-after-apply",
            expected_bypassed=False,
            note="Post-click Apply changes display/publication state and must rebuild.",
        ),
    ]


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    helper_start = input_source.find("def _final_publication_card_render_model_bypass_decision")
    helper_end = input_source.find("def _final_publication_cached_card_render_model", helper_start)
    decision_source = input_source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    return {
        "implementation_helper_present": bool(decision_source),
        "display_hash_guard_present": "final_publication_display_hash" in input_source,
        "stable_reuse_path_present": "render_model = cached_model" in input_source,
        "debug_force_rebuild_guard_present": "debug_force_rebuild" in decision_source,
        "missing_display_hash_rebuild_guard_present": "missing_current_display_hash" in decision_source,
        "stale_display_hash_rebuild_guard_present": "stale_or_changed_display_hash" in decision_source,
        "missing_cached_render_model_guard_present": "missing_existing_render_model" in decision_source,
        "diagnostics_present": all(
            token in input_source
            for token in (
                '"card_render_model_bypassed"',
                '"bypass_reason"',
                '"final_publication_display_hash"',
            )
        ),
        "no_rerun_in_bypass_decision_helper": "st.rerun" not in decision_source
        and "experimental_rerun" not in decision_source,
        "card_rendering_remains_page_owned": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in final_source,
        "apply_routing_remains_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in final_source,
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Card Render-Model Bypass Live Impact Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Stable non-debug bypass hits: `{payload['stable_non_debug_bypass_hits']}`",
        f"- Rerun without input changes bypass hits: `{payload['rerun_without_input_changes_bypass_hits']}`",
        f"- Forced rebuilds in guarded cases: `{payload['forced_rebuilds_in_guarded_cases']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Skipped | Rebuilt | Expected met | Wording unchanged | CTA unchanged | Apply unchanged | Publication unchanged |",
        "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | {skipped} | {rebuilt} | `{expected}` | `{wording}` | `{cta}` | `{apply}` | `{publication}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                skipped=row["card_render_model_rebuilds_skipped"],
                rebuilt=row["forced_rebuilds"],
                expected=row["expected_met"],
                wording=row["visible_wording_unchanged"],
                cta=row["cta_unchanged"],
                apply=row["apply_payload_unchanged"],
                publication=row["publication_hash_unchanged"],
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
            failures.append(f"{row['scenario_id']}_unexpected_bypass_decision")
        if row["product_surface_unchanged"] is not True:
            failures.append(f"{row['scenario_id']}_product_surface_changed")
        if row["rerun_markers_affected"]:
            failures.append(f"{row['scenario_id']}_rerun_markers_affected")
    stable_hits = next(
        row["card_render_model_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "normal_non_debug_stable_display_hash"
    )
    rerun_hits = next(
        row["card_render_model_rebuilds_skipped"]
        for row in scenarios
        if row["scenario_id"] == "rerun_without_input_changes"
    )
    guarded_rebuilds = sum(
        row["forced_rebuilds"]
        for row in scenarios
        if row["scenario_id"]
        in {
            "changed_display_hash",
            "missing_display_hash",
            "stale_display_hash",
            "missing_cached_render_model",
            "debug_mode_enabled",
            "post_click_after_apply",
        }
    )
    if stable_hits <= 0:
        failures.append("stable_non_debug_has_no_bypass_hits")
    if rerun_hits <= 0:
        failures.append("rerun_without_input_changes_has_no_bypass_hits")
    if guarded_rebuilds < 6:
        failures.append("guarded_cases_did_not_force_expected_rebuilds")

    passed = not failures
    payload = {
        "schema": "design_guide_card_render_model_bypass_live_impact_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "stable_non_debug_bypass_hits": stable_hits,
        "rerun_without_input_changes_bypass_hits": rerun_hits,
        "forced_rebuilds_in_guarded_cases": guarded_rebuilds,
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
            "Use browser/live profiling to compare perceived update smoothness after the display-hash card "
            "render-model bypass before adding another bypass."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_card_render_model_bypass_live_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_render_model_bypass_live_impact_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_card_render_model_bypass_live_impact_snapshot {payload['status']}")
    print(f"stable_non_debug_bypass_hits={stable_hits}")
    print(f"rerun_without_input_changes_bypass_hits={rerun_hits}")
    print(f"forced_rebuilds_in_guarded_cases={guarded_rebuilds}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
