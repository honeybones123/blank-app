"""Trace-only clean Design Guide formatter wiring snapshot.

This verifier proves the clean FinalDesignGuidePublication formatter is wired
beside the current live card render path without driving product output.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PATH = ROOT / "inputs_page.py"


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno or node.lineno])
    return ""


def _synthetic_trace() -> dict[str, Any]:
    import inputs_page  # noqa: WPS433
    from ui.design_guide_models import DesignGuideCardRenderModel

    vm = {
        "selected_family_id": "BENDING_FAIL_GOVERNS",
        "published_family_id": "BENDING_FAIL_GOVERNS",
        "cta_family_id": "BENDING_FAIL_GOVERNS",
        "status": "action",
        "pill": "ACTION",
        "title": "Strengthening required",
        "title_main": "Strengthening required",
        "summary_line": "Run one-click auto design.",
        "bucket": "fail",
        "tone": "fail",
        "button_contract": {
            "enabled": True,
            "actionable": True,
            "label": "Run one-click auto design",
            "action_type": "apply_resolved_candidate",
            "family": "BENDING_FAIL_GOVERNS",
            "updates": {"depth": 650},
            "source_candidate_id": "trace-clean-format-bending",
        },
        "action_payload": {
            "action_type": "apply_resolved_candidate",
            "updates": {"depth": 650},
        },
        "reasons": [{"label": "Result", "text": "Run one-click auto design.", "tone": "red"}],
        "current": [
            {"family": "bending", "label": "Bending", "value": "1.12", "status": "FAIL", "tone": "red"},
            {"family": "shear", "label": "Shear", "value": "0.82", "status": "PASS", "tone": "green"},
        ],
        "preview": {
            "bending": {"before": "1.12 FAIL", "after": "0.91 PASS"},
        },
    }
    render_model = DesignGuideCardRenderModel(
        family="BENDING_FAIL_GOVERNS",
        family_label="BENDING_FAIL_GOVERNS",
        title="Strengthening required",
        status="action",
        pill="ACTION",
        governing_label="Governing utilisation 1.12",
        main_text="Run one-click auto design.",
        reason_display_rows=[{"test_label": "result", "label": "Result", "text": "Run one-click auto design."}],
        cta_label="Run one-click auto design",
        cta_enabled=True,
        cta_reason="",
        card_tone="fail",
        card_class="fast-guidance-item fail",
        current_rows=vm["current"],
        preview_display_rows=[{"family": "bending", "label": "Bending", "before": "1.12 FAIL", "after": "0.91 PASS"}],
        section_title="Status",
    )
    debug_sink: dict[str, Any] = {}
    first = inputs_page._trace_final_design_guide_clean_formatter_live_wiring(
        view_model=dict(vm),
        render_model=render_model,
        debug_sink=debug_sink,
        source="synthetic_trace_wiring_snapshot",
    )
    second_debug: dict[str, Any] = {}
    second = inputs_page._trace_final_design_guide_clean_formatter_live_wiring(
        view_model=dict(vm),
        render_model=render_model,
        debug_sink=second_debug,
        source="synthetic_trace_wiring_snapshot",
    )
    return {
        "first": first,
        "second": second,
        "debug_sink": debug_sink,
        "second_debug_sink": second_debug,
        "trace_hash_stable": first.get("trace_hash") == second.get("trace_hash"),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_clean_formatter_trace_wiring_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_clean_formatter_trace_wiring_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Guide Clean Formatter Trace Wiring Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Classification",
        "",
        f"- Trace wired: `{snapshot['checks'].get('wrapper_calls_trace_helper')}`",
        f"- Product-driving: `{snapshot['trace'].get('first', {}).get('product_driving')}`",
        f"- Render-driving: `{snapshot['trace'].get('first', {}).get('render_driving')}`",
        f"- Parity status: `{snapshot['trace'].get('first', {}).get('parity_status')}`",
        f"- Ready for live cutover: `{snapshot['trace'].get('first', {}).get('ready_for_live_cutover')}`",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    source = INPUTS_PATH.read_text(encoding="utf-8", errors="replace")
    wrapper = _function_source(source, "_design_guide_dashboard_card_html_with_render_model")
    trace_helper = _function_source(source, "_trace_final_design_guide_clean_formatter_live_wiring")
    trace = _synthetic_trace()
    first = dict(trace.get("first") or {})
    checks = {
        "imports_clean_formatter": "_build_final_design_guide_card_format" in source,
        "imports_clean_renderer": "_render_final_design_guide_card_html" in source,
        "trace_helper_present": bool(trace_helper),
        "wrapper_calls_trace_helper": "_trace_final_design_guide_clean_formatter_live_wiring(" in wrapper,
        "wrapper_no_longer_returns_legacy_html": "_design_guide_dashboard_card_html_from_render_model(" not in wrapper,
        "wrapper_returns_clean_html": "return clean_html" in wrapper,
        "trace_product_driving_false": first.get("product_driving") is False,
        "trace_render_driving_false": first.get("render_driving") is False,
        "trace_apply_driving_false": first.get("apply_driving") is False,
        "trace_session_driving_false": first.get("session_driving") is False,
        "trace_hash_stable": bool(trace.get("trace_hash_stable")),
        "trace_stamped_debug": "final_design_guide_clean_formatter_trace_only" in dict(trace.get("debug_sink") or {}),
        "publication_hash_present": bool(first.get("publication_hash")),
        "clean_format_hash_present": bool(first.get("clean_format_hash")),
        "clean_html_hash_present": bool(first.get("clean_html_hash")),
        "live_render_model_hash_present": bool(first.get("live_render_model_hash")),
        "strict_mismatch_surface_present": isinstance(first.get("strict_mismatches"), dict),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_clean_formatter_trace_wiring_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "trace": trace,
        "trace_hash": _stable_hash(trace),
        "classification": {
            "product_behavior_changed": False,
            "visible_behavior_changed": False,
            "clean_formatter_product_driving": False,
            "ready_for_live_cutover": bool(first.get("ready_for_live_cutover")) and not failures,
            "ready_for_deletion": False,
            "next_required_slice": first.get("next_required_slice") or "clean_formatter_trace_mismatch_audit",
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_guide_clean_formatter_trace_wiring FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("design_guide_clean_formatter_trace_wiring PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
