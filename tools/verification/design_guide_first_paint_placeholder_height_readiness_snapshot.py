"""First-paint placeholder height readiness snapshot.

Proof-only. Classifies layout placeholders after browser/live layout stability
reported large summary-to-batch and batch-to-Design-Guide gaps. No CSS, render,
publication, CTA/apply, family runtime, wording, or engineering behaviour is
changed by this verifier.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
DESIGN_GUIDE_PAGE = ROOT / "design_guide_page.py"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path), "payload": payload}


def _line_hits(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _min_height_hits(source: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for index, line in enumerate(source.splitlines(), start=1):
        if "min-height" not in line:
            continue
        match = re.search(r"min-height\s*:\s*([^;\"']+)", line)
        hits.append(
            {
                "line": index,
                "value": (match.group(1).strip() if match else ""),
                "line_text": line.strip()[:220],
            }
        )
    return hits


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    dg_source = DESIGN_GUIDE_PAGE.read_text(encoding="utf-8", errors="replace")
    latest_layout = _latest("design_guide_browser_live_layout_stability")
    latest_reuse = _latest("design_guide_stable_publication_summary_render_reuse_live_impact")
    latest_independence = _latest("design_guide_independence_lock")
    latest_render = _latest("design_guide_render_bridge_lock")
    latest_compute = _latest("design_guide_compute_resolver_publication_bridge_lock")
    classifications = [
        {
            "surface": "inputs first-paint summary shell",
            "source": "inputs_page.py",
            "evidence_lines": _line_hits(inputs_source, "inputs-first-paint-shell")[:8],
            "classification": "A. first-paint height candidate",
            "current_role": "temporary loading shell before current summary cards are rendered",
            "safe_next_step": "prove reduced min-height or zero-reserved replacement in browser layout snapshot",
            "do_not_do": "do not remove the shell without a first-paint visual/card readiness proof",
        },
        {
            "surface": "Design Guide proof-pending placeholder",
            "source": "design_guide_page.py",
            "evidence_lines": _line_hits(dg_source, "dg-proof-pending-card")[:8]
            + _line_hits(dg_source, "min-height: 10.5rem")[:8],
            "classification": "B. proof/loading safety keep",
            "current_role": "safe visible placeholder while proof/search is running",
            "safe_next_step": "keep unless a proof-pending shell replacement verifier says otherwise",
            "do_not_do": "do not collapse this if proof/card publication can still be pending",
        },
        {
            "surface": "Batch-to-Design-Guide slot placeholder",
            "source": "inputs_page.py",
            "evidence_lines": _line_hits(inputs_source, "design_guide_page.render_pre_widget_placeholder")[:8]
            + _line_hits(inputs_source, "design_guide_slot = st.empty()")[:8],
            "classification": "C. slot readiness bridge",
            "current_role": "mounts Design Guide slot before widgets so final panel can replace it later",
            "safe_next_step": "measure whether slot placeholder height persists after final card publication",
            "do_not_do": "do not remove slot creation; render eligibility depends on it",
        },
        {
            "surface": "static layout spacing around Batch design",
            "source": "inputs_page.py",
            "evidence_lines": _line_hits(inputs_source, "### Batch design")[:8]
            + _line_hits(inputs_source, "height: 1.55rem")[:8],
            "classification": "D. static spacing audit target",
            "current_role": "visible batch manager layout and manager-only alignment spacers",
            "safe_next_step": "browser DOM path audit to distinguish real gap from selector measuring inner rows",
            "do_not_do": "do not broadly remove Streamlit spacing or manager spacers without DOM proof",
        },
    ]
    return {
        "latest": {
            "layout_stability": latest_layout,
            "summary_reuse_live_impact": latest_reuse,
            "independence_lock": latest_independence,
            "render_bridge_lock": latest_render,
            "compute_bridge_lock": latest_compute,
        },
        "inputs_min_height_hits": _min_height_hits(inputs_source),
        "design_guide_min_height_hits": _min_height_hits(dg_source),
        "classifications": classifications,
        "recommended_next_slice": (
            "Create a browser DOM gap source snapshot that records exact element paths/heights "
            "for summary_band, Batch design, Design Guide heading/card, first-paint shell, and "
            "proof-pending placeholder before changing CSS."
        ),
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    classifications = list(capture.get("classifications") or [])
    labels = {row.get("classification") for row in classifications}
    return {
        "layout_stability_pass": (latest.get("layout_stability") or {}).get("status") == "PASS",
        "summary_reuse_live_impact_pass": (latest.get("summary_reuse_live_impact") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "first_paint_shell_found": any(
            row.get("surface") == "inputs first-paint summary shell" and row.get("evidence_lines")
            for row in classifications
        ),
        "proof_pending_placeholder_found": any(
            row.get("surface") == "Design Guide proof-pending placeholder" and row.get("evidence_lines")
            for row in classifications
        ),
        "surfaces_classified": {"A. first-paint height candidate", "B. proof/loading safety keep", "C. slot readiness bridge", "D. static spacing audit target"} <= labels,
    }


def _report(payload: dict[str, Any]) -> str:
    lines = [
        "# Design Guide First-Paint Placeholder Height Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Readiness: `{payload.get('readiness')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Classified Surfaces", "", "| Surface | Classification | Safe next step |", "|---|---|---|"])
    for row in payload.get("classifications") or []:
        lines.append(
            f"| {row.get('surface')} | {row.get('classification')} | {row.get('safe_next_step')} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            str(payload.get("recommended_next_slice") or ""),
            "",
            "No layout/CSS change is made in this pass.",
            "",
        ]
    )
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_first_paint_placeholder_height_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_first_paint_placeholder_height_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(_report(payload), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "created_at": _stamp(),
        "status": status,
        "readiness": "READY_FOR_BROWSER_DOM_GAP_SOURCE_SNAPSHOT" if status == "PASS" else "NOT_READY",
        "checks": checks,
        "product_behavior_changed": False,
        **capture,
    }
    payload["snapshot_hash"] = _stable_hash(
        {
            "status": status,
            "checks": checks,
            "classifications": payload.get("classifications"),
            "recommended_next_slice": payload.get("recommended_next_slice"),
        }
    )
    json_path, report_path = _write(payload)
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
