"""Impact snapshot for summary-card layout containment.

Compares the latest source-node/broad smoothness artifacts against the previous
run and records whether the CSS-only summary-card containment experiment is
worth keeping. This verifier does not change product behaviour.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_CSS = ROOT / "ui" / "summary_sections.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "passed": proc.returncode == 0,
    }


def _latest_two(prefix: str) -> list[dict[str, Any]]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    rows: list[dict[str, Any]] = []
    for path in paths[-2:]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"path": str(path), "payload": payload, "status": payload.get("status")})
        except Exception as exc:
            rows.append({"path": str(path), "payload": {}, "status": "UNREADABLE", "error": str(exc)})
    return rows


def _css_contains_containment() -> dict[str, Any]:
    source = SUMMARY_CSS.read_text(encoding="utf-8", errors="replace")
    stack_match = re.search(r"\.summary-card-stack\s*\{([^}]*)\}", source, flags=re.DOTALL)
    card_match = re.search(r"\.summary-check-card\s*\{([^}]*)\}", source, flags=re.DOTALL)
    stack_css = stack_match.group(1) if stack_match else ""
    card_css = card_match.group(1) if card_match else ""
    return {
        "stack_contains_contain_layout_paint": "contain: layout paint" in stack_css,
        "card_contains_contain_layout_paint": "contain: layout paint" in card_css,
    }


def _source_summary(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row.get("payload") or {})
    summary = dict(payload.get("summary") or payload)
    values = dict(summary.get("layout_shift_owner_values") or {})
    return {
        "path": row.get("path"),
        "status": row.get("status"),
        "layout_shift_total": float(summary.get("layout_shift_total") or 0.0),
        "summary_owner_value": float(values.get("summary_first_paint_or_cards") or 0.0),
        "streamlit_owner_value": float(values.get("streamlit_layout_wrapper") or 0.0),
        "top_owner_by_value": summary.get("top_owner_by_value"),
    }


def _layout_hotspot_score(row: dict[str, Any]) -> float:
    payload = dict(row.get("payload") or {})
    for hotspot in list(payload.get("all_hotspot_scores") or []):
        if hotspot.get("name") == "layout placeholder/first-paint gap":
            return float(hotspot.get("score") or 0.0)
    return 0.0


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_run = _run([sys.executable, "-m", "py_compile", "ui\\summary_sections.py"])
    source_rows = _latest_two("design_guide_streamlit_layout_shift_source_node")
    profile_rows = _latest_two("design_guide_browser_live_smoothness_profile")
    before_source = _source_summary(source_rows[0]) if len(source_rows) >= 2 else {}
    after_source = _source_summary(source_rows[1]) if len(source_rows) >= 2 else {}
    before_profile_score = _layout_hotspot_score(profile_rows[0]) if len(profile_rows) >= 2 else 0.0
    after_profile_score = _layout_hotspot_score(profile_rows[1]) if len(profile_rows) >= 2 else 0.0
    source_total_improvement = float(before_source.get("layout_shift_total") or 0.0) - float(after_source.get("layout_shift_total") or 0.0)
    summary_owner_improvement = float(before_source.get("summary_owner_value") or 0.0) - float(after_source.get("summary_owner_value") or 0.0)
    profile_score_improvement = before_profile_score - after_profile_score
    css = _css_contains_containment()
    keep = (
        compile_run["passed"]
        and css["stack_contains_contain_layout_paint"]
        and css["card_contains_contain_layout_paint"]
        and source_total_improvement >= 0.004
        and profile_score_improvement >= 40.0
    )
    decision = "KEEP_SUMMARY_CARD_CONTAINMENT" if keep else "REVERT_SUMMARY_CARD_CONTAINMENT_NOT_MATERIAL"
    return {
        "schema": "design_guide_summary_card_layout_containment_impact.v1",
        "created_at": _stamp(),
        "status": "PASS" if compile_run["passed"] else "FAIL",
        "decision": decision,
        "keep_containment": keep,
        "product_behaviour_changed": False,
        "css_surface": css,
        "source_node_comparison": {
            "before": before_source,
            "after": after_source,
            "layout_shift_total_improvement": round(source_total_improvement, 6),
            "summary_owner_value_improvement": round(summary_owner_improvement, 6),
        },
        "broad_profile_comparison": {
            "before_path": profile_rows[0].get("path") if len(profile_rows) >= 2 else None,
            "after_path": profile_rows[1].get("path") if len(profile_rows) >= 2 else None,
            "before_layout_hotspot_score": before_profile_score,
            "after_layout_hotspot_score": after_profile_score,
            "layout_hotspot_score_improvement": round(profile_score_improvement, 3),
        },
        "compile_run": compile_run,
        "recommended_next_slice": (
            "Keep containment and run composed locks."
            if keep
            else "Revert containment and return to user-specific huge-gap reproduction."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_summary_card_layout_containment_impact_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_card_layout_containment_impact_{stamp}.md"
    source = dict(payload.get("source_node_comparison") or {})
    profile = dict(payload.get("broad_profile_comparison") or {})
    lines = [
        "# Design Guide Summary Card Layout Containment Impact",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Keep containment: `{payload.get('keep_containment')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Impact",
        "",
        f"- Source-node CLS improvement: `{source.get('layout_shift_total_improvement')}`",
        f"- Summary-owner CLS improvement: `{source.get('summary_owner_value_improvement')}`",
        f"- Layout hotspot score improvement: `{profile.get('layout_hotspot_score_improvement')}`",
        "",
        "## Recommendation",
        "",
        str(payload.get("recommended_next_slice") or ""),
        "",
    ]
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = _build()
    json_path, md_path = _write(payload)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
