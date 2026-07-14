"""Matrix snapshot for reproducing Inputs/Design Guide layout gap sources.

Proof-only. Runs the DOM gap source capture across several exact URL / browser
recipe states and reports whether any scenario proves a real app-owned gap
source that is safe to patch.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_browser_dom_gap_source_snapshot import (  # noqa: E402
    _capture,
    _classify,
)
from tools.verification.helpers.browser_one_click_regression import (  # noqa: E402
    _start_streamlit,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


DEFAULT_RECIPES = (
    "A_bending_under_only",
    "R1A_M300_V0",
    "R2A_M0_V400",
    "C_combined_underdesign",
    "OPT_EXPECT_BENDING_SAFE_OVERDESIGNED",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _element_presence(snapshot: dict[str, Any]) -> dict[str, bool]:
    elements = dict(snapshot.get("elements") or {})
    return {
        key: bool((elements.get(key) or {}).get("exists"))
        for key in (
            "summary_stack",
            "batch_heading",
            "batch_block",
            "design_guide_heading",
            "design_guide_block",
            "design_guide_card",
            "proof_pending_placeholder",
            "first_paint_shell",
        )
    }


def _best_snapshot_for_presence(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {}
    return max(
        snapshots,
        key=lambda row: sum(
            1
            for present in _element_presence(dict(row or {})).values()
            if present
        ),
    )


def _summarize_case(case: dict[str, Any], capture: dict[str, Any], classification: dict[str, Any]) -> dict[str, Any]:
    snapshots = [dict(row or {}) for row in list(capture.get("snapshots") or [])]
    best = _best_snapshot_for_presence(snapshots)
    return {
        "case_id": case["case_id"],
        "kind": case["kind"],
        "url": capture.get("url"),
        "recipe": capture.get("recipe"),
        "status": classification.get("status"),
        "audit_result": classification.get("audit_result"),
        "risks": list(classification.get("risks") or []),
        "measurement_gaps": list(classification.get("measurement_gaps") or []),
        "selected_snapshot_label": classification.get("selected_snapshot_label"),
        "best_presence_snapshot_label": best.get("label"),
        "element_presence": _element_presence(best),
        "final_gaps": dict(classification.get("final_gaps") or {}),
        "layout_shift_total": classification.get("layout_shift_total"),
        "safe_app_owned_patch_target_proven": bool(classification.get("risks")),
    }


def _run_matrix(base_url: str, *, exact_url: str | None, recipes: tuple[str, ...], timeout_s: float, headed: bool) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    if exact_url:
        cases.append({"case_id": "exact_url_current_state", "kind": "exact_url", "exact_url": exact_url, "recipe": ""})
    for recipe in recipes:
        cases.append({"case_id": f"recipe_{recipe}", "kind": "browser_recipe", "exact_url": None, "recipe": recipe})

    rows: list[dict[str, Any]] = []
    raw_captures: dict[str, Any] = {}
    for case in cases:
        capture = _capture(
            base_url,
            recipe=str(case.get("recipe") or ""),
            timeout_s=timeout_s,
            headed=headed,
            exact_url=case.get("exact_url"),
            scroll_scan=True,
        )
        classification = _classify([dict(row or {}) for row in list(capture.get("snapshots") or [])])
        rows.append(_summarize_case(case, capture, classification))
        raw_captures[case["case_id"]] = {
            "capture_hash": _stable_hash(capture),
            "classification": classification,
        }
    patch_ready_rows = [row for row in rows if row.get("safe_app_owned_patch_target_proven")]
    materialized_rows = [
        row
        for row in rows
        if (row.get("element_presence") or {}).get("summary_stack")
        and (
            (row.get("element_presence") or {}).get("batch_heading")
            or (row.get("element_presence") or {}).get("design_guide_heading")
            or (row.get("element_presence") or {}).get("design_guide_card")
        )
    ]
    decision = (
        "READY_FOR_NARROW_LAYOUT_PATCH"
        if patch_ready_rows
        else "NO_APP_OWNED_LAYOUT_PATCH_TARGET_PROVEN"
        if materialized_rows
        else "DOWNSTREAM_PANELS_NOT_MATERIALIZED_IN_MATRIX"
    )
    return {
        "cases": rows,
        "raw_capture_index": raw_captures,
        "classification": {
            "status": "PASS",
            "decision": decision,
            "safe_patch_case_count": len(patch_ready_rows),
            "materialized_case_count": len(materialized_rows),
            "case_count": len(rows),
            "recommended_next_slice": (
                "Patch only the measured case/source with a focused readiness verifier."
                if patch_ready_rows
                else "Capture a headed/user-specific reproducing session before product layout changes."
                if not materialized_rows
                else "No layout patch; move to the next measured non-layout hotspot."
            ),
        },
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Layout Gap Reproduction Matrix",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Decision: `{cls.get('decision')}`",
        f"- Case count: `{cls.get('case_count')}`",
        f"- Materialized case count: `{cls.get('materialized_case_count')}`",
        f"- Safe patch case count: `{cls.get('safe_patch_case_count')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        "",
        "## Cases",
        "",
        "| Case | Result | Risks | Measurement gaps | Presence |",
        "|---|---|---|---|---|",
    ]
    for row in payload.get("cases") or []:
        presence = ", ".join(key for key, value in (row.get("element_presence") or {}).items() if value) or "-"
        lines.append(
            f"| `{row.get('case_id')}` | `{row.get('audit_result')}` | "
            f"`{', '.join(row.get('risks') or []) or '-'}` | "
            f"`{', '.join(row.get('measurement_gaps') or []) or '-'}` | `{presence}` |"
        )
    lines.extend(["", "## Recommendation", "", str(cls.get("recommended_next_slice") or ""), ""])
    return "\n".join(lines)


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_layout_gap_reproduction_matrix_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_layout_gap_reproduction_matrix_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8751)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_GAP_MATRIX_URL"))
    parser.add_argument("--exact-url", default=os.environ.get("DESIGN_GUIDE_LAYOUT_GAP_MATRIX_EXACT_URL"))
    parser.add_argument("--recipe", action="append", dest="recipes")
    parser.add_argument("--timeout-s", type=float, default=12.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url and not args.exact_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            os.environ["PERF_TRACE_INPUTS"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=60.0)

        matrix = _run_matrix(
            base_url,
            exact_url=str(args.exact_url) if args.exact_url else None,
            recipes=tuple(args.recipes or DEFAULT_RECIPES),
            timeout_s=float(args.timeout_s),
            headed=bool(args.headed),
        )
        payload = {
            "created_at": created_at,
            "schema": "design_guide_layout_gap_reproduction_matrix.v1",
            "status": matrix["classification"]["status"],
            "product_behaviour_changed": False,
            "base_url": base_url,
            "exact_url": args.exact_url,
            "recipes": list(args.recipes or DEFAULT_RECIPES),
            "snapshot_hash": _stable_hash(matrix),
            **matrix,
        }
        json_path, md_path = _write(payload)
        print(f"design_guide_layout_gap_reproduction_matrix {payload['status']}")
        print(f"json={json_path}")
        print(f"report={md_path}")
        print(json.dumps(payload["classification"], indent=2, sort_keys=True))
        return 0
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
