"""Verify target-band candidate winner selection service extraction."""

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

from design_brain.candidate_evaluation import select_target_band_ranked_candidate  # noqa: E402


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


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


def _old_select(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    copied = [dict(row) for row in rows]
    copied.sort(key=lambda row: row["sort_key"])
    return copied[0]


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, target_loop = _function_segment(inputs_source, "_solve_one_click_to_target")

    cases = [
        {
            "case": "basic_min_tuple",
            "rows": [
                {"sort_key": (2, 0.1), "label": "late"},
                {"sort_key": (1, 0.4), "label": "winner"},
                {"sort_key": (1, 0.8), "label": "runner_up"},
            ],
        },
        {
            "case": "stable_tie_uses_first_row",
            "rows": [
                {"sort_key": (1, 0.4), "label": "first"},
                {"sort_key": (1, 0.4), "label": "second"},
            ],
        },
        {
            "case": "mixed_prefix_tuple",
            "rows": [
                {"sort_key": (0, 1, 0.3, 0.4), "label": "secondary"},
                {"sort_key": (0, 0, 0.5, 0.2), "label": "primary"},
            ],
        },
        {
            "case": "fallback_next_hop_negative_tier",
            "rows": [
                {"sort_key": (0, 0.01), "label": "normal"},
                {"sort_key": (-1,), "label": "fallback"},
            ],
        },
        {
            "case": "empty_pool",
            "rows": [],
        },
    ]

    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for case in cases:
        candidate_rows = [dict(row) for row in case["rows"]]
        old = _old_select(candidate_rows)
        new = select_target_band_ranked_candidate(candidate_rows)
        old_label = old.get("label") if isinstance(old, dict) else None
        new_label = new.get("label") if isinstance(new, dict) else None
        row = {
            "case": str(case["case"]),
            "old_label": old_label,
            "new_label": new_label,
            "matches": old_label == new_label,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    service_present = "def select_target_band_ranked_candidate(" in candidate_source
    page_delegates = "_select_target_band_ranked_candidate(scored)" in target_loop
    page_sort_removed = 'scored.sort(key=lambda x: x["sort_key"])' not in target_loop
    post_selection_logic_retained = all(
        token in target_loop
        for token in (
            "_one_click_step_improves(",
            "_one_click_in_band_shear_cleanup_candidate_allowed(",
            "evaluate_candidate_full(",
            "working.update(best[\"updates\"])",
            "_one_click_best_next_hop_improving_candidate(",
        )
    )
    forbidden_service_import_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if (
        mismatches
        or not service_present
        or not page_delegates
        or not page_sort_removed
        or not post_selection_logic_retained
        or forbidden_service_import_hits
    ):
        status = "FAIL"

    return {
        "status": status,
        "surface": "target_band_candidate_winner_selection",
        "inputs_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": start,
            "end_line": end,
        },
        "case_count": len(cases),
        "mismatches": mismatches,
        "parity_rows": rows,
        "static_checks": {
            "service_present": service_present,
            "page_delegates": page_delegates,
            "page_sort_removed": page_sort_removed,
            "post_selection_logic_retained": post_selection_logic_retained,
            "forbidden_service_import_hits": forbidden_service_import_hits,
        },
        "ownership": {
            "moved_to_candidate_evaluation": ["lexicographic selected-candidate pick from scored rows"],
            "remains_page_owned_for_now": [
                "no-improvement stop shaping",
                "in-band shear cleanup deferral override",
                "post-selection evaluation and working-state mutation",
                "fallback next-hop injection",
                "trace emission",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "audit/extract no-improvement stop decision or fallback next-hop injection after separate parity",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_candidate_winner_selection_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_candidate_winner_selection_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Candidate Winner Selection Service Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved only the lexicographic winner pick into `design_brain.candidate_evaluation.select_target_band_ranked_candidate(...)`.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Parity",
            f"- Cases checked: `{payload['case_count']}`",
            f"- Mismatches: `{len(payload['mismatches'])}`",
            "",
            "## Remaining Page-Owned Logic",
        ]
    )
    for item in payload["ownership"]["remains_page_owned_for_now"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
