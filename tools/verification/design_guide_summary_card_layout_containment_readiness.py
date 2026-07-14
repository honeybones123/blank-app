"""Proof-only readiness for summary-card layout containment.

The source-node layout shift snapshot currently attributes residual first-load
CLS to the summary first-paint/cards and Streamlit wrappers. This verifier
checks whether a narrow CSS-only containment experiment is justified for the
summary card surface before any product CSS change is made.

It does not change product behaviour, engineering logic, publication,
CTA/apply semantics, visible wording, or family runtimes.
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


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "payload": {}, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "path": str(path), "payload": {}, "status": "UNREADABLE", "error": str(exc)}
    return {"found": True, "path": str(path), "payload": payload, "status": payload.get("status")}


def _css_surface(source: str) -> dict[str, Any]:
    stack_match = re.search(r"\.summary-card-stack\s*\{([^}]*)\}", source, flags=re.DOTALL)
    card_match = re.search(r"\.summary-check-card\s*\{([^}]*)\}", source, flags=re.DOTALL)
    stack_css = stack_match.group(1) if stack_match else ""
    card_css = card_match.group(1) if card_match else ""
    return {
        "stack_rule_found": bool(stack_match),
        "card_rule_found": bool(card_match),
        "stack_contains_contain": "contain:" in stack_css,
        "card_contains_contain": "contain:" in card_css,
        "stack_rule": stack_css.strip(),
        "card_rule_excerpt": card_css.strip()[:800],
    }


def _build() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = SUMMARY_CSS.read_text(encoding="utf-8", errors="replace")
    css = _css_surface(source)
    source_node = _latest("design_guide_streamlit_layout_shift_source_node")
    loading_gap = _latest("design_guide_loading_gap_scroll_interaction")
    source_payload = dict(source_node.get("payload") or {})
    source_summary = dict(source_payload.get("summary") or source_payload)
    loading_payload = dict(loading_gap.get("payload") or {})
    source_values = dict(source_summary.get("layout_shift_owner_values") or {})
    source_top = source_summary.get("top_owner_by_value")
    loading_classification = dict(loading_payload.get("classification") or {})
    loading_risks = list(loading_classification.get("risks") or [])
    compile_run = _run([sys.executable, "-m", "py_compile", "ui\\summary_sections.py"])

    ready = (
        compile_run["passed"]
        and source_node.get("status") == "PASS"
        and css["stack_rule_found"]
        and css["card_rule_found"]
        and source_top == "summary_first_paint_or_cards"
        and float(source_values.get("summary_first_paint_or_cards") or 0.0) >= 0.15
        and not css["stack_contains_contain"]
        and not css["card_contains_contain"]
        and "huge_top_inputs_gap_reproduced" not in loading_risks
        and "scroll_locked_during_loading" not in loading_risks
    )
    decision = (
        "READY_FOR_NARROW_SUMMARY_CARD_LAYOUT_CONTAINMENT_EXPERIMENT"
        if ready
        else "NOT_READY_FOR_SUMMARY_CARD_CONTAINMENT"
    )
    return {
        "schema": "design_guide_summary_card_layout_containment_readiness.v1",
        "created_at": _stamp(),
        "status": "PASS" if compile_run["passed"] else "FAIL",
        "decision": decision,
        "ready_for_containment_experiment": ready,
        "product_behaviour_changed": False,
        "css_surface": css,
        "latest_source_node": {
            "path": source_node.get("path"),
            "status": source_node.get("status"),
            "top_owner_by_value": source_top,
            "layout_shift_owner_values": source_values,
            "layout_shift_total": source_summary.get("layout_shift_total"),
        },
        "latest_loading_gap": {
            "path": loading_gap.get("path"),
            "status": loading_gap.get("status"),
            "decision": loading_classification.get("decision"),
            "risks": loading_risks,
            "max_gaps": loading_classification.get("max_gaps"),
        },
        "compile_run": compile_run,
        "recommended_next_slice": (
            "Add CSS layout containment only to summary-card-stack/summary-check-card, then run source-node and broad smoothness impact. Revert if not material."
            if ready
            else "Do not patch summary containment; refresh source-node proof or reproduce the user-specific gap first."
        ),
    }


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_summary_card_layout_containment_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_summary_card_layout_containment_readiness_{stamp}.md"
    lines = [
        "# Design Guide Summary Card Layout Containment Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{payload.get('decision')}`",
        f"- Ready: `{payload.get('ready_for_containment_experiment')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Latest source-node top owner: `{(payload.get('latest_source_node') or {}).get('top_owner_by_value')}`",
        f"- Latest source-node total CLS: `{(payload.get('latest_source_node') or {}).get('layout_shift_total')}`",
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
