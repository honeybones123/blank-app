from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            matches.append((node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_initial_cache_compute_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_initial_cache_compute_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_initial_cache_compute_current_coordinator",
    )
    panel_source, panel_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("design_guide_initial_cache_compute_coordinator_missing")
    if coordinator_size > 175:
        failures.append(f"design_guide_initial_cache_compute_coordinator_too_large:{coordinator_size}")

    for required in [
        "CODEX_DG_STAGE_DEBUG",
        "inputs_render_audit[\"design_guide_rendered\"] = \"yes\"",
        "_design_guide_banner_generic_only",
        "_sync_auto_design_mode_tracking(_shared_state_snapshot())",
        'st.markdown("### Design Guide")',
        "_render_auto_design_main_panel_status()",
        "current_state, _ = _resolved_inputs_summary_state()",
        "DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY",
        "DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY",
        "fingerprint = _get_design_guide_fp(current_state)",
        "_design_guide_sidebar_debug_enabled()",
        "_reset_design_guide_reco_trace()",
        "DESIGN_GUIDE_NEEDS_REFRESH_KEY",
        "_mark_design_guide_dirty()",
        "Auto-clearing design guide refresh gate",
        "_get_cached_design_guide_guidance(fingerprint)",
        "_design_guide_cached_debug_bundle_complete",
        "_repair_incomplete_design_guide_cache_debug(",
        "_clear_design_guide_transient_ui_state(clear_history=False, preserve_apply_banner=True)",
        "_apply_guidance_ui_state(",
        "_compute_design_guidance_items(",
        "DESIGN_GUIDE_APPLY_BANNER_KEY",
        "Design guide cache coherence",
        "guidance_compute_ms",
        "DESIGN_GUIDE_RECO_TRACE_KEY",
        "guidance_disp_state",
        '"stage": _stage',
        '"guidance_items_raw": guidance_items_raw',
        '"guidance_debug": guidance_debug',
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_design_guide_initial_cache_compute_current_coordinator("
    if call_text not in panel_source:
        failures.append("panel_missing_initial_cache_compute_call")

    for stale in [
        "CODEX_DG_STAGE_DEBUG",
        'st.markdown("### Design Guide")',
        "_render_auto_design_main_panel_status()",
        "current_state, _ = _resolved_inputs_summary_state()",
        "_get_cached_design_guide_guidance(fingerprint)",
        "_compute_design_guidance_items(",
        "Design guide cache coherence",
        "guidance_compute_ms = round((time.perf_counter() - guidance_started_at)",
    ]:
        if stale in panel_source:
            failures.append(f"panel_still_owns_{stale}")

    call_index = panel_source.find(call_text)
    assignment_index = panel_source.find('guidance_items_raw = list(_dg_initial["guidance_items_raw"] or [])')
    dedupe_index = panel_source.find("_dedupe_guidance_items_for_display(")
    if not (0 <= call_index < assignment_index < dedupe_index):
        failures.append(
            "design_guide_initial_cache_compute_call_order_changed:"
            f"call={call_index}:assignment={assignment_index}:dedupe={dedupe_index}"
        )

    payload = {
        "verifier": "inputs_page_design_guide_initial_cache_compute_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "panel_size": panel_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Initial Cache Compute Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Panel size: `{panel_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
