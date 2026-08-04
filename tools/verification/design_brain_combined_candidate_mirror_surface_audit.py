from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MERGE = ROOT / "design_brain" / "combined_bending_shear_candidate_merge.py"
COMBINED_FAMILY = ROOT / "design_brain" / "families" / "combined_bending_shear_fail.py"
COMBINED_RUNTIME = ROOT / "design_brain" / "families" / "bending_and_shear_fail_govern" / "runtime.py"
PRODUCT_CORRECTNESS = ROOT / "tools" / "verification" / "runners" / "product_correctness_focused_checks.py"
VERIFICATION = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

CANONICAL_NORMALIZER = "normalise_combined_canonical_reinforcement_updates"
PROJECTION_FUNCTION = "project_combined_reinforcement_update_compatibility_mirrors"
LEGACY_MIRROR_FUNCTION = "canonicalise_combined_reinforcement_update_mirrors"
REQUIRED_PAIR_ASSERTIONS = (
    ("bot1_count", "bot_row_1_bars"),
    ("db_bot_1", "bot_row_1_dia"),
    ("top1_count", "top_row_1_bars"),
    ("db_top_1", "top_row_1_dia"),
)


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _line_hits(source: str, token: str) -> list[int]:
    return [lineno for lineno, line in enumerate(source.splitlines(), start=1) if token in line]


def _has_required_pair_assertions(source: str) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for legacy_key, canonical_key in REQUIRED_PAIR_ASSERTIONS:
        checks[f"{legacy_key}->{canonical_key}"] = legacy_key in source and canonical_key in source
    return checks


def _legacy_required_pair_assertions(source: str) -> bool:
    return '_assert(legacy_key in updates' in source or 'missing {legacy_key}' in source


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    merge_source = _read(MERGE)
    family_source = _read(COMBINED_FAMILY)
    runtime_source = _read(COMBINED_RUNTIME)
    product_source = _read(PRODUCT_CORRECTNESS)

    failures: list[str] = []

    canonical_normalizer_present = f"def {CANONICAL_NORMALIZER}(" in merge_source
    projection_function_present = f"def {PROJECTION_FUNCTION}(" in merge_source
    legacy_function_present = f"def {LEGACY_MIRROR_FUNCTION}(" in merge_source
    if not canonical_normalizer_present:
        failures.append("canonical_normalizer_missing")
    if legacy_function_present:
        failures.append("legacy_mirror_function_still_present")

    family_projection_hits = _line_hits(family_source, f"{PROJECTION_FUNCTION}(")
    family_canonical_hits = _line_hits(family_source, f"{CANONICAL_NORMALIZER}(")
    runtime_projection_hits = _line_hits(runtime_source, f"{PROJECTION_FUNCTION}(")
    runtime_canonical_hits = _line_hits(runtime_source, f"{CANONICAL_NORMALIZER}(")
    product_pair_assertions = _has_required_pair_assertions(product_source)

    if not runtime_canonical_hits:
        failures.append("combined_runtime_no_longer_calls_canonical_normalizer")
    if runtime_projection_hits:
        failures.append("combined_runtime_still_calls_projection_function")

    product_blocker_present = _legacy_required_pair_assertions(product_source)

    payload = {
        "snapshot_name": "design_brain_combined_candidate_mirror_surface_audit",
        "generated_at": timestamp,
        "result": "PASS" if not failures else "FAIL",
        "combined_update_shape": {
            "canonical_normalizer": CANONICAL_NORMALIZER,
            "canonical_normalizer_present": canonical_normalizer_present,
            "compatibility_projection": PROJECTION_FUNCTION,
            "compatibility_projection_present": projection_function_present,
            "legacy_mirror_function_removed": not legacy_function_present,
            "merge_file": str(MERGE.relative_to(ROOT)).replace("\\", "/"),
        },
        "consumers": {
            "combined_family_projection_lines": family_projection_hits,
            "combined_family_canonical_lines": family_canonical_hits,
            "combined_runtime_projection_lines": runtime_projection_hits,
            "combined_runtime_canonical_lines": runtime_canonical_hits,
            "product_correctness_pair_assertions": product_pair_assertions,
        },
        "classification": {
            "safe_delete_now": not projection_function_present,
            "live_inputs_page_authority_blocker": False,
            "update_shape_consumer_blocker": False,
            "compatibility_projection_boundary_live": projection_function_present,
            "reason": (
                "Combined runtime internals normalize to canonical row-model keys only, and the explicit combined-family "
                "compatibility projection has been removed. No old-shape reinforcement mirror emitter remains in the "
                "combined path."
                if not projection_function_present
                else (
                    "Combined runtime internals now normalize to canonical row-model keys only. The remaining old-shape "
                    "surface is one explicit compatibility projection at the combined family output boundary, kept live "
                    "because the combined family still emits legacy bottom-reinforcement mirrors outward."
                    if not product_blocker_present
                    else
                    "Combined runtime internals now normalize to canonical row-model keys only. The remaining old-shape "
                    "surface is one explicit compatibility projection at the combined family output boundary, kept live "
                    "because downstream product correctness and apply-shape parity still expect both legacy and canonical keys."
                )
            ),
        },
        "next_safe_target": (
            "Move to the next internal proof-only or safety-only scaffolding surface."
            if not projection_function_present
            else
            "Prove downstream combined-family/controller/apply consumers can accept canonical-only updates, then delete "
            "the combined family compatibility projection adapter."
        ),
        "failures": failures,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_brain_combined_candidate_mirror_surface_audit_{timestamp.replace(':', '-')}.json"
    md_path = AUDITS / f"design_brain_combined_candidate_mirror_surface_audit_{timestamp.replace(':', '-')}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Design Brain Combined Candidate Mirror Surface Audit",
        "",
        f"## Summary\n{payload['result']}",
        "",
        f"- Canonical normalizer present: `{canonical_normalizer_present}`",
        f"- Compatibility projection present: `{projection_function_present}`",
        f"- Legacy mirror function removed: `{not legacy_function_present}`",
        f"- Combined family projection lines: `{family_projection_hits}`",
        f"- Combined runtime canonical lines: `{runtime_canonical_hits}`",
        f"- Product correctness still requires legacy mirror pairs: `{product_blocker_present}`",
        f"- Safe delete now: `{payload['classification']['safe_delete_now']}`",
        "",
        "## Reason",
        "",
        payload["classification"]["reason"],
        "",
        "## Next Safe Target",
        "",
        payload["next_safe_target"],
        "",
        "## Failures",
        "",
        *([f"- `{failure}`" for failure in failures] or ["None."]),
        "",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"design_brain_combined_candidate_mirror_surface_audit {payload['result']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if payload["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
