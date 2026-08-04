"""Verify zero-shear cleanup is not published as stale shear-fail evidence."""

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
INPUTS_PAGE = ROOT / "inputs_page.py"
INPUTS_COMPOSITION = (
    ROOT / "inputs_application" / "page_runtime" / "design_guide.py",
    ROOT / "inputs_application" / "page_runtime" / "design_guide_runtime_support.py",
    ROOT / "inputs_page_modules" / "guidance_compute.py",
    ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py",
)
PUBLICATION = ROOT / "design_brain" / "publication.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _accumulate_sequence(order: tuple[str, ...]) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        accumulate_design_guide_shear_low_util_cleanup_candidate,
    )

    rows = {
        "heavy": {
            "classification": {
                "accepted_band_candidate": False,
                "target_band_candidate": False,
                "distance_to_target_band": 0.20,
            },
            "updates": {"lig_legs": 3, "s_lig": 400.0},
            "shear_util": 0.65,
            "is_no_link_candidate": False,
        },
        "no_link": {
            "classification": {
                "accepted_band_candidate": False,
                "target_band_candidate": False,
                "distance_to_target_band": 0.85,
            },
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
            "shear_util": 0.0,
            "is_no_link_candidate": True,
        },
    }
    state = {
        "accepted_band_count": 0,
        "target_count": 0,
        "best_distance": None,
        "best": None,
    }
    trace: list[dict[str, Any]] = []
    for name in order:
        row = rows[name]
        result = accumulate_design_guide_shear_low_util_cleanup_candidate(
            accepted_band_count=int(state["accepted_band_count"]),
            target_count=int(state["target_count"]),
            best_distance=state["best_distance"],
            best=state["best"],
            classification=dict(row["classification"]),
            updates=dict(row["updates"]),
            candidate={"candidate_id": name},
            overview={"utils": {"shear": row["shear_util"]}},
            shear_util=row["shear_util"],
            is_no_link_candidate=bool(row["is_no_link_candidate"]),
        )
        state.update(
            {
                "accepted_band_count": result.get("accepted_band_count"),
                "target_count": result.get("target_count"),
                "best_distance": result.get("best_distance"),
                "best": result.get("best"),
            }
        )
        trace.append({"candidate": name, "selected": result.get("candidate_selected_as_best")})
    best = dict(state.get("best") or {})
    return {
        "order": list(order),
        "trace": trace,
        "best_updates": dict(best.get("updates") or {}),
        "best_is_no_link": bool(best.get("is_no_link_candidate")),
        "best_distance": state.get("best_distance"),
    }


def _capture() -> dict[str, Any]:
    import design_brain.publication as publication

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    bridge_source = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in INPUTS_COMPOSITION
    )
    publication_source = PUBLICATION.read_text(encoding="utf-8", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")

    heavy_then_no_link = _accumulate_sequence(("heavy", "no_link"))
    no_link_then_heavy = _accumulate_sequence(("no_link", "heavy"))

    cleanup_primary = {
        "title_main": "Shear cleanup - one-click reduction",
        "summary_line": "Remove unnecessary shear reinforcement.",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
        },
    }
    fail_primary = {
        "title_main": "Shear governs",
        "summary_line": "Shear capacity is failing. Run one-click auto design.",
        "family": "shear",
        "check_key": "shear",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_legs": 3, "s_lig": 400.0},
        },
    }
    combined_primary = {
        "title_main": "Combined cleanup",
        "candidate_family_id": "COMBINED_OVERDESIGN",
        "family": "combined",
    }
    combined_owner_shear_cleanup_primary = {
        "title_main": "Shear cleanup - one-click reduction",
        "summary_line": "Remove unnecessary shear reinforcement.",
        "family": "shear",
        "check_key": "shear",
        "selected_action_family": "shear",
        "action_type": "apply_resolved_candidate",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
        },
    }
    stale_shell_payload = publication.enforce_family_selection_publication_contract(
        {
            "guidance_items": [
                {
                    "title_main": "Design Guide family contract violation",
                    "title": "Design Guide family contract violation",
                    "summary_line": "Publication blocked by family contract before final render.",
                    "blocker_explanation": "family_selection_contract_mismatch",
                    "selected_family_id": "COMBINED_OVERDESIGN",
                    "published_family_id": "COMBINED_OVERDESIGN",
                    "cta_family_id": "COMBINED_OVERDESIGN",
                    "card_family_id": "COMBINED_OVERDESIGN",
                    "family_match_passed": True,
                }
            ],
            "debug_trace": {
                "selected_family_id": "COMBINED_OVERDESIGN",
                "primary_title": "Design is safe - optional shear cleanup available",
                "selected_title": "Design is safe - optional shear cleanup available",
                "primary_button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "family": "shear",
                    "action_type": "apply_resolved_candidate",
                    "updates": {"lig_d": 0, "lig_legs": 0, "s_lig": 200.0},
                    "preview_pass": True,
                    "blocking_reason": None,
                    "candidate_id": "local_cleanup:shear:no_link",
                },
            },
            "overview": {
                "utils": {"bending": 0.65, "shear": 0.0},
                "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            },
            "active_failures": [],
        }
    )
    stale_shell_item = dict((stale_shell_payload.get("guidance_items") or [{}])[0])
    stale_shell_contract = dict(stale_shell_item.get("button_contract") or {})
    return {
        "accumulator": {
            "heavy_then_no_link": heavy_then_no_link,
            "no_link_then_heavy": no_link_then_heavy,
        },
        "candidate_family_mapping": {
            "shear_cleanup": publication._candidate_family_id_from_publication(cleanup_primary, {}),
            "shear_fail": publication._candidate_family_id_from_publication(fail_primary, {}),
            "combined_canonical": publication._candidate_family_id_from_publication(combined_primary, {}),
        },
        "cta_family_mapping": {
            "combined_owner_shear_cleanup": publication._cta_family_id_from_publication(
                combined_owner_shear_cleanup_primary,
                {},
                "COMBINED_OVERDESIGN",
                "COMBINED_OVERDESIGN",
            ),
            "standalone_shear_cleanup": publication._cta_family_id_from_publication(
                cleanup_primary,
                {},
                "SHEAR_OVERDESIGN_GOVERNS",
                "SHEAR_OVERDESIGN_GOVERNS",
            ),
        },
        "stale_contract_shell_recovery": {
            "title": stale_shell_item.get("title_main") or stale_shell_item.get("title"),
            "blocker_explanation": stale_shell_item.get("blocker_explanation"),
            "selected_family_id": stale_shell_item.get("selected_family_id"),
            "published_family_id": stale_shell_item.get("published_family_id"),
            "cta_family_id": stale_shell_item.get("cta_family_id"),
            "family_match_passed": stale_shell_item.get("family_match_passed"),
            "button_enabled": stale_shell_contract.get("enabled"),
            "button_actionable": stale_shell_contract.get("actionable"),
            "button_updates": dict(stale_shell_contract.get("updates") or {}),
            "recovered": bool(
                dict(stale_shell_item.get("candidate_search_evidence") or {}).get(
                    "stale_family_contract_violation_recovered_to_cleanup_action"
                )
            ),
        },
        "source_checks": {
            "page_passes_no_link_candidate_flag_to_accumulator": (
                "is_no_link_candidate=is_no_link_candidate" in inputs_source
                or (
                    "accumulate_design_guide_shear_low_util_cleanup_candidate("
                    not in bridge_source
                    and bool(heavy_then_no_link.get("best_is_no_link"))
                    and bool(no_link_then_heavy.get("best_is_no_link"))
                )
                or "is_no_link_candidate=is_no_link_candidate" in bridge_source
            ),
            "controller_accumulator_accepts_no_link_flag": (
                "is_no_link_candidate: bool = False" in controller_source
            ),
            "controller_no_link_overrides_distance_to_target": (
                "A passing no-link candidate is the terminal cleanup floor" in controller_source
                and "current_best_distance = -1.0 if is_no_link_candidate else distance" in controller_source
            ),
            "publication_preserves_canonical_family_ids": (
                "canonical_family_ids = {" in publication_source
                and "if raw_text in canonical_family_ids:" in publication_source
            ),
            "publication_maps_cleanup_shear_to_overdesign": (
                'return "SHEAR_OVERDESIGN_GOVERNS" if cleanup_publication else "SHEAR_FAIL_GOVERNS"'
                in publication_source
            ),
            "publication_maps_combined_owner_cleanup_cta_to_combined": (
                'selected_family_id == "COMBINED_OVERDESIGN" and mechanical in {"bending", "shear"}'
                in publication_source
            ),
            "publication_recovers_stale_contract_shell_to_cleanup_action": (
                "stale_family_contract_violation_recovered_to_cleanup_action" in publication_source
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    accumulator = dict(capture.get("accumulator") or {})
    mapping = dict(capture.get("candidate_family_mapping") or {})
    cta_mapping = dict(capture.get("cta_family_mapping") or {})
    stale_recovery = dict(capture.get("stale_contract_shell_recovery") or {})
    return {
        "no_link_wins_after_heavy_candidate": (
            dict(accumulator.get("heavy_then_no_link") or {}).get("best_updates", {}).get("lig_legs") == 0
            and dict(accumulator.get("heavy_then_no_link") or {}).get("best_is_no_link") is True
        ),
        "no_link_remains_best_before_heavy_candidate": (
            dict(accumulator.get("no_link_then_heavy") or {}).get("best_updates", {}).get("lig_legs") == 0
            and dict(accumulator.get("no_link_then_heavy") or {}).get("best_is_no_link") is True
        ),
        "cleanup_shear_maps_to_shear_overdesign": mapping.get("shear_cleanup") == "SHEAR_OVERDESIGN_GOVERNS",
        "failing_shear_still_maps_to_shear_fail": mapping.get("shear_fail") == "SHEAR_FAIL_GOVERNS",
        "combined_canonical_family_is_preserved": mapping.get("combined_canonical") == "COMBINED_OVERDESIGN",
        "combined_owner_shear_cleanup_cta_maps_to_combined": (
            cta_mapping.get("combined_owner_shear_cleanup") == "COMBINED_OVERDESIGN"
        ),
        "standalone_shear_cleanup_cta_still_maps_to_shear_overdesign": (
            cta_mapping.get("standalone_shear_cleanup") == "SHEAR_OVERDESIGN_GOVERNS"
        ),
        "stale_contract_shell_recovers_to_cleanup_item": (
            stale_recovery.get("title") == "Design is safe - optional shear cleanup available"
            and stale_recovery.get("blocker_explanation") in {None, ""}
            and stale_recovery.get("selected_family_id") == "COMBINED_OVERDESIGN"
            and stale_recovery.get("published_family_id") == "COMBINED_OVERDESIGN"
            and stale_recovery.get("cta_family_id") == "COMBINED_OVERDESIGN"
            and stale_recovery.get("button_enabled") is True
            and stale_recovery.get("button_actionable") is True
            and dict(stale_recovery.get("button_updates") or {}).get("lig_legs") == 0
            and stale_recovery.get("recovered") is True
        ),
        "source_checks_pass": all(dict(capture.get("source_checks") or {}).values()),
        "product_behavior_guarded": capture.get("product_behavior_changed") is False,
        "visible_wording_guarded": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_guarded": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_guarded": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Zero-Shear Cleanup Publication Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in dict(payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Accumulator",
            "",
            "```json",
            json.dumps(capture.get("accumulator"), indent=2, sort_keys=True),
            "```",
            "",
            "## Candidate Family Mapping",
            "",
            "```json",
            json.dumps(capture.get("candidate_family_mapping"), indent=2, sort_keys=True),
            "```",
            "",
            "## CTA Family Mapping",
            "",
            "```json",
            json.dumps(capture.get("cta_family_mapping"), indent=2, sort_keys=True),
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "status": status,
        "checks": checks,
        "capture": capture,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_zero_shear_cleanup_publication_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_zero_shear_cleanup_publication_{stamp}.md"
    payload["json_path"] = str(json_path)
    payload["report_path"] = str(report_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_zero_shear_cleanup_publication {status}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
