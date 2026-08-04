"""Proof-only readiness snapshot for the same-page Inputs dispatch gap.

This verifier composes the latest live rerun/status-widget gap evidence with a
direct source check of ``app.py``. It answers whether the transient large gap is
ready for a narrow app-dispatch layout guard, without changing product
behaviour, Design Guide publication, CTA/apply semantics, family runtimes, or
visible wording.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APP_PATH = ROOT / "app.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> tuple[Path | None, dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return None, {}
    path = paths[-1]
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, {}


def _line_number(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def _extract_function(source: str, function_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(function_name)}\(\) -> None:\n", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    start = match.start()
    next_match = re.search(r"^    (?:def|if |try:|with |render_timing_mark\()", source[match.end() :], re.MULTILINE)
    if not next_match:
        return source[start:]
    return source[start : match.end() + next_match.start()]


def _source_evidence() -> dict[str, Any]:
    source = APP_PATH.read_text(encoding="utf-8")
    dispatch_fn = _extract_function(source, "_render_selected_page_in_content_slot")
    same_page_branch_match = re.search(
        r"if same_page_inputs_root_shell:(?P<body>.*?)(?:\n        render_timing_mark\(\"app\.page_dispatch\.page_content_slot\.clear\.start\")",
        dispatch_fn,
        re.DOTALL,
    )
    same_page_branch = same_page_branch_match.group("body") if same_page_branch_match else ""
    clear_path_match = re.search(
        r"render_timing_mark\(\"app\.page_dispatch\.page_content_slot\.clear\.start\".*?with page_content_slot\.container\(\):\n            PAGES\[selected_slug\]\[1\]\(\)",
        dispatch_fn,
        re.DOTALL,
    )
    return {
        "app_path": str(APP_PATH),
        "same_page_inputs_root_shell_line": _line_number(source, "same_page_inputs_root_shell = selected_slug == \"inputs\" and not page_changed"),
        "stable_shell_marker_line": _line_number(source, "data-testid=\"inputs-root-dispatch-stable-shell\""),
        "dispatch_function_line": _line_number(source, "def _render_selected_page_in_content_slot() -> None:"),
        "clear_path_line": _line_number(source, "app.page_dispatch.page_content_slot.clear.start"),
        "same_page_branch_present": "if same_page_inputs_root_shell:" in dispatch_fn,
        "same_page_branch_uses_container_without_slot_clear": bool(same_page_branch) and "with page_content_slot.container():" in same_page_branch and "page_content_slot.empty()" not in same_page_branch,
        "same_page_branch_emits_stable_shell": "_render_inputs_root_dispatch_stable_shell()" in same_page_branch,
        "other_page_clear_path_present": bool(clear_path_match),
        "other_page_clear_path_uses_slot_empty": "page_content_slot.empty()" in dispatch_fn,
        "stable_shell_declared_zero_height": all(
            token in source
            for token in (
                "height:0",
                "min-height:0",
                "overflow:hidden",
                "opacity:0",
            )
        ),
    }


def _classify(source: dict[str, Any], gap_artifact_path: Path | None, gap_artifact: dict[str, Any]) -> dict[str, Any]:
    gap_cls = dict(gap_artifact.get("classification") or {})
    owner_counts = dict(gap_cls.get("owner_counts_in_largest_gap") or {})
    largest_gap_px = int(gap_cls.get("largest_gap_px") or 0)
    diagnosis = str(gap_cls.get("diagnosis") or "")
    readiness_checks = {
        "same_page_inputs_branch_found": bool(source.get("same_page_branch_present")),
        "same_page_branch_keeps_slot_mounted": bool(source.get("same_page_branch_uses_container_without_slot_clear")),
        "same_page_branch_has_zero_height_marker": bool(source.get("same_page_branch_emits_stable_shell") and source.get("stable_shell_declared_zero_height")),
        "other_page_clear_path_still_exists": bool(source.get("other_page_clear_path_present") and source.get("other_page_clear_path_uses_slot_empty")),
        "latest_gap_artifact_found": gap_artifact_path is not None,
        "large_transient_gap_reproduced": largest_gap_px >= 300,
        "streamlit_running_status_seen_in_gap": bool(owner_counts.get("streamlit_running_status")),
        "batch_or_input_widget_seen_in_gap": bool(owner_counts.get("batch_or_input_widget")),
    }
    ready = all(readiness_checks.values())
    if ready:
        readiness = "READY_FOR_NARROW_SAME_PAGE_INPUTS_LAYOUT_GUARD"
        next_slice = (
            "Implement a narrow guard around the same-page Inputs dispatch/loading region, "
            "then rerun the transient gap owner snapshot and composed Design Guide locks."
        )
    elif gap_artifact_path is None:
        readiness = "BLOCKED_NO_LIVE_GAP_ARTIFACT"
        next_slice = "Run design_guide_rerun_status_widget_gap_owner_audit.py before changing layout."
    elif largest_gap_px < 300:
        readiness = "BLOCKED_GAP_NOT_REPRODUCED"
        next_slice = "Reproduce the user-visible large loading gap before changing layout."
    else:
        readiness = "BLOCKED_UNCLEAR_DISPATCH_OR_GAP_OWNER"
        next_slice = "Add lower-level dispatch trace probes before changing layout."
    return {
        "status": "PASS" if ready or gap_artifact_path is not None else "FAIL",
        "readiness": readiness,
        "latest_gap_diagnosis": diagnosis,
        "largest_gap_px": largest_gap_px,
        "owner_counts_in_largest_gap": owner_counts,
        "readiness_checks": readiness_checks,
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    source = dict(payload.get("source_evidence") or {})
    lines = [
        "# Design Guide Same-Page Inputs Dispatch Gap Readiness Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Readiness: `{cls.get('readiness')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Latest gap artifact: `{payload.get('latest_gap_artifact')}`",
        f"- Latest gap diagnosis: `{cls.get('latest_gap_diagnosis')}`",
        f"- Largest gap px: `{cls.get('largest_gap_px')}`",
        f"- Owner counts: `{cls.get('owner_counts_in_largest_gap')}`",
        "",
        "## Source Evidence",
        "",
        f"- Same-page branch line: `{source.get('same_page_inputs_root_shell_line')}`",
        f"- Dispatch function line: `{source.get('dispatch_function_line')}`",
        f"- Stable shell marker line: `{source.get('stable_shell_marker_line')}`",
        f"- Clear path line: `{source.get('clear_path_line')}`",
        "",
        "```json",
        json.dumps(cls.get("readiness_checks") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
    ]
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_same_page_inputs_dispatch_gap_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_same_page_inputs_dispatch_gap_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    created_at = _stamp()
    gap_path, gap_artifact = _latest("design_guide_rerun_status_widget_gap_owner")
    source = _source_evidence()
    classification = _classify(source, gap_path, gap_artifact)
    payload: dict[str, Any] = {
        "schema": "design_guide_same_page_inputs_dispatch_gap_readiness.v1",
        "created_at": created_at,
        "status": classification["status"],
        "classification": classification,
        "source_evidence": source,
        "latest_gap_artifact": str(gap_path) if gap_path else None,
        "product_behaviour_changed": False,
        "behaviour_scope": {
            "layout_changed": False,
            "rendering_changed": False,
            "publication_changed": False,
            "cta_apply_changed": False,
            "family_runtime_changed": False,
            "visible_wording_changed": False,
            "engineering_behaviour_changed": False,
        },
    }
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload["status"], **classification}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
