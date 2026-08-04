"""Source snapshot for the same-page Inputs dispatch status layout guard.

This verifies the narrow layout-only guard that keeps Streamlit's transient
status chrome out of the normal document flow during same-page Inputs reruns.
It does not drive the browser and it does not change Design Guide publication,
CTA/apply semantics, family runtimes, or visible product wording.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APP_PATH = ROOT / "app.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _stable_shell_body(source: str) -> str:
    match = re.search(
        r"def _render_inputs_root_dispatch_stable_shell\(\) -> None:(?P<body>.*?)(?:\n\n    def _render_selected_page_in_content_slot)",
        source,
        re.DOTALL,
    )
    return match.group("body") if match else ""


def _checks() -> dict[str, bool]:
    source = APP_PATH.read_text(encoding="utf-8", errors="replace")
    body = _stable_shell_body(source)
    same_page_branch = re.search(
        r"if same_page_inputs_root_shell:(?P<body>.*?)(?:\n        render_timing_mark\(\"app\.page_dispatch\.page_content_slot\.clear\.start\")",
        source,
        re.DOTALL,
    )
    branch = same_page_branch.group("body") if same_page_branch else ""
    return {
        "stable_shell_helper_found": bool(body),
        "guard_is_inside_stable_shell_helper": "inputs-root-dispatch-status-layout-guard" in body,
        "guard_targets_only_streamlit_status_chrome": "[data-testid=\"stStatusWidget\"]" in body
        and "[data-testid=\"stDecoration\"]" in body
        and "summary-card" not in body
        and "design-guide" not in body,
        "guard_removes_status_from_normal_flow": "position: fixed !important" in body
        and "min-height: 0 !important" in body,
        "same_page_branch_invokes_guarded_shell": "_render_inputs_root_dispatch_stable_shell()" in branch,
        "same_page_branch_does_not_clear_page_slot": "page_content_slot.empty()" not in branch,
        "other_page_clear_path_still_exists": "app.page_dispatch.page_content_slot.clear.start" in source
        and "page_content_slot.empty()" in source,
        "no_design_brain_publication_terms_in_guard": not any(
            token in body
            for token in (
                "FinalDesignGuidePublication",
                "selected_family_id",
                "button_contract",
                "apply_payload",
                "candidate",
                "family_runtime",
            )
        ),
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide Same-Page Inputs Dispatch Status Layout Guard",
        "",
        f"Status: `{payload.get('status')}`",
        f"Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Checks",
        "",
        "```json",
        json.dumps(payload.get("checks") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Latest Prerequisites",
        "",
    ]
    for name, latest in (payload.get("latest") or {}).items():
        lines.append(f"- {name}: `{latest.get('status')}` ({latest.get('path')})")
    lines.append("")
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_page_inputs_dispatch_status_layout_guard_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_page_inputs_dispatch_status_layout_guard_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    latest = {
        "dispatch_gap_readiness": _latest("design_guide_same_page_inputs_dispatch_gap_readiness"),
        "landing_flash_guard": _latest("design_guide_same_page_landing_flash_guard_implementation"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "zero_authority_lock": _latest("design_brain_inputs_page_zero_authority_inventory_lock"),
    }
    checks = _checks()
    prerequisite_ok = (latest["dispatch_gap_readiness"].get("status") == "PASS")
    status = "PASS" if all(checks.values()) and prerequisite_ok else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_same_page_inputs_dispatch_status_layout_guard.v1",
        "created_at": _stamp(),
        "status": status,
        "checks": checks,
        "latest": latest,
        "product_behaviour_changed": False,
        "behaviour_scope": {
            "layout_changed": True,
            "rendering_changed": False,
            "publication_changed": False,
            "cta_apply_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
            "engineering_behaviour_changed": False,
        },
    }
    json_path, md_path = _write(payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
