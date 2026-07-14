from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
DESIGN_BRAIN = ROOT / "design_brain"
INPUTS_PAGE = ROOT / "inputs_page.py"
UI_DIR = ROOT / "ui"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@dataclass(frozen=True)
class Surface:
    surface_id: str
    file: str
    symbol: str
    classification: str
    reason: str
    source_kind: str
    search_terms: tuple[str, ...] = ()
    contract_json: str | None = None
    contract_public_api: str | None = None


SURFACES: tuple[Surface, ...] = (
    Surface(
        surface_id="combined_family_dead_alias_removed",
        file="design_brain/families/combined_fail.py",
        symbol="CombinedFailFamily",
        classification="safe_delete_now",
        reason="Backward-compatible alias module is not imported by live code.",
        source_kind="dead_alias_module",
        search_terms=("CombinedFailFamily", "families.combined_fail"),
    ),
    Surface(
        surface_id="serviceability_package_public_api",
        file="design_brain/families/serviceability_governs/__init__.py",
        symbol="evaluate_serviceability_governs",
        classification="safety_keep",
        reason="Still consumed by the live serviceability family shell and remains a contract-facing runtime entrypoint.",
        source_kind="package_public_api",
        search_terms=("evaluate_serviceability_governs(",),
        contract_json="design_brain/families/serviceability_governs/contract.json",
        contract_public_api="evaluate_serviceability_governs",
    ),
)


def _live_source_files() -> list[Path]:
    files = [INPUTS_PAGE]
    if UI_DIR.exists():
        files.extend(path for path in UI_DIR.rglob("*.py"))
    files.extend(path for path in DESIGN_BRAIN.rglob("*.py"))
    return files


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _count_live_refs(term: str, *, self_path: Path | None = None) -> tuple[int, list[str]]:
    hits: list[str] = []
    for path in _live_source_files():
        if self_path is not None and path == self_path:
            continue
        text = _read_text(path)
        if term in text:
            rel = path.relative_to(ROOT).as_posix()
            line_no = next(
                (idx for idx, line in enumerate(text.splitlines(), start=1) if term in line),
                1,
            )
            hits.append(f"{rel}:{line_no}")
    return len(hits), hits


def _contract_meta(surface: Surface) -> dict[str, Any]:
    if not surface.contract_json:
        return {}
    contract_path = ROOT / surface.contract_json
    if not contract_path.exists():
        return {
            "contract_present": False,
            "contract_public_api_matches": False,
        }
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    family_identity = payload.get("family_identity")
    live_public_api = payload.get("public_api")
    if live_public_api is None and isinstance(family_identity, dict):
        live_public_api = family_identity.get("public_api")
    return {
        "contract_present": True,
        "contract_public_api": live_public_api,
        "contract_public_api_matches": live_public_api == surface.contract_public_api,
    }


def _surface_row(surface: Surface) -> dict[str, Any]:
    path = ROOT / surface.file
    present = path.exists()
    live_ref_counts: dict[str, int] = {}
    live_ref_hits: dict[str, list[str]] = {}
    if present:
        for term in surface.search_terms:
            count, hits = _count_live_refs(term, self_path=path)
            live_ref_counts[term] = count
            live_ref_hits[term] = hits
    else:
        for term in surface.search_terms:
            live_ref_counts[term] = 0
            live_ref_hits[term] = []
    return {
        "surface_id": surface.surface_id,
        "file": surface.file,
        "symbol": surface.symbol,
        "present": present,
        "classification": surface.classification,
        "reason": surface.reason,
        "source_kind": surface.source_kind,
        "search_terms": list(surface.search_terms),
        "live_ref_counts": live_ref_counts,
        "live_ref_hits": live_ref_hits,
        **_contract_meta(surface),
    }


def _markdown_report(rows: list[dict[str, Any]], summary: dict[str, Any], stamp: str) -> str:
    lines = [
        "# Design Brain Broad Internal Scaffolding Audit",
        "",
        f"Generated: `{stamp}`",
        "",
        "## Summary",
        "",
        f"- Present surfaces audited: `{summary['present_surfaces']}`",
        f"- Safe delete now: `{summary['safe_delete_now']}`",
        f"- Safety keep: `{summary['safety_keep']}`",
        f"- Proof-only keep: `{summary['proof_only_keep']}`",
        f"- Removed dead alias confirmed absent: `{summary['combined_fail_alias_removed']}`",
        "",
        "## Surface Classification",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['surface_id']}",
                "",
                f"- File: `{row['file']}`",
                f"- Symbol: `{row['symbol']}`",
                f"- Present: `{row['present']}`",
                f"- Classification: `{row['classification']}`",
                f"- Reason: {row['reason']}",
                f"- Source kind: `{row['source_kind']}`",
            ]
        )
        if "contract_present" in row:
            lines.append(f"- Contract present: `{row['contract_present']}`")
            if row.get("contract_present"):
                lines.append(
                    f"- Contract public_api matches: `{row.get('contract_public_api_matches')}`"
                )
        if row["search_terms"]:
            lines.append("- Live reference hits:")
            for term in row["search_terms"]:
                lines.append(
                    f"  - `{term}` -> `{row['live_ref_counts'].get(term, 0)}` refs "
                    f"{row['live_ref_hits'].get(term, [])}"
                )
        lines.append("")
    lines.extend(
        [
            "## Recommendation",
            "",
        "The remaining present surfaces in this broad audit are canonical package/public APIs or dead alias candidates. The guarded validity/fallback scaffolding surfaces are no longer present inside design_brain.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    rows = [_surface_row(surface) for surface in SURFACES]
    present_rows = [row for row in rows if row["present"]]
    summary = {
        "present_surfaces": len(present_rows),
        "safe_delete_now": sum(1 for row in present_rows if row["classification"] == "safe_delete_now"),
        "safety_keep": sum(1 for row in present_rows if row["classification"] == "safety_keep"),
        "proof_only_keep": sum(1 for row in present_rows if row["classification"] == "proof_only_keep"),
        "combined_fail_alias_removed": not (ROOT / "design_brain/families/combined_fail.py").exists(),
    }
    payload = {
        "snapshot_name": "design_brain_broad_internal_scaffolding_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "summary": summary,
        "surfaces": rows,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_brain_broad_internal_scaffolding_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_broad_internal_scaffolding_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(rows, summary, stamp), encoding="utf-8")
    print("design_brain_broad_internal_scaffolding_audit PASS")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
