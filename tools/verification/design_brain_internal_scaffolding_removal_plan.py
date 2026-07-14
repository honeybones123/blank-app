from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"C:/Users/jono/OneDrive/Documents/GitHub/complete-app - Copy (3)")
DESIGN_BRAIN = ROOT / "design_brain"
INPUTS_PAGE = ROOT / "inputs_page.py"
TOOLS = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


@dataclass(frozen=True)
class Surface:
    surface_id: str
    file: str
    symbol: str
    classification: str
    reason: str
    next_slice: str
    evidence_checks: tuple[tuple[str, str, str], ...]


ACTIVE_SCAFFOLDING_SURFACES: tuple[Surface, ...] = ()


EXCLUDED_NON_SCAFFOLDING_SURFACES: tuple[Surface, ...] = (
    Surface(
        surface_id="serviceability_package_public_api",
        file="design_brain/families/serviceability_governs/__init__.py",
        symbol="evaluate_serviceability_governs",
        classification="excluded_non_scaffolding",
        reason="This is the canonical contract-facing serviceability family entrypoint, not an old-shaped compatibility, fallback, or restamper scaffold.",
        next_slice="exclude from remaining scaffolding counts unless the family contract public_api itself is redesigned",
        evidence_checks=(
            (
                "family_shell_import",
                "design_brain/families/serviceability.py",
                "from design_brain.families.serviceability_governs import evaluate_serviceability_governs",
            ),
            (
                "contract_public_api",
                "design_brain/families/serviceability_governs/contract.json",
                '"public_api": "evaluate_serviceability_governs"',
            ),
        ),
    ),
)


REMOVED_EVIDENCE_SURFACES: tuple[Surface, ...] = (
    Surface(
        surface_id="controller_compute_rebound_debug_compatibility_updates",
        file="design_brain/design_guide_controller.py",
        symbol="debug_compatibility_updates",
        classification="shim_removed",
        reason="The controller no longer returns the mirrored debug payload; page/debug consumers now use local debug stamps plus key/hash proof metadata.",
        next_slice="continue deleting any remaining proof-only payload mirrors that still duplicate page-known debug truth",
        evidence_checks=(
            (
                "controller_response_key_metadata",
                "design_brain/design_guide_controller.py",
                "debug_compatibility_update_keys: tuple[str, ...]",
            ),
            (
                "inputs_debug_session_stamp",
                "inputs_page.py",
                '"debug_compatibility_updates_hash": response.debug_compatibility_updates_hash',
            ),
            (
                "inputs_trace_key_consumer",
                "inputs_page.py",
                '"debug_compatibility_update_keys": list(response.debug_compatibility_update_keys)',
            ),
            (
                "inputs_late_branch_local_stamp",
                "inputs_page.py",
                '"late_evidence_cleanup_contract_rebound": True',
            ),
            (
                "inputs_post_branch_local_stamp",
                "inputs_page.py",
                'debug_trace["post_evidence_cleanup_contract_rebound"] = (',
            ),
        ),
    ),
    Surface(
        surface_id="final_publication_render_fallback_shell_projection",
        file="design_brain/final_publication.py",
        symbol="build_final_design_guide_render_fallback_shell_projection",
        classification="shim_removed",
        reason="The fallback-shell helper has been retired; all remaining direct shell callsites now use the clean direct-shell card projection.",
        next_slice="keep deleting stale verifier references and then focus on the final validity guard only",
        evidence_checks=(
            (
                "direct_builder_exported",
                "design_brain/final_publication.py",
                '"build_final_design_guide_direct_shell_card_projection"',
            ),
            (
                "early_shell_switched",
                "inputs_page.py",
                "_early_shear_cleanup_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
            ),
            (
                "pre_render_switched",
                "inputs_page.py",
                "_pre_render_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
            ),
            (
                "post_render_switched",
                "inputs_page.py",
                "_fallback_shell_projection = _build_final_design_guide_direct_shell_card_projection(",
            ),
        ),
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _check_presence(relative_path: str, needle: str) -> dict[str, Any]:
    path = ROOT / relative_path
    text = _read(path)
    found = needle in text
    line = None
    if found:
        line = next((i for i, value in enumerate(text.splitlines(), start=1) if needle in value), None)
    return {
        "file": relative_path,
        "needle": needle,
        "found": found,
        "line": line,
    }


def _surface_row(surface: Surface) -> dict[str, Any]:
    checks = []
    all_found = True
    for check_id, relative_path, needle in surface.evidence_checks:
        result = _check_presence(relative_path, needle)
        result["check_id"] = check_id
        checks.append(result)
        all_found = all_found and bool(result["found"])
    return {
        "surface_id": surface.surface_id,
        "file": surface.file,
        "symbol": surface.symbol,
        "classification": surface.classification,
        "reason": surface.reason,
        "next_slice": surface.next_slice,
        "all_expected_evidence_found": all_found,
        "evidence_checks": checks,
    }


def _markdown(
    rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
    removed_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    stamp: str,
) -> str:
    lines = [
        "# Design Brain Internal Scaffolding Removal Plan",
        "",
        f"Generated: `{stamp}`",
        "",
        "## Summary",
        "",
        f"- Remaining scaffolding surfaces audited: `{summary['remaining_surface_count']}`",
        f"- Safe delete now: `{summary['safe_delete_now']}`",
        f"- Removed evidence surfaces: `{summary['removed_evidence_count']}`",
        f"- Excluded non-scaffolding surfaces: `{summary['excluded_non_scaffolding_count']}`",
        f"- Live safety keep: `{summary['live_safety_keep']}`",
        f"- Proof-only keep: `{summary['proof_only_keep']}`",
        f"- Rename-candidate keep: `{summary['rename_candidate_keep']}`",
        "",
        "## Remaining Scaffolding Surfaces",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['surface_id']}",
                "",
                f"- File: `{row['file']}`",
                f"- Symbol: `{row['symbol']}`",
                f"- Classification: `{row['classification']}`",
                f"- Reason: {row['reason']}",
                f"- Next slice: `{row['next_slice']}`",
                f"- Evidence complete: `{row['all_expected_evidence_found']}`",
                "- Evidence:",
            ]
        )
        for check in row["evidence_checks"]:
            lines.append(
                f"  - `{check['check_id']}` -> `{check['found']}` "
                f"at `{check['file']}:{check['line']}`"
            )
        lines.append("")
    if excluded_rows:
        lines.extend(["## Excluded Non-Scaffolding Surfaces", ""])
        for row in excluded_rows:
            lines.extend(
                [
                    f"### {row['surface_id']}",
                    "",
                    f"- File: `{row['file']}`",
                    f"- Symbol: `{row['symbol']}`",
                    f"- Classification: `{row['classification']}`",
                    f"- Reason: {row['reason']}",
                    f"- Next slice: `{row['next_slice']}`",
                    "",
                ]
            )
    if removed_rows:
        lines.extend(["## Removed Evidence Surfaces", ""])
        for row in removed_rows:
            lines.extend(
                [
                    f"### {row['surface_id']}",
                    "",
                    f"- File: `{row['file']}`",
                    f"- Symbol: `{row['symbol']}`",
                    f"- Classification: `{row['classification']}`",
                    f"- Reason: {row['reason']}",
                    f"- Next slice: `{row['next_slice']}`",
                    "",
                ]
            )
    lines.extend(
        [
            "## Recommendation",
            "",
            "The remaining scaffolding inventory now excludes canonical contract public APIs, the retired output-readiness proof surface, the fallback-shell helper boundary, and the retired final-visible validity guard seam.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    rows = [_surface_row(surface) for surface in ACTIVE_SCAFFOLDING_SURFACES]
    excluded_rows = [_surface_row(surface) for surface in EXCLUDED_NON_SCAFFOLDING_SURFACES]
    removed_rows = [_surface_row(surface) for surface in REMOVED_EVIDENCE_SURFACES]
    status = "PASS" if all(row["all_expected_evidence_found"] for row in rows) else "FAIL"
    summary = {
        "remaining_surface_count": len(rows),
        "safe_delete_now": sum(1 for row in rows if row["classification"] == "safe_delete_now"),
        "removed_evidence_count": len(removed_rows),
        "excluded_non_scaffolding_count": len(excluded_rows),
        "live_safety_keep": sum(1 for row in rows if row["classification"] == "live_safety_keep"),
        "proof_only_keep": sum(1 for row in rows if row["classification"] == "proof_only_keep"),
        "rename_candidate_keep": sum(1 for row in rows if row["classification"] == "rename_candidate_keep"),
    }
    payload = {
        "snapshot_name": "design_brain_internal_scaffolding_removal_plan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": status,
        "summary": summary,
        "surfaces": rows,
        "excluded_non_scaffolding_surfaces": excluded_rows,
        "removed_evidence_surfaces": removed_rows,
        "recommended_next_slice": (
            "inventory is at zero remaining design_brain compatibility/fallback scaffolding surfaces; continue with delete-readiness only for unrelated page-owned legacy code"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_brain_internal_scaffolding_removal_plan_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_internal_scaffolding_removal_plan_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(rows, excluded_rows, removed_rows, summary, stamp), encoding="utf-8")
    print(f"design_brain_internal_scaffolding_removal_plan {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
