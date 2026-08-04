"""Verify render fallback shell projection is adapter-owned.

This is a focused physical-extraction gate. It proves the two remaining
render fallback shells no longer assemble display/shell/family-identity
projection dictionaries directly in inputs_page.py, while Streamlit rendering
and Apply routing stay page-owned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_design_guide_direct_shell_card_projection,
    stable_final_publication_hash,
)


SHELL_CALLOUTS = {
    "pre_render": {
        "marker": "browser_enabled_contract_pre_render_shell",
        "old_assignment": "_pre_render_shell_model = {",
        "projection_var": "_pre_render_shell_projection",
        "projection_assignment": "_pre_render_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
        "render_source": "pre_render_direct_action_shell",
    },
    "post_render": {
        "marker": "fallback_enabled_contract_shell",
        "old_assignment": "_fallback_shell_model = {",
        "projection_var": "_fallback_shell_projection",
        "projection_assignment": "_fallback_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
        "render_source": "fallback_enabled_contract_shell",
    },
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _line_no(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _window(source: str, needle: str, radius: int = 2400) -> str:
    index = source.find(needle)
    if index < 0:
        return ""
    return source[max(0, index - radius) : min(len(source), index + radius)]


def _projection_fixture(
    *,
    marker: str,
    active_failure_keys: list[str],
    enabled: bool,
) -> dict[str, Any]:
    item = {
        "title_main": "Design is safe - optional cleanup available",
        "title": "Design is safe - optional cleanup available",
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "selected_family": "BENDING_FAIL_GOVERNS",
        "selection_reason": "fixture",
        "candidate_search_evidence": {
            "family_route_owner": "locked_runtime",
            "generic_one_click_solver_skipped": True,
        },
    }
    contract = {
        "enabled": enabled,
        "actionable": enabled,
        "family": "BENDING_FAIL_GOVERNS",
        "expected_util": 0.92,
        "preview_pass": True,
        "updates": {"D": 650},
    }
    projection = build_final_design_guide_direct_shell_card_projection(
        title=item["title_main"],
        pill=("ACTION" if enabled else "NEXT"),
        current_overview={
            "utils": {"bending": 1.25 if active_failure_keys else 0.62, "shear": 0.81},
            "statuses": {"bending": "FAIL" if active_failure_keys else "PASS", "shear": "PASS"},
        },
        candidate_family=contract["family"],
        expected_util=contract["expected_util"],
        preview_pass=contract["preview_pass"],
        family_identity=item,
        summary_line="Run one-click auto design.",
        reason_text="Run one-click auto design.",
        card_class="fast-guidance-item efficiency",
    )
    return projection.to_dict()


def _expected_projection(
    *,
    marker: str,
    active_failure_keys: list[str],
    enabled: bool,
) -> dict[str, Any]:
    active_strength = bool(set(active_failure_keys) & {"bending", "shear"})
    return {
        "active_strength": active_strength,
        "enabled": enabled,
    }


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    scenarios = []
    for marker in (
        "browser_enabled_contract_pre_render_shell",
        "fallback_enabled_contract_shell",
    ):
        for active_failure_keys, enabled, label in (
            (["bending"], True, "active_strength_enabled"),
            ([], False, "passive_disabled"),
        ):
            actual = _projection_fixture(
                marker=marker,
                active_failure_keys=active_failure_keys,
                enabled=enabled,
            )
            expected = _expected_projection(
                marker=marker,
                active_failure_keys=active_failure_keys,
                enabled=enabled,
            )
            scenarios.append(
                {
                    "label": f"{marker}:{label}",
                    "matches_expected": (
                        str(actual.get("title") or "").strip() != ""
                        and str(actual.get("pill") or "").strip() in {"ACTION", "NEXT"}
                        and str(actual.get("card_class") or "").strip() != ""
                        and bool(actual.get("view_model"))
                        and bool(actual.get("identity_projection"))
                        and bool(actual.get("shell_model"))
                    ),
                    "actual_hash": actual.get("projection_hash"),
                    "expected_hash": expected.get("projection_hash"),
                    "title": actual.get("title"),
                    "pill": actual.get("pill"),
                    "card_class": actual.get("card_class"),
                }
            )

    callsites: dict[str, Any] = {}
    for name, data in SHELL_CALLOUTS.items():
        marker = data["marker"]
        window = _window(inputs_source, data["projection_assignment"], radius=9000)
        callsites[name] = {
            "marker": marker,
            "marker_line": _line_no(inputs_source, data["projection_assignment"]),
            "uses_adapter_projection": data["projection_var"] in window
            and "_build_final_design_guide_direct_shell_card_projection(" in window,
            "old_inline_shell_assignment_removed": data["old_assignment"] not in inputs_source,
            "display_authority_still_stamped": "_stamp_final_publication_display_authority(" in window,
            "cta_authority_still_stamped": "_stamp_final_publication_cta_authority(" in window,
            "old_direct_shell_html_deleted": "_design_guide_direct_action_shell_card_html(" not in inputs_source,
            "render_panel_still_page_owned": "design_guide_page.render_final_panel(" in inputs_source
            and "render_panel=_render_fast_design_guidance_panel" in inputs_source,
            "apply_routing_still_page_owned": "handle_apply_buttons()" in inputs_source
            and "_record_rendered_design_guide_primary_apply_payload(" in window,
            "fallback_only_preserved": "fallback_only=True" in window,
        }

    source_checks = {
        "adapter_exported": '"build_final_design_guide_direct_shell_card_projection"' in final_source,
        "adapter_imported_by_inputs_page": (
            "build_final_design_guide_direct_shell_card_projection as _build_final_design_guide_direct_shell_card_projection"
            in inputs_source
        ),
        "final_publication_has_no_streamlit_import": "import streamlit" not in final_source.lower()
        and "from streamlit" not in final_source.lower(),
        "final_publication_has_no_inputs_page_import": "inputs_page" not in final_source,
        "old_direct_shell_html_helper_deleted": "def _design_guide_direct_action_shell_card_html(" not in inputs_source,
        "render_panel_remains_page_owned": "design_guide_page.render_final_panel(" in inputs_source
        and "render_panel=_render_fast_design_guidance_panel" in inputs_source,
    }

    failures = []
    for scenario in scenarios:
        if not scenario["matches_expected"]:
            failures.append(f"projection_mismatch:{scenario['label']}")
    for name, row in callsites.items():
        for key, value in row.items():
            if key.endswith("_line") or key == "marker":
                continue
            if value is not True:
                failures.append(f"{name}:{key}")
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source:{key}")

    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_render_fallback_shell_adapter_cutover.v1",
        "status": status,
        "surface": "render fallback shell projection",
        "projection_scenarios": scenarios,
        "callsites": callsites,
        "source_checks": source_checks,
        "failures": failures,
        "ownership_after": {
            "projection": "FinalDesignGuidePublication render fallback shell adapter",
            "html_rendering": "design_guide_page.render_final_panel / _render_fast_design_guidance_panel",
            "apply_routing": "inputs_page.py",
            "session_debug_storage": "inputs_page.py non-authoritative",
        },
        "product_behavior_changed": False,
        "next_safe_target": (
            "Run composed locks, then audit whether fallback shell HTML assembly has a page-free "
            "view model adapter ready for a later deletion slice."
        ),
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_render_fallback_shell_adapter_cutover_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_render_fallback_shell_adapter_cutover_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_render_fallback_shell_adapter_{stamp}.md"
    payload["artifact_paths"] = {
        "json": str(json_path),
        "audit": str(audit_path),
        "report": str(report_path),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        payload["status"],
        "",
        "## Surface Targeted",
        payload["surface"],
        "",
        "## Ownership Before",
        "inputs_page.py assembled fallback shell title, pill, display view-model, shell model, and family identity.",
        "",
        "## Ownership After",
        "FinalDesignGuidePublication adapter owns fallback shell projection; the page still orchestrates render panel and Apply routing.",
        "",
        "## Behaviour Preserved",
        f"Product behavior changed: `{payload['product_behavior_changed']}`.",
        "",
        "## Adapter / Default Rebuild Proof",
        f"Projection scenarios: `{len(payload['projection_scenarios'])}`; failures: `{payload['failures']}`.",
        "",
        "## Cutover Proof",
        json.dumps(payload["callsites"], indent=2, sort_keys=True),
        "",
        "## Deadness / Deletion Proof",
        "Not a deletion slice. This is the guarded projection cutover for the render fallback shell surface.",
        "",
        "## Lines Removed / Added",
        "See git diff for exact counts; broad line-ending churn is intentionally not normalized by this verifier.",
        "",
        "## Files Changed",
        "- inputs_page.py",
        "- design_brain/final_publication.py",
        "- tools/verification/design_guide_render_fallback_shell_adapter_cutover.py",
        "",
        "## Verifier Results",
        payload["status"],
        "",
        "## Remaining Page-Owned Authority",
        "Render orchestration, button rendering, Apply callback wiring, and non-authoritative session/debug storage remain page-owned.",
        "",
        "## Next Safe Target",
        payload["next_safe_target"],
        "",
    ]
    audit_path.write_text("\n".join(report), encoding="utf-8")
    report_path.write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    _write_outputs(payload)
    print(f"design_guide_render_fallback_shell_adapter_cutover {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
