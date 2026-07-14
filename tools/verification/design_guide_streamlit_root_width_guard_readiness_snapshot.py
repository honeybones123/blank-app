"""Readiness audit for a root/main Streamlit width guard.

Proof-only. This verifier decides whether the residual early layout shift can
be safely targeted by app-owned CSS, or whether it happens before our app CSS can
affect the Streamlit main block. It does not change product behaviour.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "app.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": None, "path": None, "payload": {}}
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
    return {"found": True, "status": payload.get("status"), "path": str(path), "payload": payload}


def _function_block(source: str, name: str) -> str:
    match = re.search(rf"^def {re.escape(name)}\(", source, flags=re.MULTILINE)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", source[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


def _capture() -> dict[str, Any]:
    source = APP_PY.read_text(encoding="utf-8", errors="replace")
    css_block = _function_block(source, "_apply_sharp_embed_css")
    latest_width = _latest("design_guide_streamlit_main_width_settle")
    latest_summary = dict((latest_width.get("payload") or {}).get("summary") or {})
    first_style = latest_summary.get("first_app_style_at_ms")
    first_inputs = latest_summary.get("first_inputs_visible_at_ms")
    largest_shift = latest_summary.get("early_pre_summary_layout_shift_total")
    width_delta = latest_summary.get("main_width_delta_px")
    source_markers = {
        "page_config_wide": 'layout="wide"' in source,
        "sharp_css_called_before_inputs_import": source.find("_apply_sharp_embed_css()") < source.find("import inputs_page"),
        "main_width_css_scoped_to_stapp": ".stApp [data-testid=\"stMainBlockContainer\"]" in css_block,
        "main_width_css_unscoped": bool(
            re.search(r"(^|\n)\s*\[data-testid=\"stMainBlockContainer\"\]\s*,", css_block)
        ),
        "block_container_max_width_1180": "max-width: 1180px" in css_block,
        "app_css_uses_markdown_in_body": "st.markdown(" in css_block,
    }
    return {
        "source_markers": source_markers,
        "latest_width_settle": {
            "path": latest_width.get("path"),
            "status": latest_width.get("status"),
            "summary": latest_summary,
        },
        "measured": {
            "first_app_style_at_ms": first_style,
            "first_inputs_visible_at_ms": first_inputs,
            "early_pre_summary_layout_shift_total": largest_shift,
            "main_width_delta_px": width_delta,
        },
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    markers = dict(capture.get("source_markers") or {})
    measured = dict(capture.get("measured") or {})
    first_style = measured.get("first_app_style_at_ms")
    width_delta = float(measured.get("main_width_delta_px") or 0)
    early_shift = float(measured.get("early_pre_summary_layout_shift_total") or 0)
    latest = dict(capture.get("latest_width_settle") or {})

    implementation_present = bool(markers.get("main_width_css_unscoped"))
    ready_for_unscoped_guard = bool(
        latest.get("status") == "PASS"
        and markers.get("page_config_wide")
        and markers.get("sharp_css_called_before_inputs_import")
        and markers.get("main_width_css_scoped_to_stapp")
        and markers.get("block_container_max_width_1180")
        and width_delta >= 200
        and early_shift >= 0.05
        and first_style is not None
        and int(first_style or 0) <= 700
    )

    if implementation_present and ready_for_unscoped_guard:
        decision = "UNSCOPED_MAIN_WIDTH_GUARD_IMPLEMENTED"
        next_slice = "Run width-settle/source-node/broad smoothness impact checks and composed locks."
    elif ready_for_unscoped_guard:
        decision = "READY_FOR_UNSCOPED_MAIN_WIDTH_GUARD"
        next_slice = "Add the same max-width/padding rule to unscoped main block selectors in _apply_sharp_embed_css."
    elif latest.get("status") != "PASS":
        decision = "MISSING_WIDTH_SETTLE_PROOF"
        next_slice = "Run design_guide_streamlit_main_width_settle_snapshot before product changes."
    else:
        decision = "NOT_READY_FOR_ROOT_WIDTH_PATCH"
        next_slice = "Do not patch global width; focus on user-specific jump reproduction or non-layout stable rerun hotspots."

    return {
        "status": "PASS",
        "decision": decision,
        "ready_for_unscoped_main_width_guard": ready_for_unscoped_guard,
        "unscoped_main_width_guard_present": implementation_present,
        "product_behaviour_changed": False,
        "recommended_next_slice": next_slice,
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_streamlit_root_width_guard_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_streamlit_root_width_guard_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Streamlit Root Width Guard Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{cls.get('decision')}`",
        f"- Ready for unscoped main width guard: `{cls.get('ready_for_unscoped_main_width_guard')}`",
        f"- Unscoped main width guard present: `{cls.get('unscoped_main_width_guard_present')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Recommended next slice: `{cls.get('recommended_next_slice')}`",
        "",
        "## Evidence",
        "",
        "```json",
        json.dumps(
            {
                "source_markers": payload.get("source_markers"),
                "measured": payload.get("measured"),
                "latest_width_settle_path": (payload.get("latest_width_settle") or {}).get("path"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        ),
        "```",
        "",
        "## Rules",
        "- Readiness-only.",
        "- No engineering behaviour, visible wording, CTA/apply, publication, render ownership, or family runtime changed.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    capture = _capture()
    classification = _classify(capture)
    payload = {
        "schema": "design_guide_streamlit_root_width_guard_readiness.v1",
        "created_at": _stamp(),
        "status": classification["status"],
        "product_behaviour_changed": False,
        **capture,
        "classification": classification,
    }
    json_path, md_path = _write(payload)
    print(f"design_guide_streamlit_root_width_guard_readiness {payload['status']}")
    print(f"decision={classification['decision']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
