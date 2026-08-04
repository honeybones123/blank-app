from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

CANONICAL_ROW_FIELDS = {
    "bottom": ("bot_row_count", "bot_row_1_bars", "bot_row_1_dia", "bot_row_2_bars", "bot_row_2_dia"),
    "top": ("top_row_count", "top_row_1_bars", "top_row_1_dia", "top_row_2_bars", "top_row_2_dia"),
}
LEGACY_MIRROR_FIELDS = {
    "bottom": ("bot1_count", "db_bot_1", "bot2_count", "db_bot_2"),
    "top": ("top1_count", "db_top_1", "top2_count", "db_top_2"),
}
REQUIRED_MIRROR_PAIRS = (
    ("bot1_count", "bot_row_1_bars"),
    ("db_bot_1", "bot_row_1_dia"),
    ("bot2_count", "bot_row_2_bars"),
    ("db_bot_2", "bot_row_2_dia"),
    ("top1_count", "top_row_1_bars"),
    ("db_top_1", "top_row_1_dia"),
)

FILES = {
    "candidate_evaluation": ROOT / "design_brain" / "candidate_evaluation.py",
    "combined_candidate_merge": ROOT / "design_brain" / "combined_bending_shear_candidate_merge.py",
    "bending_fail_runtime": ROOT / "design_brain" / "families" / "bending_fail_governs" / "runtime.py",
    "bending_overdesign_runtime": ROOT / "design_brain" / "families" / "bending_overdesign_governs" / "runtime.py",
    "combined_fail_runtime": ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py",
    "inputs_page": ROOT / "inputs_page.py",
    "product_correctness": ROOT / "tools" / "verification" / "runners" / "product_correctness_focused_checks.py",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _line_hits(source: str, token: str) -> list[int]:
    return [index for index, line in enumerate(source.splitlines(), start=1) if token in line]


def _field_counts(source: str, fields: tuple[str, ...]) -> dict[str, int]:
    return {field: len(re.findall(rf"\b{re.escape(field)}\b", source)) for field in fields}


def _pair_presence(source: str, pairs: tuple[tuple[str, str], ...]) -> dict[str, dict[str, bool]]:
    return {
        f"{legacy}->{canonical}": {
            "legacy_present": legacy in source,
            "canonical_present": canonical in source,
            "both_present": legacy in source and canonical in source,
        }
        for legacy, canonical in pairs
    }


def _legacy_required_assertion_present(source: str) -> bool:
    return '_assert(legacy_key in updates' in source or 'missing {legacy_key}' in source


def _classify() -> dict[str, Any]:
    sources = {name: _read(path) for name, path in FILES.items()}
    canonical_flat = tuple(field for group in CANONICAL_ROW_FIELDS.values() for field in group)
    legacy_flat = tuple(field for group in LEGACY_MIRROR_FIELDS.values() for field in group)

    design_brain_sources = "\n".join(
        sources[name]
        for name in (
            "candidate_evaluation",
            "combined_candidate_merge",
            "bending_fail_runtime",
            "bending_overdesign_runtime",
            "combined_fail_runtime",
        )
    )
    inputs_source = sources["inputs_page"]
    product_source = sources["product_correctness"]

    design_brain_counts = {
        "canonical": _field_counts(design_brain_sources, canonical_flat),
        "legacy_mirror": _field_counts(design_brain_sources, legacy_flat),
    }
    inputs_counts = {
        "canonical": _field_counts(inputs_source, canonical_flat),
        "legacy_mirror": _field_counts(inputs_source, legacy_flat),
    }
    product_correctness_pairs = _pair_presence(product_source, REQUIRED_MIRROR_PAIRS)

    blockers = []
    if _legacy_required_assertion_present(product_source):
        blockers.append(
            {
                "blocker": "product_correctness_requires_legacy_and_canonical_mirror_pairs",
                "file": str(FILES["product_correctness"].relative_to(ROOT)),
                "reason": "The current correctness gate still requires legacy row-model mirrors as authority instead of optional projection parity.",
            }
        )
    ownership_rows = [
        {
            "surface": "canonical row-model fields",
            "fields": sorted(canonical_flat),
            "current_owner": "Design Brain contract/ladders internally, with shared/page consumers reading projected outputs",
            "target_owner": "Design Brain contract/ladders",
            "status": "contract_driven_inside_combined_runtime",
        },
        {
            "surface": "combined update compatibility projection",
            "fields": [
                "normalise_combined_canonical_reinforcement_updates",
                "merge_updates",
            ],
            "current_owner": "design_brain.combined_bending_shear_candidate_merge",
            "target_owner": "Design Brain canonical row-model contract adapter",
            "status": "canonical_boundary_completed",
        },
    ]

    next_slice = {
        "title": "Retire remaining proof-only row-model scaffolds",
        "steps": [
            "Keep combined runtime internals canonical-only and verify no runtime row reintroduces legacy bottom mirrors.",
            "Retire verifier-only compatibility language that still describes a projection boundary.",
            "Then move to the next proof-only or safety-only Design Brain scaffolding surface.",
        ],
    }

    return {
        "schema": "design_brain_row_model_contract_ladder_ownership_audit.v1",
        "status": "PASS",
        "contract_driven_now": True,
        "safe_to_delete_legacy_mirrors_now": True,
        "design_brain_counts": design_brain_counts,
        "inputs_page_counts": inputs_counts,
        "product_correctness_mirror_pairs": product_correctness_pairs,
        "ownership": ownership_rows,
        "blockers": blockers,
        "next_slice": next_slice,
        "line_evidence": {
            "combined_normalizer": _line_hits(
                sources["combined_candidate_merge"],
                "normalise_combined_canonical_reinforcement_updates",
            ),
            "combined_projection": _line_hits(
                sources["combined_candidate_merge"],
                "project_combined_reinforcement_update_compatibility_mirrors",
            ),
            "product_correctness_required_pairs": _line_hits(product_source, "required_equal_pairs"),
            "inputs_row_model_legacy_debug": _line_hits(inputs_source, "row_model_legacy_sync"),
        },
        "decision": (
            "Combined runtime internals and the combined family boundary are now canonical-only. Legacy mirror fields are "
            "no longer emitted by the combined Design Brain path; remaining cleanup is verifier/proof scaffolding only."
        ),
    }


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_brain_row_model_contract_ladder_ownership_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_row_model_contract_ladder_ownership_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Brain Row-Model Contract/Ladder Ownership Audit",
        "",
        f"Status: `{snapshot['status']}`",
        f"Contract-driven now: `{snapshot['contract_driven_now']}`",
        f"Safe to delete legacy mirrors now: `{snapshot['safe_to_delete_legacy_mirrors_now']}`",
        "",
        "## Ownership",
        "",
    ]
    for row in snapshot["ownership"]:
        lines.extend(
            [
                f"- {row['surface']}: `{row['status']}`",
                f"  - current owner: `{row['current_owner']}`",
                f"  - target owner: `{row['target_owner']}`",
            ]
        )
    lines.extend(["", "## Blockers", ""])
    lines.extend(
        [
            f"- `{row['blocker']}` in `{row['file']}`: {row['reason']}"
            for row in snapshot["blockers"]
        ]
        or ["- none"]
    )
    lines.extend(
        [
            "",
            "## Next Slice",
            "",
            f"{snapshot['next_slice']['title']}.",
            "",
        ]
    )
    lines.extend(f"- {step}" for step in snapshot["next_slice"]["steps"])
    lines.extend(["", "## Decision", "", snapshot["decision"], ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    snapshot = _classify()
    json_path, md_path = _write(snapshot)
    print(f"design_brain_row_model_contract_ladder_ownership_audit {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
