from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"


LATEST_GATES: tuple[dict[str, str], ...] = (
    {
        "id": "design_guide_independence_lock",
        "prefix": "design_guide_independence_lock",
        "purpose": "FinalDesignGuidePublication owns final CTA/display truth.",
    },
    {
        "id": "render_bridge_lock",
        "prefix": "design_guide_render_bridge_lock",
        "purpose": "Render-stage bridges are compatibility/proof-only.",
    },
    {
        "id": "compute_resolver_publication_bridge_lock",
        "prefix": "design_guide_compute_resolver_publication_bridge_lock",
        "purpose": "Compute resolver cannot override publication after publication exists.",
    },
    {
        "id": "locked_family_live_wiring",
        "prefix": "locked_family_live_wiring_snapshot",
        "purpose": "Locked family output reaches live wiring.",
    },
    {
        "id": "shared_component_lock_matrix",
        "prefix": "design_brain_shared_component_lock_matrix",
        "purpose": "Shared Design Brain component locks remain green.",
    },
    {
        "id": "shared_apply_payload_lock",
        "prefix": "design_brain_shared_apply_payload_lock",
        "purpose": "Apply payload projection and current-state safety are locked.",
    },
    {
        "id": "shared_cta_binding_lock",
        "prefix": "design_brain_shared_cta_binding_lock",
        "purpose": "CTA binding is sourced from shared/final publication authority.",
    },
    {
        "id": "shared_filtering_lock",
        "prefix": "design_brain_shared_filtering_lock",
        "purpose": "Shared candidate filters reject invalid detailing/geometry.",
    },
    {
        "id": "shared_candidate_evaluation_lock",
        "prefix": "design_brain_shared_candidate_evaluation_lock",
        "purpose": "Shared candidate evaluation boundary remains stable.",
    },
    {
        "id": "shared_publication_assembly_lock",
        "prefix": "design_brain_shared_publication_assembly_lock",
        "purpose": "Publication assembly remains Design Brain-owned.",
    },
    {
        "id": "summary_first_paint_cache_guard",
        "prefix": "design_guide_first_paint_cached_summary_reuse",
        "purpose": "Cached first-paint summary cannot be stale or unstyled.",
    },
    {
        "id": "summary_final_render_skip_guard",
        "prefix": "design_guide_first_paint_summary_final_render_skip",
        "purpose": "Skipped final summary repaint still injects required CSS.",
    },
    {
        "id": "summary_render_reuse_lock",
        "prefix": "design_guide_stable_publication_summary_render_reuse_implementation",
        "purpose": "Summary HTML reuse remains hash-guarded.",
    },
)


QUICK_GATES: tuple[str, ...] = (
    "tools/verification/summary_sections_smoke.py",
    "tools/verification/cta_button_contract_check.py",
    "tools/verification/design_guide_first_paint_cached_summary_reuse_snapshot.py",
    "tools/verification/design_guide_first_paint_summary_final_render_skip_snapshot.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status(payload: dict[str, Any]) -> str:
    for key in ("status", "result", "lock_status"):
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        upper = value.upper()
        if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
            return "PASS"
        if "PARTIAL" in upper:
            return "PARTIAL"
        if "FAIL" in upper or "BLOCKED" in upper or "INCOMPLETE" in upper:
            return "FAIL"
        return value or "UNKNOWN"
    if payload.get("passed") is True:
        return "PASS"
    if payload.get("passed") is False:
        return "FAIL"
    return "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "status": _status(payload),
        "path": str(path),
        "payload": payload,
    }


def _run(script: str, timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        "script": script,
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    line_start = source.rfind("\n", 0, start) + 1
    header = source[line_start : source.find("\n", start)]
    indent = len(header) - len(header.lstrip(" "))
    pattern = re.compile(rf"^ {{{0},{indent}}}def\s+\w+\(", re.MULTILINE)
    for match in pattern.finditer(source, start + len(marker)):
        match_indent = len(match.group(0)) - len(match.group(0).lstrip(" "))
        if match_indent <= indent:
            return source[start : match.start()]
    return source[start:]


def _direct_checks(inputs_source: str, final_source: str) -> dict[str, bool]:
    cached_helper = _function_body(inputs_source, "_cached_summary_html_for_first_paint")
    summary_render = _function_body(inputs_source, "_render_current_inputs_summary")
    secondary_items = _function_body(inputs_source, "_render_guidance_secondary_items")
    final_publication_surface = final_source
    exact_primary_apply_key_count = len(re.findall(r'key\s*=\s*["\']apply_design_guide["\']', inputs_source))
    apply_button_keys = re.findall(r'key\s*=\s*["\'](apply_design_guide[^"\']*)["\']', inputs_source)
    return {
        "final_publication_object_exists": "class FinalDesignGuidePublication" in final_publication_surface,
        "final_publication_has_cta_display_evidence": all(
            token in final_publication_surface
            for token in ("FinalDesignGuideCTA", "FinalDesignGuideDisplay", "FinalDesignGuideEvidence")
        ),
        "summary_cached_shell_injects_card_css": "__SUMMARY_CARD_CSS__" in cached_helper
        and "_summary_card_css()" in cached_helper,
        "summary_first_paint_cache_uses_overlay_summary_fp": all(
            token in cached_helper
            for token in ("_resolved_inputs_summary_state()", "current_summary_action_fp", "stale_summary_action_fp")
        ),
        "summary_final_render_skip_reinjects_card_css": (
            "summary_final_render_skipped" in summary_render
            and "st.markdown(_summary_card_css(), unsafe_allow_html=True)" in summary_render
        ),
        "summary_html_cache_key_contains_summary_action_fp": (
            '"summary_action_fp": _stable_final_publication_hash(summary_action_fp)' in inputs_source
        ),
        "primary_apply_button_key_single_authoritative_key": exact_primary_apply_key_count == 1,
        "apply_button_keys_are_unique": len(apply_button_keys) == len(set(apply_button_keys)),
        "enabled_cta_renders_apply_button": "_design_guide_button_contract_enabled(button_contract)" in secondary_items
        and "st.button(" in secondary_items
        and "key=\"apply_design_guide\"" in secondary_items,
        "enabled_cta_records_apply_payload_before_button": (
            "_record_rendered_design_guide_primary_apply_payload(" in secondary_items
            and secondary_items.find("_record_rendered_design_guide_primary_apply_payload(")
            < secondary_items.find("st.button(")
        ),
        "fallback_cta_is_explicitly_non_primary_keyed": "apply_design_guide_final_publication_cta_fallback"
        in secondary_items,
        "advisory_path_does_not_render_apply_button": "Recommendation is advisory, not directly executable"
        in secondary_items,
    }


def _scenario_matrix() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "family_action_to_apply",
            "invariant": "Executable selected family result renders exactly one authoritative Apply CTA.",
            "proof": "CTA binding lock + source check for enabled button and unique primary key.",
        },
        {
            "scenario": "apply_once_terminal_or_blocked",
            "invariant": "Post-Apply state must settle to target band, exact stop, or blocker proof.",
            "proof": "family process/churn locks and apply payload/current-state locks.",
        },
        {
            "scenario": "widget_change_summary_freshness",
            "invariant": "Summary cache cannot reuse stale HTML after overlay-visible widget state changes.",
            "proof": "first-paint cache now includes overlay-aware summary_action_fp.",
        },
        {
            "scenario": "cached_summary_styling",
            "invariant": "Cached summary card HTML cannot mount without summary-card CSS.",
            "proof": "cached shell and final repaint skip both inject _summary_card_css().",
        },
        {
            "scenario": "post_family_publication_integrity",
            "invariant": "Render/session/fallback paths cannot reinterpret final family publication truth.",
            "proof": "independence, render bridge, and compute resolver/publication locks.",
        },
    ]


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Shared Path Product Lock",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Purpose",
        "",
        "This verifier sits above family-specific fuzz. It checks the shared path where correct family results can still be lost:",
        "",
        "`family result -> publication -> summary/card formatter -> CTA binding -> Apply payload -> post-Apply state`",
        "",
        "## Direct Shared-Path Checks",
        "",
    ]
    for key, value in payload["direct_checks"].items():
        lines.append(f"- `{key}`: `{'PASS' if value else 'FAIL'}`")
    lines.extend(["", "## Composed Latest Gates", ""])
    for row in payload["latest_gates"]:
        lines.append(f"- `{row['id']}`: `{row['status']}` ({row['path']})")
    lines.extend(["", "## Refreshed Quick Gates", ""])
    for row in payload["quick_gates"]:
        lines.append(f"- `{row['script']}`: `{'PASS' if row['passed'] else 'FAIL'}`")
    lines.extend(["", "## Scenario Coverage", ""])
    for row in payload["scenario_matrix"]:
        lines.append(f"- `{row['scenario']}`: {row['invariant']} Proof: {row['proof']}")
    if payload["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in payload["failures"])
    lines.extend(
        [
            "",
            "## What This Adds",
            "",
            "Family fuzz can prove a family selected the right result. This lock proves the shared product path cannot stale, hide, duplicate, or unstyle that result after the family returns it.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)

    latest_rows: list[dict[str, Any]] = []
    for gate in LATEST_GATES:
        latest = _latest(gate["prefix"])
        latest_rows.append({**gate, **latest})

    quick_rows = [_run(script) for script in QUICK_GATES]
    direct_checks = _direct_checks(inputs_source, final_source)

    failures: list[str] = []
    failures.extend(f"direct_check_failed:{key}" for key, ok in direct_checks.items() if not ok)
    failures.extend(
        f"latest_gate_not_pass:{row['id']}:{row['status']}"
        for row in latest_rows
        if row["status"] != "PASS"
    )
    failures.extend(
        f"quick_gate_failed:{row['script']}"
        for row in quick_rows
        if not bool(row.get("passed"))
    )

    stamp = datetime.now().replace(microsecond=0).isoformat().replace(":", "-")
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_shared_path_product_lock.v1",
        "created_at": stamp,
        "status": status,
        "direct_checks": direct_checks,
        "latest_gates": latest_rows,
        "quick_gates": quick_rows,
        "scenario_matrix": _scenario_matrix(),
        "shared_path_locked": status == "PASS",
        "product_behavior_changed": False,
        "failures": failures,
    }

    json_path = ARTIFACT_DIR / f"design_guide_shared_path_product_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_shared_path_product_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")

    print(f"design_guide_shared_path_product_lock {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
