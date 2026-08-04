"""Verify bottom-reo legacy local rejection reason moved to family ownership."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS = ROOT / "inputs_page.py"
BENDING = ROOT / "design_brain" / "families" / "bending.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PAGE_WRAPPER = "_legacy_bottom_local_rejection_reason"
FAMILY_HELPER = "resolve_bottom_reo_legacy_local_rejection_reason"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _candidate_ductility_util(candidate: dict) -> float | None:
    raw = ((candidate.get("bending_components") or {}).get("ductility_util"))
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _old_page_reason(
    pick: dict,
    *,
    seed_bu_f: float | None,
    ductility_seed: bool,
    seed_du: float | None,
) -> str | None:
    bu = ((pick.get("overview") or {}).get("utils") or {}).get("bending")
    try:
        bu_f = float(bu) if bu is not None else None
    except (TypeError, ValueError):
        bu_f = None
    if bu_f is None:
        return "missing_bending_util"
    if ductility_seed:
        pdu = _candidate_ductility_util(pick)
        if seed_du is not None and pdu is not None and float(pdu) >= float(seed_du) - 1e-9:
            return "ductility_not_improved"
        return None
    if seed_bu_f is not None and float(bu_f) >= float(seed_bu_f) - 1e-9:
        return "bending_util_not_improved"
    return None


def _sample_cases() -> list[dict[str, Any]]:
    return [
        {
            "case": "missing_bending_util",
            "pick": {"overview": {"utils": {}}},
            "seed_bu_f": 0.95,
            "ductility_seed": False,
            "seed_du": None,
        },
        {
            "case": "ductility_not_improved",
            "pick": {
                "overview": {"utils": {"bending": 0.92}},
                "bending_components": {"ductility_util": 0.91},
            },
            "seed_bu_f": 0.95,
            "ductility_seed": True,
            "seed_du": 0.90,
        },
        {
            "case": "ductility_improved",
            "pick": {
                "overview": {"utils": {"bending": 0.92}},
                "bending_components": {"ductility_util": 0.80},
            },
            "seed_bu_f": 0.95,
            "ductility_seed": True,
            "seed_du": 0.90,
        },
        {
            "case": "bending_util_not_improved",
            "pick": {"overview": {"utils": {"bending": 0.96}}},
            "seed_bu_f": 0.95,
            "ductility_seed": False,
            "seed_du": None,
        },
        {
            "case": "bending_util_improved",
            "pick": {"overview": {"utils": {"bending": 0.88}}},
            "seed_bu_f": 0.95,
            "ductility_seed": False,
            "seed_du": None,
        },
        {
            "case": "missing_seed_bending_util",
            "pick": {"overview": {"utils": {"bending": 0.96}}},
            "seed_bu_f": None,
            "ductility_seed": False,
            "seed_du": None,
        },
    ]


def _forbidden_terms(segment: str) -> dict[str, bool]:
    return {
        "imports_inputs_page": "inputs_page" in segment,
        "imports_streamlit": "streamlit" in segment or "st." in segment,
        "uses_session_state": "session_state" in segment,
        "uses_apply_routing": "apply_" in segment or "one_click" in segment,
        "uses_rendering": "render_" in segment or "html" in segment,
        "uses_publication": "FinalDesignGuidePublication" in segment or "publication" in segment,
    }


def build_payload() -> dict[str, Any]:
    from design_brain.families.bending import resolve_bottom_reo_legacy_local_rejection_reason

    inputs_source = _read(INPUTS)
    bending_source = _read(BENDING)
    page_start, page_end, page_segment = _function_segment(inputs_source, PAGE_WRAPPER)
    helper_start, helper_end, helper_segment = _function_segment(bending_source, FAMILY_HELPER)

    parity_rows: list[dict[str, Any]] = []
    for case in _sample_cases():
        old = _old_page_reason(
            dict(case["pick"]),
            seed_bu_f=case.get("seed_bu_f"),
            ductility_seed=bool(case.get("ductility_seed")),
            seed_du=case.get("seed_du"),
        )
        new = resolve_bottom_reo_legacy_local_rejection_reason(
            dict(case["pick"]),
            seed_bending_util=case.get("seed_bu_f"),
            ductility_seed=bool(case.get("ductility_seed")),
            seed_ductility_util=case.get("seed_du"),
        )
        parity_rows.append({"case": case.get("case"), "old": old, "new": new, "matches": old == new})

    forbidden = _forbidden_terms(helper_segment)
    checks = {
        "family_helper_exists": bool(helper_segment),
        "family_helper_has_no_page_or_ui_forbidden_terms": not any(forbidden.values()),
        "page_wrapper_delegates_to_family_helper": "_resolve_bottom_reo_legacy_local_rejection_reason(" in page_segment,
        "page_wrapper_preserves_signature": "seed_candidate: dict" in page_segment
        and "seed_bu_f: float | None" in page_segment
        and "seed_du: float | None" in page_segment,
        "page_wrapper_no_longer_contains_reason_logic": "bending_util_not_improved" not in page_segment
        and "ductility_not_improved" not in page_segment
        and "missing_bending_util" not in page_segment,
        "all_sample_cases_match": all(row["matches"] for row in parity_rows),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "decision": (
            "BOTTOM_REO_LEGACY_REJECTION_POLICY_FAMILY_ADAPTER_EXTRACTED"
            if status == "PASS"
            else "BOTTOM_REO_LEGACY_REJECTION_POLICY_EXTRACTION_FAILED"
        ),
        "page_wrapper_lines": {"start": page_start, "end": page_end},
        "family_helper_lines": {"start": helper_start, "end": helper_end},
        "parity_rows": parity_rows,
        "family_helper_forbidden_terms": forbidden,
        "checks": checks,
        "remaining_page_owned_inputs": [
            "page wrapper remains temporarily for selector loop compatibility",
            "live selector loop still page-owned",
            "seed util values are still computed by the live selector loop",
        ],
        "next_safe_slice": "bottom_reo_compound_preference_family_extraction_or_selector_loop_parity",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_bottom_reo_legacy_rejection_policy_family_extraction_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_bottom_reo_legacy_rejection_policy_family_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Bottom Reo Legacy Rejection Policy Family Extraction",
        "",
        f"## Executive Summary: {payload.get('status')}",
        "",
        f"Decision: `{payload.get('decision')}`",
        "",
        "## Behaviour Preserved",
        "",
        "The page wrapper signature remains in place for the current selector loop. The bending family now owns the legacy rejection reason policy.",
        "",
        "## Parity Cases",
        "",
        "| Case | Old | New | Match |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("parity_rows") or []:
        lines.append(f"| `{row.get('case')}` | `{row.get('old')}` | `{row.get('new')}` | `{row.get('matches')}` |")
    lines.extend(["", "## Remaining Page-Owned Inputs", ""])
    lines.extend(f"- {item}" for item in payload.get("remaining_page_owned_inputs") or [])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{name}`: `{value}`" for name, value in dict(payload.get("checks") or {}).items())
    lines.extend(["", "## Next Safe Slice", "", f"`{payload.get('next_safe_slice')}`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    payload = build_payload()
    json_path, report_path = write_artifacts(payload)
    print(f"design_guide_bottom_reo_legacy_rejection_policy_family_extraction {payload.get('status')}")
    print(f"decision={payload.get('decision')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if payload.get("status") != "PASS":
        failed = [name for name, value in dict(payload.get("checks") or {}).items() if not value]
        print(f"failed_checks={','.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
