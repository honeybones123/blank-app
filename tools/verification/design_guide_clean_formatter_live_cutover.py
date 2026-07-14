"""Clean Design Guide formatter live cutover verifier."""

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


def _synthetic_cutover() -> dict[str, Any]:
    import inputs_page  # noqa: WPS433

    button_contract = {
        "enabled": True,
        "actionable": True,
        "label": "Run one-click auto design",
        "action_type": "apply_resolved_candidate",
        "family": "BENDING_FAIL_GOVERNS",
        "updates": {"depth": 650},
        "source_candidate_id": "live-cutover-clean-format-bending",
    }
    action_payload = {
        "action_type": "apply_resolved_candidate",
        "updates": {"depth": 650},
    }
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
        "cta": {
            "enabled": True,
            "actionable": True,
            "label": "Run one-click auto design",
            "disabled_reason": "",
        },
        "button_contract": dict(button_contract),
        "action_payload": dict(action_payload),
        "details": {
            "button_contract": dict(button_contract),
            "action_payload": dict(action_payload),
        },
        "reasons": [{"label": "Result", "text": "Run one-click auto design.", "tone": "red"}],
        "current": [
            {"family": "bending", "label": "Bending", "value": "1.12", "status": "FAIL", "tone": "red"},
            {"family": "shear", "label": "Shear", "value": "0.82", "status": "PASS", "tone": "green"},
        ],
        "preview": {"bending": {"before": "1.12 FAIL", "after": "0.91 PASS"}},
    }
    html = inputs_page._design_guide_dashboard_card_html_with_render_model(
        vm,
        card_class="fast-guidance-item fail",
        source="synthetic_clean_formatter_live_cutover",
    )
    debug = dict(inputs_page.st.session_state.get(inputs_page.DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})
    proof = dict(debug.get("final_design_guide_clean_formatter_trace_only") or {})
    return {
        "html_hash": _stable_hash(html),
        "html_sample": html[:900],
        "uses_clean_fdg_card_class": "fdg-card" in html,
        "uses_design_guide_card_test_id": "data-testid='design-guide-card'" in html
        or 'data-testid="design-guide-card"' in html,
        "legacy_fallback_available": bool(debug.get("final_design_guide_clean_formatter_legacy_fallback_available")),
        "legacy_fallback_used": bool(debug.get("final_design_guide_clean_formatter_legacy_fallback_used")),
        "live_cutover": bool(debug.get("final_design_guide_clean_formatter_live_cutover")),
        "trace_proof": proof,
        "debug_keys": sorted(key for key in debug if "clean_formatter" in str(key)),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_clean_formatter_live_cutover_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_clean_formatter_live_cutover_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Guide Clean Formatter Live Cutover",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Cutover",
        "",
        f"- Live cutover: `{snapshot['synthetic_cutover'].get('live_cutover')}`",
        f"- Legacy fallback available: `{snapshot['synthetic_cutover'].get('legacy_fallback_available')}`",
        f"- Legacy fallback used: `{snapshot['synthetic_cutover'].get('legacy_fallback_used')}`",
        f"- Parity status: `{snapshot['synthetic_cutover'].get('trace_proof', {}).get('parity_status')}`",
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
    cutover = _synthetic_cutover()
    proof = dict(cutover.get("trace_proof") or {})
    checks = {
        "trace_helper_present": bool(trace_helper),
        "wrapper_calls_trace_helper": "_trace_final_design_guide_clean_formatter_live_wiring(" in wrapper,
        "wrapper_does_not_build_legacy_html": "_design_guide_dashboard_card_html_from_render_model(" not in wrapper,
        "wrapper_returns_clean_html_on_ready": "return clean_html" in wrapper,
        "wrapper_fallback_uses_clean_html": "final_design_guide_clean_formatter_clean_fallback_used" in wrapper,
        "legacy_fallback_marked_available": "final_design_guide_clean_formatter_legacy_fallback_available" in wrapper,
        "legacy_renderer_deleted_marker": "final_design_guide_clean_formatter_legacy_renderer_deleted" in wrapper,
        "synthetic_live_cutover_true": cutover.get("live_cutover") is True,
        "synthetic_uses_clean_html": cutover.get("uses_clean_fdg_card_class") is True,
        "synthetic_keeps_design_guide_card_test_id": cutover.get("uses_design_guide_card_test_id") is True,
        "synthetic_legacy_fallback_removed": cutover.get("legacy_fallback_available") is False,
        "synthetic_legacy_fallback_not_used": cutover.get("legacy_fallback_used") is False,
        "trace_parity_pass": proof.get("parity_status") == "PASS",
        "trace_ready_for_live_cutover": proof.get("ready_for_live_cutover") is True,
        "trace_not_product_driving": proof.get("product_driving") is False,
        "trace_not_apply_driving": proof.get("apply_driving") is False,
        "trace_not_session_driving": proof.get("session_driving") is False,
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_clean_formatter_live_cutover.v1",
        "result": "PASS" if not failures else "FAIL",
        "checks": checks,
        "synthetic_cutover": cutover,
        "classification": {
            "clean_formatter_live_authority": not failures,
            "legacy_formatter_deleted": not failures,
            "ready_for_deletion": False,
            "next_required_slice": "clean_formatter_browser_live_cutover_snapshot",
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("design_guide_clean_formatter_live_cutover FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("design_guide_clean_formatter_live_cutover PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
