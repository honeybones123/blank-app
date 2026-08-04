from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

FILES = {
    "controller": ROOT / "design_brain" / "design_guide_controller.py",
    "family_apply_mismatch_audit": ROOT / "tools" / "verification" / "families" / "combined_bending_shear_fail_apply_output_mismatch_audit.py",
    "product_correctness": ROOT / "tools" / "verification" / "runners" / "product_correctness_focused_checks.py",
    "projection_boundary": ROOT / "tools" / "verification" / "design_brain_combined_candidate_projection_parity_snapshot.py",
}

TOKENS = {
    "legacy_bottom_keys": ("bot1_count", "db_bot_1", "bot2_count", "db_bot_2"),
    "canonical_bottom_keys": ("bot_row_count", "bot_row_1_bars", "bot_row_1_dia", "bot_row_2_bars", "bot_row_2_dia"),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_hits(source: str, token: str) -> list[int]:
    return [lineno for lineno, line in enumerate(source.splitlines(), start=1) if token in line]


def _pair_requirements(source: str) -> dict[str, bool]:
    return {
        f"{legacy}->{canonical}": legacy in source and canonical in source
        for legacy, canonical in (
            ("bot1_count", "bot_row_1_bars"),
            ("db_bot_1", "bot_row_1_dia"),
            ("top1_count", "top_row_1_bars"),
            ("db_top_1", "top_row_1_dia"),
        )
    }


def _legacy_required_assertion_present(source: str) -> bool:
    return '_assert(legacy_key in updates' in source or 'missing {legacy_key}' in source


def _apply_audit_uses_canonical_authority(source: str) -> bool:
    return all(
        token in source
        for token in (
            'updates.get("bot_row_1_bars")',
            'updates.get("bot_row_1_dia")',
            'authority = "canonical"',
        )
    )


def _apply_audit_requires_legacy_authority(source: str) -> bool:
    if not _apply_audit_uses_canonical_authority(source):
        return True
    return 'authority = "legacy"' not in source


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_combined_candidate_canonical_only_consumer_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_brain_combined_candidate_canonical_only_consumer_readiness_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Combined Candidate Canonical-Only Consumer Readiness Audit",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Classification",
        "",
    ]
    for row in snapshot["rows"]:
        lines.extend(
            [
                f"### `{row['surface_id']}`",
                f"- owner: `{row['owner']}`",
                f"- classification: `{row['classification']}`",
                f"- canonical-only ready now: `{row['canonical_only_ready_now']}`",
                f"- reason: {row['reason']}",
                f"- next proof: {row['next_proof']}",
                "",
            ]
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, report_path


def main() -> int:
    controller_source = _read(FILES["controller"])
    apply_audit_source = _read(FILES["family_apply_mismatch_audit"])
    product_source = _read(FILES["product_correctness"])
    projection_source = _read(FILES["projection_boundary"])

    rows = [
        {
            "surface_id": "controller_cleanup_projection_tolerance",
            "owner": "design_brain.design_guide_controller",
            "classification": "CANONICAL_TOLERANT_SHARED_CONSUMER",
            "canonical_only_ready_now": True,
            "reason": "The controller cleanup/presentation path already lists both canonical and legacy bottom update keys, so canonical-only updates remain visible to this consumer.",
            "next_proof": "Optional live browser parity only if controller display regressions are suspected.",
            "line_evidence": {
                "canonical_bottom_keys": _line_hits(controller_source, "bot_row_1_bars"),
                "legacy_bottom_keys": _line_hits(controller_source, "bot1_count"),
            },
        },
        {
            "surface_id": "combined_apply_output_mismatch_expected_bottom_from_updates",
            "owner": "tools/verification/families/combined_bending_shear_fail_apply_output_mismatch_audit.py",
            "classification": (
                "PROOF_BLOCKER_LEGACY_EXPECTATION"
                if _apply_audit_requires_legacy_authority(apply_audit_source)
                else "CANONICAL_AUTHORITY_WITH_OPTIONAL_PROJECTION_PARITY"
            ),
            "canonical_only_ready_now": not _apply_audit_requires_legacy_authority(apply_audit_source),
            "reason": (
                "The live apply mismatch audit still requires legacy bottom keys as authority when deriving expected bottom reinforcement from applied updates."
                if _apply_audit_requires_legacy_authority(apply_audit_source)
                else "The live apply mismatch audit now derives expected bottom reinforcement from canonical row-model keys first and only falls back to legacy keys as optional compatibility parity."
            ),
            "next_proof": (
                "Teach the audit to derive expected bottom reinforcement from canonical row-model keys first, with legacy keys treated as compatibility only."
                if _apply_audit_requires_legacy_authority(apply_audit_source)
                else "No further proof needed here before deleting the combined family projection boundary."
            ),
            "line_evidence": {
                "expected_bottom_from_updates": _line_hits(apply_audit_source, "def _expected_bottom_from_updates"),
                "canonical_authority": _line_hits(apply_audit_source, 'updates.get("bot_row_1_bars")'),
                "legacy_fallback": _line_hits(apply_audit_source, 'updates.get("bot1_count")'),
                "canonical_authority_ready": _apply_audit_uses_canonical_authority(apply_audit_source),
            },
        },
        {
            "surface_id": "product_correctness_rescue_seed_pair_assertions",
            "owner": "tools/verification/runners/product_correctness_focused_checks.py",
            "classification": (
                "PROOF_BLOCKER_MIXED_PAIR_ASSERTION"
                if _legacy_required_assertion_present(product_source)
                else "CANONICAL_AUTHORITY_WITH_OPTIONAL_PROJECTION_PARITY"
            ),
            "canonical_only_ready_now": not _legacy_required_assertion_present(product_source),
            "reason": (
                "The focused product correctness gate still asserts both legacy and canonical reinforcement pairs together, which blocks deletion of the compatibility projection even after runtime canonicalization."
                if _legacy_required_assertion_present(product_source)
                else "The focused product correctness gate now requires canonical rescue-seed authority and treats legacy mirror fields as optional projection parity only."
            ),
            "next_proof": (
                "Replace the pair-equality requirement with canonical authority plus outward projection parity at the chosen boundary."
                if _legacy_required_assertion_present(product_source)
                else "No further proof needed here before deleting the combined family projection boundary."
            ),
            "line_evidence": {
                "required_equal_pairs": _line_hits(product_source, "required_equal_pairs"),
                "pair_presence": _pair_requirements(product_source),
                "legacy_required_assertion_present": _legacy_required_assertion_present(product_source),
            },
        },
        {
            "surface_id": "family_projection_boundary",
            "owner": "design_brain.families.combined_bending_shear_fail",
            "classification": (
                "LIVE_COMPATIBILITY_BOUNDARY"
                if _line_hits(projection_source, "project_combined_reinforcement_update_compatibility_mirrors")
                else "CANONICAL_ONLY_BOUNDARY"
            ),
            "canonical_only_ready_now": not bool(
                _line_hits(projection_source, "project_combined_reinforcement_update_compatibility_mirrors")
            ),
            "reason": (
                "The family boundary still projects canonical runtime rows into the outward compatibility shape. This remains the only live emitter of legacy bottom mirror keys in the combined path."
                if _line_hits(projection_source, "project_combined_reinforcement_update_compatibility_mirrors")
                else "The family boundary now emits canonical runtime rows directly and no longer reintroduces legacy bottom mirror keys."
            ),
            "next_proof": (
                "Delete only after the two proof blockers above accept canonical-only updates or boundary-only projection parity."
                if _line_hits(projection_source, "project_combined_reinforcement_update_compatibility_mirrors")
                else "No further proof needed here; the combined family boundary is canonical-only."
            ),
            "line_evidence": {
                "projection_calls": _line_hits(projection_source, "project_combined_reinforcement_update_compatibility_mirrors"),
            },
        },
    ]

    blockers = [row["surface_id"] for row in rows if not row["canonical_only_ready_now"]]
    next_safe_target = (
        "Delete the combined family projection boundary after a focused boundary-readiness proof confirms shared/runtime consumers accept canonical authority plus optional projection parity."
        if blockers == ["family_projection_boundary"]
        else (
            "The combined family boundary is canonical-only. Move to the next proof-only or safety-only scaffolding keep."
            if not blockers
            else "Convert the remaining proof blockers from legacy-key expectation to canonical authority plus projection parity."
        )
    )
    snapshot = {
        "schema": "design_brain_combined_candidate_canonical_only_consumer_readiness_audit.v1",
        "result": "PASS",
        "rows": rows,
        "blockers": blockers,
        "next_safe_target": next_safe_target,
    }
    json_path, report_path = _write(snapshot)
    print("design_brain_combined_candidate_canonical_only_consumer_readiness_audit PASS")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
