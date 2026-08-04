"""Proof that the Inputs same-page stable shell cannot create a top gap.

The historical failure mode was an invisible in-flow shell with min-height 900px
rendering between the app tabs and the Inputs heading while the page loaded.
This snapshot is source-level and behavior-boundary only; it does not change
publication, CTA, Design Brain, engineering logic, or rendering authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APP_PATH = ROOT / "app.py"


def _stable_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _extract_shell_block(source: str) -> str:
    marker = 'data-testid="inputs-root-dispatch-stable-shell"'
    idx = source.find(marker)
    if idx < 0:
        return ""
    start = max(0, source.rfind("<div", 0, idx))
    end = source.find("</div>", idx)
    if end < 0:
        return source[start : idx + 240]
    return source[start : end + len("</div>")]


def _write_report(payload: dict, path: Path) -> None:
    proof = dict(payload.get("proof") or {})
    lines = [
        "# Design Guide Inputs Top Gap Stable Shell Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Proof",
        "",
        f"- Shell marker found: `{proof.get('shell_marker_found')}`",
        f"- No `min-height:900px`: `{proof.get('no_900px_min_height')}`",
        f"- Has zero height: `{proof.get('has_zero_height')}`",
        f"- Has overflow hidden: `{proof.get('has_overflow_hidden')}`",
        f"- CTA/render/apply untouched by this verifier: `{proof.get('shared_authority_untouched')}`",
        "",
        "## Shell Block",
        "",
        "```html",
        str(payload.get("shell_block") or ""),
        "```",
    ]
    if payload.get("failures"):
        lines.extend(["", "## Failures", ""])
        for failure in payload["failures"]:
            lines.append(f"- `{failure}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    source = APP_PATH.read_text(encoding="utf-8")
    shell_block = _extract_shell_block(source)
    proof = {
        "shell_marker_found": bool(shell_block),
        "no_900px_min_height": "min-height:900px" not in shell_block.replace(" ", ""),
        "has_zero_height": "height:0" in shell_block.replace(" ", ""),
        "has_overflow_hidden": "overflow:hidden" in shell_block.replace(" ", ""),
        "shared_authority_untouched": True,
    }
    failures = [key for key, passed in proof.items() if passed is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_inputs_top_gap_stable_shell_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "product_behaviour_changed": False,
        "design_brain_changed": False,
        "publication_cta_apply_changed": False,
        "proof": proof,
        "shell_block": shell_block.strip(),
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"proof": proof, "shell_block": shell_block.strip()})
    artifact_path = ARTIFACT_DIR / f"design_guide_inputs_top_gap_stable_shell_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_inputs_top_gap_stable_shell_{stamp}.md"
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(payload, report_path)
    print(json.dumps({"status": status, "artifact": str(artifact_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
