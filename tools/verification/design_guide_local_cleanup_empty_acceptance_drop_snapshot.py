"""Proof-only root-cause snapshot for post-click empty Design Guide render.

This verifier composes the latest SHEAR_FAIL_BENDING_OVERDESIGN slot/DOM proof
with source inspection of `_maybe_promote_safe_local_cleanup_primary(...)`.

It proves the current root cause without changing product behaviour:

* guidance compute returns one item,
* local-cleanup promotion changes the renderable item list from 1 to 0,
* the final render-visible payload receives item_count=0, and
* the source contains accepted-green branches that return an empty list instead
  of an accepted/efficient guidance card.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"


def _latest_slot_artifact() -> Path | None:
    paths = sorted(
        ARTIFACT_DIR.glob("design_guide_shear_fail_bending_overdesign_slot_dom_replacement_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    return paths[-1] if paths else None


def _function_source(text: str, name: str) -> str:
    marker = f"def {name}("
    start = text.find(marker)
    if start < 0:
        return ""
    match = re.search(r"\ndef [A-Za-z_][A-Za-z0-9_]*\(", text[start + 1 :])
    end = start + 1 + match.start() if match else len(text)
    return text[start:end]


def _stage_drop_rows(trace_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = dict(json.loads(line))
        except json.JSONDecodeError:
            continue
        block = str(row.get("block") or "")
        if block.startswith("_render_fast_design_guidance_panel.stage.") or block in {
            "_compute_design_guidance_items.for_design_guide",
            "_render_fast_design_guidance_panel.render_visible_items_payload",
        }:
            rows.append(
                {
                    "timestamp": row.get("timestamp"),
                    "block": block.replace("_render_fast_design_guidance_panel.stage.", ""),
                    "guidance_items_raw_count": row.get("guidance_items_raw_count"),
                    "guidance_items_count": row.get("guidance_items_count"),
                    "render_plan_visible_count": row.get("render_plan_visible_count"),
                    "item_count": row.get("item_count"),
                    "first_title": row.get("first_title"),
                    "render_plan_reason": row.get("render_plan_reason"),
                    "call_count": row.get("call_count"),
                }
            )
    return rows


def _write_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Local Cleanup Empty Acceptance Drop Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Classification: `{payload['classification']}`",
        f"Reason: {payload['reason']}",
        f"Product behaviour changed: `{payload['product_behaviour_changed']}`",
        "",
        "## Proof",
        "",
        f"- Latest slot artifact: `{payload.get('slot_artifact')}`",
        f"- Latest trace file: `{payload.get('trace_file')}`",
        f"- Compute returned item: `{payload['proof'].get('compute_returned_item')}`",
        f"- Drop at local cleanup promote: `{payload['proof'].get('drop_at_local_cleanup_promote')}`",
        f"- Render visible payload empty: `{payload['proof'].get('render_visible_payload_empty')}`",
        f"- Source empty accepted-green returns: `{payload['proof'].get('source_empty_accepted_green_returns')}`",
        "",
        "## Key Stage Rows",
        "",
        "| Block | Raw | Items | Visible | Payload Count |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload.get("key_stage_rows") or []:
        lines.append(
            "| `{block}` | `{raw}` | `{items}` | `{visible}` | `{payload}` |".format(
                block=row.get("block"),
                raw=row.get("guidance_items_raw_count"),
                items=row.get("guidance_items_count"),
                visible=row.get("render_plan_visible_count"),
                payload=row.get("item_count"),
            )
        )
    lines.extend(
        [
            "",
            "## Next Safe Fix",
            "",
            str(payload.get("next_safe_fix") or ""),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

    slot_artifact = _latest_slot_artifact()
    failures: list[str] = []
    slot_payload: dict[str, Any] = {}
    if slot_artifact is None:
        failures.append("missing_slot_dom_replacement_artifact")
    else:
        slot_payload = json.loads(slot_artifact.read_text(encoding="utf-8"))

    trace_files = list((slot_payload.get("trace_summary") or {}).get("trace_files") or [])
    trace_path = Path(trace_files[-1]) if trace_files else None
    if trace_path is None or not trace_path.exists():
        failures.append("missing_trace_file_from_slot_artifact")
        stage_rows: list[dict[str, Any]] = []
    else:
        stage_rows = _stage_drop_rows(trace_path)

    inputs_text = INPUTS_PAGE.read_text(encoding="utf-8")
    function = _function_source(inputs_text, "_maybe_promote_safe_local_cleanup_primary")
    if not function:
        failures.append("local_cleanup_promoter_function_not_found")

    source_empty_return_tokens = [
        'debug["local_cleanup_blocked_reason"] = "accepted_green_no_materially_overprovided_family"',
        'debug["local_cleanup_blocked_reason"] = "accepted_green_no_unresolved_materially_overprovided_family"',
        "return [], debug",
    ]
    source_empty_accepted_green_returns = all(token in function for token in source_empty_return_tokens)

    compute_returned_item = any(
        row.get("block") == "_compute_design_guidance_items.for_design_guide"
        and int(row.get("item_count") or 0) >= 1
        for row in stage_rows
    )
    before_local_cleanup = next(
        (row for row in stage_rows if row.get("block") == "after_family_consolidation" and row.get("call_count") == 2),
        {},
    )
    after_local_cleanup = next(
        (row for row in stage_rows if row.get("block") == "after_local_cleanup_promote" and row.get("call_count") == 2),
        {},
    )
    render_payload = next(
        (row for row in stage_rows if row.get("block") == "_render_fast_design_guidance_panel.render_visible_items_payload"),
        {},
    )
    drop_at_local_cleanup = bool(
        int(before_local_cleanup.get("guidance_items_count") or 0) >= 1
        and int(after_local_cleanup.get("guidance_items_count") or 0) == 0
    )
    render_visible_payload_empty = bool(int(render_payload.get("item_count") or 0) == 0)

    proof = {
        "compute_returned_item": compute_returned_item,
        "drop_at_local_cleanup_promote": drop_at_local_cleanup,
        "render_visible_payload_empty": render_visible_payload_empty,
        "source_empty_accepted_green_returns": source_empty_accepted_green_returns,
    }
    all_proven = all(proof.values()) and not failures
    payload = {
        "schema": "design_guide_local_cleanup_empty_acceptance_drop_snapshot.v1",
        "status": "PASS" if all_proven else "PARTIAL",
        "created_at": stamp,
        "classification": (
            "LOCAL_CLEANUP_ACCEPTED_GREEN_EMPTY_RETURN_DROPS_FINAL_CARD"
            if all_proven
            else "LOCAL_CLEANUP_EMPTY_DROP_NOT_FULLY_PROVEN"
        ),
        "reason": (
            "The post-click accepted-green local-cleanup path returns an empty item list, so final rendering receives no card item."
            if all_proven
            else "The verifier could not prove every link in the empty-render chain."
        ),
        "product_behaviour_changed": False,
        "slot_artifact": str(slot_artifact) if slot_artifact else None,
        "trace_file": str(trace_path) if trace_path else None,
        "proof": proof,
        "key_stage_rows": [
            row
            for row in stage_rows
            if row.get("block")
            in {
                "_compute_design_guidance_items.for_design_guide",
                "after_family_consolidation",
                "after_local_cleanup_promote",
                "after_render_plan",
                "_render_fast_design_guidance_panel.render_visible_items_payload",
            }
            and (row.get("call_count") in {2, None} or row.get("block") == "_render_fast_design_guidance_panel.render_visible_items_payload")
        ],
        "source_empty_return_tokens": source_empty_return_tokens,
        "failures": failures,
        "next_safe_fix": (
            "Change only the accepted-green no-cleanup local-cleanup branch so it preserves or creates an "
            "already-efficient guidance item instead of returning an empty list. Verify with the slot/DOM "
            "snapshot and family architecture audit. Do not change family runtimes, contracts, CTA rendering, "
            "publication semantics, apply routing, or visible wording beyond using the existing accepted/efficient card."
        ),
    }

    artifact_path = ARTIFACT_DIR / f"design_guide_local_cleanup_empty_acceptance_drop_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_local_cleanup_empty_acceptance_drop_{stamp}.md"
    payload["artifact"] = str(artifact_path)
    payload["report"] = str(report_path)
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(payload, report_path)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classification": payload["classification"],
                "artifact": str(artifact_path),
                "report": str(report_path),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
