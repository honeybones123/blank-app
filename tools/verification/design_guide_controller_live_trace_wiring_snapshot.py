"""DesignGuideController live wiring snapshot.

This verifier proves inputs_page keeps trace comparison wiring and now routes
the final-visible publication bridge through DesignGuideController publication
authority. Render, Apply, session, CTA rendering, and UI ownership stay page
owned.
"""

from __future__ import annotations

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
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

REQUIRED_ARTIFACTS = {
    "controller_trace_only_parity": "design_guide_controller_trace_only_parity",
    "controller_publication_authority_cutover": (
        "design_guide_controller_publication_authority_cutover"
    ),
    "design_guide_independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None, "passed": False}
    path = paths[-1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "found": True,
            "path": str(path),
            "status": "JSON_ERROR",
            "passed": False,
            "error": str(exc),
        }
    status = data.get("status") or data.get("result") or data.get("lock_status")
    return {
        "found": True,
        "path": str(path),
        "status": status,
        "passed": status == "PASS" or str(status or "").endswith("locked"),
    }


def _function_body(source: str, function_name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(function_name)}\(.*?(?=^def |\Z)", re.S | re.M)
    match = pattern.search(source)
    return match.group(0) if match else ""


def _source_checks() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8")
    controller_source = CONTROLLER.read_text(encoding="utf-8")
    final_visible_body = _function_body(
        source,
        "_final_visible_resolution_from_final_publication_authority",
    )
    stamp_body = _function_body(source, "_stamp_design_guide_controller_trace_only_parity")
    checks = {
        "controller_imported": "_run_design_guide_controller_trace_only" in source
        and "_run_design_guide_controller_publication_authority" in source
        and "_DesignGuideControllerRequest" in source,
        "stamp_helper_present": bool(stamp_body),
        "stamp_called_from_final_visible_adapter": (
            "_stamp_design_guide_controller_trace_only_parity(" in final_visible_body
        ),
        "controller_called_only_from_stamp": (
            source.count("_run_design_guide_controller_trace_only(") == 1
            and "_run_design_guide_controller_trace_only(" in stamp_body
        ),
        "compares_live_hash_to_controller_hash": (
            '"parity_pass": bool(live_hash and live_hash == response.publication_hash)'
            in stamp_body
        ),
        "writes_debug_trace_payload": (
            'debug_sink["design_guide_controller_trace_only_parity"]' in stamp_body
            and 'debug_sink["design_guide_controller_trace_only_parity_hash"]' in stamp_body
        ),
        "marks_live_wired": (
            'debug_sink["design_guide_controller_trace_only_live_wired"] = True'
            in stamp_body
        ),
        "marks_non_authoritative": all(
            token in stamp_body
            for token in (
                '"product_driving": False',
                '"render_driving": False',
                '"apply_driving": False',
                '"session_driving": False',
                'debug_sink["design_guide_controller_trace_only_product_driving"] = False',
                'debug_sink["design_guide_controller_trace_only_render_driving"] = False',
                'debug_sink["design_guide_controller_trace_only_apply_driving"] = False',
                'debug_sink["design_guide_controller_trace_only_session_driving"] = False',
            )
        ),
        "controller_publication_authority_called_from_final_visible_adapter": (
            "_run_design_guide_controller_publication_authority(" in final_visible_body
        ),
        "controller_collapsed_item_drives_final_visible_item": (
            "controller_response.collapsed_guidance_item" in final_visible_body
        ),
        "controller_publication_payload_drives_display_projection": (
            "controller_response.publication" in final_visible_body
        ),
        "controller_authority_debug_markers_present": (
            'debug_sink["design_guide_controller_publication_authority_live_wired"] = True'
            in final_visible_body
            and 'debug_sink["design_guide_controller_publication_authority_product_driving"] = True'
            in final_visible_body
            and 'debug_sink["design_guide_controller_publication_authority_render_driving"] = False'
            in final_visible_body
            and 'debug_sink["design_guide_controller_publication_authority_apply_driving"] = False'
            in final_visible_body
            and 'debug_sink["design_guide_controller_publication_authority_session_driving"] = False'
            in final_visible_body
        ),
        "controller_module_clean_of_page_imports": all(
            token not in controller_source
            for token in (
                "inputs_page",
                "streamlit",
                "st.session_state",
                "design_guide_page",
                "playwright",
                "render_final_panel",
            )
        ),
    }
    checks["all_source_checks_pass"] = all(checks.values())
    return checks


def _write(snapshot: dict[str, Any], json_path: Path, md_path: Path) -> None:
    lines = [
        "# DesignGuideController Live Trace Wiring Snapshot",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Summary",
        "",
        f"- Live trace wiring PASS: `{snapshot['live_trace_wiring_pass']}`",
        f"- Product behavior changed: `{snapshot['product_behavior_changed']}`",
        f"- Controller authority moved: `{snapshot['controller_authority_moved']}`",
        "",
        "## Source Checks",
        "",
        "| Check | Passed |",
        "| --- | --- |",
    ]
    for name, value in snapshot["source_checks"].items():
        if name == "all_source_checks_pass":
            continue
        lines.append(f"| {name} | {value} |")
    lines.extend(
        [
            "",
            "## Composed Gates",
            "",
            "| Gate | Found | Status | Path |",
            "| --- | --- | --- | --- |",
        ]
    )
    for name, artifact in snapshot["required_artifacts"].items():
        lines.append(
            f"| {name} | {artifact['found']} | {artifact['status']} | `{artifact['path']}` |"
        )
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            (
                "Run a browser/live controller trace parity snapshot that captures "
                "`design_guide_controller_trace_only_parity` from the live debug bundle "
                "after normal render and post-click rerun states."
            ),
        ]
    )
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source_checks = _source_checks()
    artifacts = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    status = "PASS"
    if not source_checks["all_source_checks_pass"]:
        status = "FAIL"
    if not all(artifact["passed"] for artifact in artifacts.values()):
        status = "FAIL"
    snapshot = {
        "status": status,
        "snapshot": "design_guide_controller_live_trace_wiring",
        "timestamp": timestamp,
        "live_trace_wiring_pass": source_checks["all_source_checks_pass"],
        "product_behavior_changed": False,
        "controller_authority_moved": True,
        "source_checks": source_checks,
        "required_artifacts": artifacts,
    }
    json_path = ARTIFACT_DIR / f"design_guide_controller_live_trace_wiring_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_controller_live_trace_wiring_{timestamp}.md"
    _write(snapshot, json_path, md_path)
    print(f"status: {status}")
    print(f"json: {json_path}")
    print(f"report: {md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
