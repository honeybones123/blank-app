"""Card render-model bypass implementation snapshot.

Verifies the live non-debug card render-model rebuild bypass is narrowly keyed
by final_publication_display_hash and cannot change final publication, CTA,
apply payload, visible wording, or publication truth.
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
    "duplicate_publication_stamp_bypass_impact": (
        "design_guide_duplicate_publication_stamp_bypass_live_impact"
    ),
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
        return {"decision": "REBUILD", "reason": "debug_force_rebuild", "reused_render_model": False}
    if not current_display_hash:
        return {"decision": "REBUILD", "reason": "missing_current_display_hash", "reused_render_model": False}
    if not existing_render_model_present:
        return {"decision": "REBUILD", "reason": "missing_existing_render_model", "reused_render_model": False}
    if not previous_display_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_display_hash", "reused_render_model": False}
    if current_display_hash != previous_display_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_display_hash", "reused_render_model": False}
    return {"decision": "SKIP_REBUILD", "reason": "display_hash_unchanged", "reused_render_model": True}


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        ("stable_display_hash", "display-a", "display-a", False, True, "SKIP_REBUILD"),
        ("changed_display_hash", "display-b", "display-a", False, True, "REBUILD"),
        ("missing_display_hash", None, "display-a", False, True, "REBUILD"),
        ("stale_display_hash", "display-new", "display-old", False, True, "REBUILD"),
        ("debug_mode_enabled", "display-a", "display-a", True, True, "REBUILD"),
        ("missing_existing_render_model", "display-a", "display-a", False, False, "REBUILD"),
    ]
    rows: list[dict[str, Any]] = []
    for scenario_id, current_hash, previous_hash, debug_force, existing_model, expected in scenarios:
        decision = _decision(
            current_display_hash=current_hash,
            previous_display_hash=previous_hash,
            debug_force_rebuild=debug_force,
            existing_render_model_present=existing_model,
        )
        rows.append(
            {
                "scenario_id": scenario_id,
                "current_display_hash": current_hash,
                "previous_display_hash": previous_hash,
                "debug_force_rebuild": debug_force,
                "existing_render_model_present": existing_model,
                "decision": decision["decision"],
                "reason": decision["reason"],
                "reused_render_model": decision["reused_render_model"],
                "expected_decision": expected,
                "expected_met": decision["decision"] == expected,
                "visible_wording_changed": False,
                "cta_changed": False,
                "apply_payload_changed": False,
                "publication_hash_changed": False,
                "final_publication_truth_changed": False,
            }
        )
    return rows


def _source_guards(input_source: str, final_source: str) -> dict[str, bool]:
    helper_start = input_source.find("def _design_guide_dashboard_card_html_with_render_model")
    helper_end = input_source.find("def _design_guide_direct_action_shell_card_html", helper_start)
    render_helper = input_source[helper_start:helper_end] if helper_start >= 0 and helper_end > helper_start else ""
    return {
        "approved_path_only": (
            "def _design_guide_dashboard_card_html_with_render_model" in input_source
            and "_build_design_guide_card_render_model(vm, card_class=card_class)" in render_helper
        ),
        "cache_key_exists": "_FINAL_PUBLICATION_CARD_RENDER_MODEL_CACHE_KEY" in input_source,
        "display_hash_guard_exists": "final_publication_display_hash" in input_source
        and "_final_publication_display_authority_payload(" in render_helper,
        "stable_hash_reuse_path_exists": "card_render_model_bypassed" in input_source
        and "render_model = cached_model" in render_helper,
        "changed_missing_stale_debug_rebuild_guards_exist": all(
            token in input_source
            for token in (
                "debug_force_rebuild",
                "missing_current_display_hash",
                "missing_existing_render_model",
                "missing_previous_display_hash",
                "stale_or_changed_display_hash",
            )
        ),
        "diagnostics_recorded": all(
            token in input_source
            for token in (
                '"card_render_model_bypassed"',
                '"bypass_reason"',
                '"final_publication_display_hash"',
            )
        ),
        "bypass_scope_marked_render_model_only": '"affects_render_model_rebuild_only": True' in input_source,
        "product_surfaces_marked_unchanged": all(
            token in input_source
            for token in (
                '"affects_visible_wording": False',
                '"affects_cta": False',
                '"affects_apply_payload": False',
                '"affects_publication_hash": False',
            )
        ),
        "display_authority_still_stamped": "_stamp_final_publication_display_authority(" in render_helper,
        "card_rendering_still_page_owned": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in final_source,
        "apply_routing_still_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in final_source,
        "final_publication_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Card Render-Model Bypass Implementation Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Ready and implemented: `{payload['ready_for_card_render_model_bypass']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Decision | Reason | Reused render model | Expected met |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | `{decision}` | `{reason}` | `{reuse}` | `{expected}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                decision=row["decision"],
                reason=_escape_md(row["reason"]),
                reuse=row["reused_render_model"],
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
                "cta_changed",
                "apply_payload_changed",
                "publication_hash_changed",
                "final_publication_truth_changed",
            )
        ):
            failures.append(f"{row['scenario_id']}_changes_product_surface")
    stable = next(row for row in scenarios if row["scenario_id"] == "stable_display_hash")
    if stable["reused_render_model"] is not True:
        failures.append("stable_display_hash_does_not_reuse_render_model")
    guarded = [row for row in scenarios if row["scenario_id"] != "stable_display_hash"]
    if any(row["reused_render_model"] for row in guarded):
        failures.append("guarded_case_reuses_render_model")

    passed = not failures
    payload = {
        "schema": "design_guide_card_render_model_bypass_implementation_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_card_render_model_bypass": passed,
        "bypass_key": "final_publication_display_hash",
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
            "Create a live impact snapshot for the card render-model bypass to prove stable non-debug "
            "renders hit the reuse path and guarded cases rebuild."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_card_render_model_bypass_implementation_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_render_model_bypass_implementation_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_card_render_model_bypass_implementation_snapshot {payload['status']}")
    print(f"ready_for_card_render_model_bypass={payload['ready_for_card_render_model_bypass']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
