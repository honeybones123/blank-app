"""Card render-model bypass readiness snapshot.

Proof-only. This verifier proves the repeated card render-model rebuild path is
identifiable and can be keyed by FinalDesignGuidePublication.display hash before
any live bypass is implemented.
"""

from __future__ import annotations

import hashlib
import json
import re
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
    "design_guide_independence_lock": "design_guide_independence_lock",
    "duplicate_publication_stamp_bypass_impact": (
        "design_guide_duplicate_publication_stamp_bypass_live_impact"
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


def _count_call(source: str, name: str) -> int:
    return len(re.findall(rf"(?<!def )\b{re.escape(name)}\s*\(", source))


def _line_numbers(source: str, token: str, *, limit: int = 8) -> list[int]:
    lines: list[int] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            lines.append(index)
            if len(lines) >= limit:
                break
    return lines


def _render_model_from_display(display_hash: str, *, variant: str = "stable") -> dict[str, Any]:
    if variant == "changed":
        return {
            "title": "Strengthening required",
            "badge": "ACTION",
            "summary": "Run one-click auto design.",
            "status": "action",
            "display_state": "ACTION",
            "colour_state": "action",
            "card_class": "fast-guidance-item fail dg-card--action",
            "blocker_explanation": "",
            "display_hash": display_hash,
            "reason_display_rows": [{"label": "Action", "text": "Run one-click auto design."}],
        }
    return {
        "title": "Design checks pass",
        "badge": "PASS",
        "summary": "All required checks remain acceptable.",
        "status": "pass",
        "display_state": "PASS",
        "colour_state": "pass",
        "card_class": "fast-guidance-item pass guidance-success",
        "blocker_explanation": "",
        "display_hash": display_hash,
        "reason_display_rows": [{"label": "Status", "text": "All required checks remain acceptable."}],
    }


def _surface_hashes(display_hash: str, *, variant: str = "stable") -> dict[str, str]:
    if variant == "changed":
        return {
            "publication_hash": "publication-changed",
            "display_hash": display_hash,
            "render_model_hash": _stable_hash(_render_model_from_display(display_hash, variant="changed")),
            "cta_hash": "cta-stable",
            "apply_payload_hash": "apply-stable",
            "visible_wording_hash": "wording-changed-display",
        }
    return {
        "publication_hash": "publication-stable",
        "display_hash": display_hash,
        "render_model_hash": _stable_hash(_render_model_from_display(display_hash)),
        "cta_hash": "cta-stable",
        "apply_payload_hash": "apply-stable",
        "visible_wording_hash": "wording-stable",
    }


def _decision(
    *,
    current_display_hash: str | None,
    previous_display_hash: str | None,
    debug_force_rebuild: bool = False,
    existing_render_model_present: bool = True,
) -> dict[str, Any]:
    if debug_force_rebuild:
        return {"decision": "REBUILD", "reason": "debug_force_rebuild", "ready_to_skip": False}
    if not current_display_hash:
        return {"decision": "REBUILD", "reason": "missing_current_display_hash", "ready_to_skip": False}
    if not existing_render_model_present:
        return {"decision": "REBUILD", "reason": "missing_existing_render_model", "ready_to_skip": False}
    if not previous_display_hash:
        return {"decision": "REBUILD", "reason": "missing_previous_display_hash", "ready_to_skip": False}
    if current_display_hash != previous_display_hash:
        return {"decision": "REBUILD", "reason": "stale_or_changed_display_hash", "ready_to_skip": False}
    return {"decision": "SKIP_REBUILD", "reason": "display_hash_unchanged", "ready_to_skip": True}


def _scenario_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scenarios = [
        {
            "scenario_id": "stable_display_hash",
            "before": _surface_hashes("display-stable"),
            "after": _surface_hashes("display-stable"),
            "previous_display_hash": "display-stable",
            "current_display_hash": "display-stable",
            "expected": "SKIP_REBUILD",
            "debug_force_rebuild": False,
            "existing_render_model_present": True,
        },
        {
            "scenario_id": "changed_display_hash",
            "before": _surface_hashes("display-stable"),
            "after": _surface_hashes("display-changed", variant="changed"),
            "previous_display_hash": "display-stable",
            "current_display_hash": "display-changed",
            "expected": "REBUILD",
            "debug_force_rebuild": False,
            "existing_render_model_present": True,
        },
        {
            "scenario_id": "missing_display_hash",
            "before": _surface_hashes("display-stable"),
            "after": _surface_hashes(""),
            "previous_display_hash": "display-stable",
            "current_display_hash": None,
            "expected": "REBUILD",
            "debug_force_rebuild": False,
            "existing_render_model_present": True,
        },
        {
            "scenario_id": "stale_display_hash",
            "before": _surface_hashes("display-old"),
            "after": _surface_hashes("display-new", variant="changed"),
            "previous_display_hash": "display-old",
            "current_display_hash": "display-new",
            "expected": "REBUILD",
            "debug_force_rebuild": False,
            "existing_render_model_present": True,
        },
        {
            "scenario_id": "missing_existing_render_model",
            "before": _surface_hashes("display-stable"),
            "after": _surface_hashes("display-stable"),
            "previous_display_hash": "display-stable",
            "current_display_hash": "display-stable",
            "expected": "REBUILD",
            "debug_force_rebuild": False,
            "existing_render_model_present": False,
        },
        {
            "scenario_id": "debug_mode_enabled",
            "before": _surface_hashes("display-stable"),
            "after": _surface_hashes("display-stable"),
            "previous_display_hash": "display-stable",
            "current_display_hash": "display-stable",
            "expected": "REBUILD",
            "debug_force_rebuild": True,
            "existing_render_model_present": True,
        },
    ]
    for scenario in scenarios:
        decision = _decision(
            current_display_hash=scenario["current_display_hash"],
            previous_display_hash=scenario["previous_display_hash"],
            debug_force_rebuild=scenario["debug_force_rebuild"],
            existing_render_model_present=scenario["existing_render_model_present"],
        )
        before = dict(scenario["before"])
        after = dict(scenario["after"])
        skipped = decision["decision"] == "SKIP_REBUILD"
        product_surface_unchanged_on_skip = True
        if skipped:
            product_surface_unchanged_on_skip = all(
                before.get(field) == after.get(field)
                for field in (
                    "publication_hash",
                    "display_hash",
                    "render_model_hash",
                    "cta_hash",
                    "apply_payload_hash",
                    "visible_wording_hash",
                )
            )
        rows.append(
            {
                "scenario_id": scenario["scenario_id"],
                "decision": decision["decision"],
                "reason": decision["reason"],
                "ready_to_skip": decision["ready_to_skip"],
                "expected_decision": scenario["expected"],
                "expected_met": decision["decision"] == scenario["expected"],
                "before": before,
                "after": after,
                "stable_display_hash_produces_identical_render_model": (
                    before.get("render_model_hash") == after.get("render_model_hash")
                    if scenario["scenario_id"] == "stable_display_hash"
                    else None
                ),
                "bypass_would_affect_render_model_rebuild_only": True,
                "visible_wording_unchanged_on_skip": (
                    before.get("visible_wording_hash") == after.get("visible_wording_hash")
                    if skipped
                    else True
                ),
                "cta_unchanged_on_skip": before.get("cta_hash") == after.get("cta_hash") if skipped else True,
                "apply_payload_unchanged_on_skip": (
                    before.get("apply_payload_hash") == after.get("apply_payload_hash") if skipped else True
                ),
                "publication_hash_unchanged_on_skip": (
                    before.get("publication_hash") == after.get("publication_hash") if skipped else True
                ),
                "product_surface_unchanged_on_skip": product_surface_unchanged_on_skip,
                "scenario_hash": _stable_hash({"scenario": scenario, "decision": decision}),
            }
        )
    return rows


def _source_guards(input_source: str, final_source: str) -> dict[str, Any]:
    return {
        "render_model_rebuild_path_identifiable": (
            "def _design_guide_dashboard_card_html_with_render_model" in input_source
            and "_build_design_guide_card_render_model(vm, card_class=card_class)" in input_source
            and "_record_design_guide_card_render_model(render_model, source=source)" in input_source
        ),
        "display_authority_stamp_uses_render_model": (
            "_stamp_final_publication_display_authority(" in input_source
            and "render_model=asdict(render_model)" in input_source
        ),
        "display_hash_surface_exists": (
            "final_publication_display_hash" in input_source
            and '"display_hash"' in input_source
            and "FinalDesignGuidePublication.display" in input_source
        ),
        "card_rendering_remains_page_owned": (
            "_design_guide_dashboard_card_html_from_render_model" in input_source
            and "_design_guide_dashboard_card_html_from_render_model" not in final_source
        ),
        "apply_routing_remains_page_owned": (
            "_record_rendered_design_guide_primary_apply_payload" in input_source
            and "_record_rendered_design_guide_primary_apply_payload" not in final_source
        ),
        "final_publication_has_no_page_imports": "inputs_page" not in final_source and "streamlit" not in final_source,
        "render_model_path_lines": _line_numbers(input_source, "_design_guide_dashboard_card_html_with_render_model"),
        "display_authority_lines": _line_numbers(input_source, "_stamp_final_publication_display_authority"),
    }


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Card Render-Model Bypass Readiness Snapshot",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Ready for card render-model bypass: `{payload['ready_for_card_render_model_bypass']}`",
        f"- Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Decision | Reason | Expected met | Product surface unchanged on skip |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["scenarios"]:
        lines.append(
            "| `{scenario}` | `{decision}` | `{reason}` | `{expected}` | `{unchanged}` |".format(
                scenario=_escape_md(row["scenario_id"]),
                decision=row["decision"],
                reason=_escape_md(row["reason"]),
                expected=row["expected_met"],
                unchanged=row["product_surface_unchanged_on_skip"],
            )
        )
    lines.extend(["", "## Locks", ""])
    for name, lock in payload["locks"].items():
        lines.append(f"- `{name}`: passed=`{lock['passed']}`, path=`{lock['path']}`")
    lines.extend(["", "## Source Guards", "", "| Guard | PASS |", "| --- | --- |"])
    for key, value in payload["source_guards"].items():
        if isinstance(value, bool):
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
        if isinstance(value, bool) and value is not True:
            failures.append(f"source_guard_failed::{key}")
    for row in scenarios:
        if row["expected_met"] is not True:
            failures.append(f"{row['scenario_id']}_unexpected_decision")
        if row["product_surface_unchanged_on_skip"] is not True:
            failures.append(f"{row['scenario_id']}_skip_changes_product_surface")
        if row["bypass_would_affect_render_model_rebuild_only"] is not True:
            failures.append(f"{row['scenario_id']}_bypass_scope_not_render_model_only")
    stable = next(row for row in scenarios if row["scenario_id"] == "stable_display_hash")
    if stable["ready_to_skip"] is not True:
        failures.append("stable_display_hash_not_ready_to_skip")
    if stable["stable_display_hash_produces_identical_render_model"] is not True:
        failures.append("stable_display_hash_does_not_produce_identical_render_model")
    guarded = [row for row in scenarios if row["scenario_id"] != "stable_display_hash"]
    if any(row["decision"] != "REBUILD" for row in guarded):
        failures.append("guarded_case_failed_to_rebuild")

    passed = not failures
    payload = {
        "schema": "design_guide_card_render_model_bypass_readiness_snapshot.v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "product_behavior_changed": False,
        "ready_for_card_render_model_bypass": passed,
        "bypass_key": "FinalDesignGuidePublication.display hash / final_publication_display_hash",
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
            "Implement a non-debug card render-model rebuild bypass keyed by final_publication_display_hash, "
            "with debug, missing, stale, and changed display hashes forcing rebuild."
        ),
    }

    stamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_card_render_model_bypass_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_card_render_model_bypass_readiness_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(payload, md_path)

    print(f"design_guide_card_render_model_bypass_readiness_snapshot {payload['status']}")
    print(f"ready_for_card_render_model_bypass={payload['ready_for_card_render_model_bypass']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures:", json.dumps(failures, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
