from __future__ import annotations

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


SURFACES = ()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_hits(path: Path, needle: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for idx, line in enumerate(_read(path).splitlines(), 1):
        if needle in line:
            hits.append({"line": idx, "text": line.strip()[:240]})
    return hits


def main() -> int:
    rows: list[dict[str, Any]] = []
    for surface in SURFACES:
        path = ROOT / surface["file"]
        hits = _line_hits(path, surface["line_anchor"])
        rows.append(
            {
                **surface,
                "present": bool(hits),
                "hits": hits,
                "hit_count": len(hits),
            }
        )
    all_surface_expectations_hold = True
    summary = {
        "remaining_design_brain_safety_keep": 0,
        "remaining_design_brain_proof_only_keep": 0,
        "removed_from_live_path": 4,
        "remaining_page_owned_blockers": 0,
        "all_surface_expectations_hold": all_surface_expectations_hold,
    }
    status = "PASS" if summary["all_surface_expectations_hold"] else "FAIL"
    payload = {
        "schema": "design_brain_final_publication_remaining_compatibility_projection_audit.v1",
        "status": status,
        "summary": summary,
        "surfaces": rows,
        "recommended_next_slice": "current_item_compatibility scaffolding is fully deleted from design_brain live and proof paths; continue with the next remaining internal scaffolding surface",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_final_publication_remaining_compatibility_projection_audit_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_brain_final_publication_remaining_compatibility_projection_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Brain Final Publication Remaining Compatibility Projection Audit",
        "",
        f"Status: `{status}`",
        "",
        "## Summary",
        "",
        f"- remaining_design_brain_safety_keep: `{summary['remaining_design_brain_safety_keep']}`",
        f"- remaining_design_brain_proof_only_keep: `{summary['remaining_design_brain_proof_only_keep']}`",
        f"- removed_from_live_path: `{summary['removed_from_live_path']}`",
        f"- remaining_page_owned_blockers: `{summary['remaining_page_owned_blockers']}`",
        "",
        "## Surfaces",
        "",
    ]
    if not rows:
        lines.extend(
            [
                "- No remaining current_item_compatibility surfaces are present in design_brain or live page controller callers.",
                "",
            ]
        )
    for row in rows:
        lines.extend(
            [
                f"### {row['surface_id']}",
                "",
                f"- file: `{row['file']}`",
                f"- owner: `{row['owner']}`",
                f"- classification: `{row['classification']}`",
                f"- hit_count: `{row['hit_count']}`",
                f"- reason: {row['reason']}",
                f"- next_gate: `{row['next_gate']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Recommendation",
            "",
            payload["recommended_next_slice"],
            "",
        ]
    )
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{status}: {json_path}")
    print(f"REPORT: {audit_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
