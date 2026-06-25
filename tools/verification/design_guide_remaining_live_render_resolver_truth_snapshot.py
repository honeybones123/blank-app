"""Classify remaining live render-stage resolver truth.

This is audit/proof only. It uses the adapter-owned render mutation narrowing
snapshot to identify the remaining live mutation rows and classifies each one
without moving render, CTA/apply, session/UI, wording, or family runtime
ownership.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
NARROWING_SNAPSHOT = (
    ROOT / "tools" / "verification" / "design_guide_adapter_owned_render_mutation_narrowing_snapshot.py"
)
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

CLASS_A = "A. final resolver identity replacement"
CLASS_B = "B. final visible resolution metadata"
CLASS_C = "C. safe-low-util action replacement"
CLASS_D = "D. combined cleanup rescue replacement"
CLASS_E = "E. post-click exact blocker replacement"
CLASS_F = "F. still unknown / needs proof"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _load_narrowing_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "design_guide_adapter_owned_render_mutation_narrowing_snapshot",
        NARROWING_SNAPSHOT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load adapter-owned narrowing snapshot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _line_context(line_no: int, radius: int = 8) -> str:
    lines = INPUTS_PAGE.read_text(encoding="utf-8").splitlines()
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start - 1 : end])


def _classify_remaining_row(row: dict[str, Any]) -> dict[str, Any]:
    target = str(row.get("target") or "")
    value = str(row.get("value") or "")
    line_text = str(row.get("line_text") or "")
    line = int(row.get("line") or 0)
    context = _line_context(line)
    combined = "\n".join([target, value, line_text, context])

    if "_session_zero_shear_debug" in combined:
        return {
            "classification": CLASS_E,
            "current_behaviour_role": "session/debug exact-blocker evidence replacement for zero-shear terminal proof",
            "final_publication_equivalent_truth": "partial: blocker/evidence truth is represented, session storage remains page-owned",
            "can_be_narrowed_next": False,
            "required_proof_before_narrowing": (
                "session/debug storage proof that this exact-blocker evidence is derived from "
                "FinalDesignGuidePostResolverMutationProof and remains non-authoritative"
            ),
        }
    if "_final_safe_low_util_action" in combined or "visible_safe_low_util_cleanup_from_blocker_evidence" in combined:
        return {
            "classification": CLASS_C,
            "current_behaviour_role": "promotes visible blocker into best safe low-util cleanup action",
            "final_publication_equivalent_truth": "partial: identity/display/CTA can be represented after the action item exists",
            "can_be_narrowed_next": False,
            "required_proof_before_narrowing": (
                "safe-low-util action replacement same-object proof comparing replacement item, "
                "resolution item, render reason, CTA hash, display hash, and publication hash"
            ),
        }
    if "_safe_combined_item" in combined or "final_visible_combined_low_util_safe_cleanup" in combined:
        return {
            "classification": CLASS_D,
            "current_behaviour_role": "rescues family-selection boundary with safe combined cleanup action",
            "final_publication_equivalent_truth": "partial: publication object can carry the result after rescue item selection",
            "can_be_narrowed_next": False,
            "required_proof_before_narrowing": (
                "combined cleanup rescue same-object proof showing FinalDesignGuidePublication can own "
                "the rescue item identity, CTA/display hashes, and family-selection repair reason"
            ),
        }
    if "presentation" in target or "render_reason" in target:
        return {
            "classification": CLASS_B,
            "current_behaviour_role": "updates final visible resolution metadata for render presentation",
            "final_publication_equivalent_truth": "partial: display fields exist, resolver metadata still remains live",
            "can_be_narrowed_next": False,
            "required_proof_before_narrowing": (
                "final visible resolution metadata proof mapping render_reason/presentation to "
                "FinalDesignGuidePublication display/evidence without changing visible wording"
            ),
        }
    if target == "_final_visible_item" or target == '_final_visible_resolution["item"]':
        role = "replaces final selected visible item identity"
        if "_underdesign_boundary_items" in combined:
            role = "replaces final selected item with underdesign repair boundary item"
        elif "_family_selection_items" in combined:
            role = "replaces final selected item with family-selection contract item"
        elif 'dict(_final_visible_item)' in value:
            role = "syncs final visible resolution item to current final visible item"
        return {
            "classification": CLASS_A,
            "current_behaviour_role": role,
            "final_publication_equivalent_truth": "partial: published_item_id exists, but live resolver still chooses/syncs item",
            "can_be_narrowed_next": False,
            "required_proof_before_narrowing": (
                "final resolver identity same-object proof proving selected item identity and "
                "resolution item sync are derived from FinalDesignGuidePublication"
            ),
        }
    return {
        "classification": CLASS_F,
        "current_behaviour_role": "unclassified remaining render resolver mutation",
        "final_publication_equivalent_truth": "unknown",
        "can_be_narrowed_next": False,
        "required_proof_before_narrowing": "missing row-specific proof",
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    narrowing_module = _load_narrowing_module()
    narrowing = narrowing_module._narrow_mutations()
    remaining_rows = list(narrowing.get("remaining_live_rows") or [])
    classifications: list[dict[str, Any]] = []
    for row in remaining_rows:
        row_classification = _classify_remaining_row(row)
        classifications.append(
            {
                "line": row.get("line"),
                "target": row.get("target"),
                "source_expression": row.get("value"),
                "line_text": row.get("line_text"),
                **row_classification,
                "context_hash": _stable_hash(_line_context(int(row.get("line") or 0))),
            }
        )

    class_counts = {
        class_name: sum(1 for row in classifications if row["classification"] == class_name)
        for class_name in (CLASS_A, CLASS_B, CLASS_C, CLASS_D, CLASS_E, CLASS_F)
    }
    unknown_rows = [row for row in classifications if row["classification"] == CLASS_F]
    can_narrow_next_rows = [row for row in classifications if row["can_be_narrowed_next"]]
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    ownership_guards = {
        "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_not_moved": "st.session_state" in input_source
        and "session_state" not in publication_source,
        "ui_rendering_not_moved": "ui.design_guide_cards" not in publication_source,
        "visible_wording_not_moved": "_design_guide_clean_main_card_text" in input_source
        and "_design_guide_clean_main_card_text" not in publication_source,
    }
    narrowing_run = _run("tools/verification/design_guide_adapter_owned_render_mutation_narrowing_snapshot.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")

    failures: list[str] = []
    if not classifications:
        failures.append("no_remaining_live_rows_found")
    if unknown_rows:
        failures.append("unknown_remaining_rows_require_proof")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if not narrowing_run["passed"]:
        failures.append("adapter_owned_narrowing_snapshot_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")

    proof_surface = {
        "classifications": classifications,
        "class_counts": class_counts,
        "unknown_lines": [row["line"] for row in unknown_rows],
        "ownership_guards": ownership_guards,
        "remaining_live_count": len(classifications),
    }
    next_slice = (
        "Create a final resolver identity same-object proof for class A rows."
        if class_counts[CLASS_A]
        else "Create the smallest class-specific same-object proof before narrowing."
    )
    return {
        "snapshot_name": "design_guide_remaining_live_render_resolver_truth_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "remaining_live_rows": len(classifications),
            "unknown_rows": len(unknown_rows),
            "can_narrow_next_rows": len(can_narrow_next_rows),
            "class_counts": class_counts,
            "product_behavior_changed": False,
            "next_smallest_slice": next_slice,
        },
        "classifications": classifications,
        "ownership_guards": ownership_guards,
        "verification": {
            "adapter_owned_render_mutation_narrowing": narrowing_run,
            "design_guide_independence_lock": lock_run,
        },
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    rows = "\n".join(
        "| {line} | `{target}` | {classification} | {role} | {equiv} | `{can}` | {proof} |".format(
            line=row["line"],
            target=_escape_md(row["target"]),
            classification=_escape_md(row["classification"]),
            role=_escape_md(row["current_behaviour_role"]),
            equiv=_escape_md(row["final_publication_equivalent_truth"]),
            can=row["can_be_narrowed_next"],
            proof=_escape_md(row["required_proof_before_narrowing"]),
        )
        for row in snapshot["classifications"]
    )
    class_counts = snapshot["summary"]["class_counts"]
    body = "\n".join(
        [
            "# Design Guide Remaining Live Render Resolver Truth Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Remaining live rows: `{snapshot['summary']['remaining_live_rows']}`",
            f"- Unknown rows: `{snapshot['summary']['unknown_rows']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            f"- A final resolver identity replacement: `{class_counts[CLASS_A]}`",
            f"- B final visible resolution metadata: `{class_counts[CLASS_B]}`",
            f"- C safe-low-util action replacement: `{class_counts[CLASS_C]}`",
            f"- D combined cleanup rescue replacement: `{class_counts[CLASS_D]}`",
            f"- E post-click exact blocker replacement: `{class_counts[CLASS_E]}`",
            f"- F unknown / needs proof: `{class_counts[CLASS_F]}`",
            "",
            "## Rows",
            "",
            "| Line | Target | Class | Current role | FinalPublication equivalent | Can narrow next | Required proof |",
            "|---:|---|---|---|---|---|---|",
            rows or "| - | - | - | - | - | - | - |",
            "",
            "## Ownership Guards",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Next Smallest Slice",
            "",
            snapshot["summary"]["next_smallest_slice"],
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_remaining_live_render_resolver_truth_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_remaining_live_render_resolver_truth_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_remaining_live_render_resolver_truth_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
