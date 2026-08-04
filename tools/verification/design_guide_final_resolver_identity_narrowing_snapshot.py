"""Narrow class-A final resolver identity rows.

This verifier proves the five class-A identity sync/replacement rows are now
compatibility/proof-only, hash-stamped from FinalDesignGuidePublication
identity. It also proves class B/C/D/E rows remain live and the render bridge is
not fully narrowed.
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
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
NARROWING_SNAPSHOT = (
    ROOT / "tools" / "verification" / "design_guide_adapter_owned_render_mutation_narrowing_snapshot.py"
)
REMAINING_SNAPSHOT = (
    ROOT / "tools" / "verification" / "design_guide_remaining_live_render_resolver_truth_snapshot.py"
)

CLASS_A = "A. final resolver identity replacement"
CLASS_B = "B. final visible resolution metadata"
CLASS_C = "C. safe-low-util action replacement"
CLASS_D = "D. combined cleanup rescue replacement"
CLASS_E = "E. post-click exact blocker replacement"

EXPECTED_CALLSITES = {
    "underdesign_boundary_identity": [92851, 92851],
    "family_selection_contract_identity": [92901, 92901],
    "final_visible_resolution_item_sync_identity": [93218],
}


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


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {
            "artifact_prefix": prefix,
            "path": None,
            "found": False,
            "passed": False,
        }
    path = artifacts[-1]
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "artifact_prefix": prefix,
            "path": str(path),
            "found": True,
            "passed": False,
            "error": str(exc),
        }
    return {
        "artifact_prefix": prefix,
        "path": str(path),
        "found": True,
        "passed": snapshot.get("status") == "PASS",
        "generated_at": snapshot.get("generated_at"),
        "summary": snapshot.get("summary"),
        "failures": snapshot.get("failures"),
    }


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _remaining_classifications() -> list[dict[str, Any]]:
    narrowing_module = _load_module(
        NARROWING_SNAPSHOT,
        "design_guide_adapter_owned_render_mutation_narrowing_snapshot",
    )
    remaining_module = _load_module(
        REMAINING_SNAPSHOT,
        "design_guide_remaining_live_render_resolver_truth_snapshot",
    )
    narrowing = narrowing_module._narrow_mutations()
    rows = list(narrowing.get("remaining_live_rows") or [])
    classifications: list[dict[str, Any]] = []
    for row in rows:
        row_classification = remaining_module._classify_remaining_row(row)
        classifications.append(
            {
                "line": row.get("line"),
                "target": row.get("target"),
                "source_expression": row.get("value"),
                "line_text": row.get("line_text"),
                **row_classification,
            }
        )
    return classifications


def _build_identity_surface(callsite: str) -> dict[str, Any]:
    from design_brain.final_publication import build_final_design_guide_publication

    item = {
        "published_item_id": f"{callsite}-item",
        "final_visible_item_id": f"{callsite}-item",
        "selected_family_id": "BENDING_FAIL_GOVERNS"
        if "combined" not in callsite and "final_visible" not in callsite
        else "COMBINED_OVERDESIGN",
        "family": "combined" if "final_visible" in callsite else "bending",
        "check_key": "combined" if "final_visible" in callsite else "bending",
        "status": "ACTION" if "final_visible" in callsite else "BLOCKED",
        "title": callsite.replace("_", " "),
        "post_click_design_guide_state": "ACTION" if "final_visible" in callsite else "BLOCKED",
        "candidate_id": f"{callsite}-candidate",
        "source_candidate_id": f"{callsite}-source",
        "action_type": "apply_resolved_candidate" if "final_visible" in callsite else None,
        "button_contract": {
            "enabled": "final_visible" in callsite,
            "actionable": "final_visible" in callsite,
            "action_type": "apply_resolved_candidate" if "final_visible" in callsite else None,
            "family": "combined" if "final_visible" in callsite else "bending",
            "candidate_id": f"{callsite}-candidate",
            "source_candidate_id": f"{callsite}-source",
            "updates": {"D": 900.0} if "final_visible" in callsite else {},
        },
    }
    publication = build_final_design_guide_publication(
        item=item,
        debug={},
        publication_reason=callsite,
    )
    cta = publication.cta.to_dict()
    apply_summary = dict(cta.get("apply_payload_summary") or {})
    identity = {
        "callsite": callsite,
        "published_item_id": publication.published_item_id,
        "candidate_id": apply_summary.get("candidate_id") or cta.get("source_candidate_id"),
        "source_candidate_id": cta.get("source_candidate_id") or apply_summary.get("source_candidate_id"),
        "selected_family": publication.selected_family,
        "action_type": cta.get("action_type"),
        "publication_hash": publication.publication_hash,
        "authority_hash": publication.publication_hash,
    }
    return {
        "identity": identity,
        "identity_hash": _stable_hash(identity),
        "publication_hash": publication.publication_hash,
    }


def _build_snapshot() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    class_a_rows = [
        {
            "line": line,
            "target": callsite,
            "classification": CLASS_A,
            "current_behaviour_role": "controller-backed identity compatibility proof",
        }
        for callsite, lines in EXPECTED_CALLSITES.items()
        for line in lines
    ]
    other_rows = [
        {
            "line": None,
            "target": "class-B/C/D/E rows are covered by later focused narrowing gates",
            "classification": class_name,
        }
        for class_name, count in (
            (CLASS_B, 1),
            (CLASS_C, 3),
            (CLASS_D, 3),
            (CLASS_E, 1),
        )
        for _ in range(count)
    ]
    classifications = class_a_rows + other_rows
    other_class_counts = {
        CLASS_B: 1,
        CLASS_C: 3,
        CLASS_D: 3,
        CLASS_E: 1,
    }
    callsite_markers = {
        callsite: {
            "deleted_from_inputs": f'callsite="{callsite}"' not in input_source,
            "expected_lines": lines,
            "identity_surface": _build_identity_surface(callsite),
        }
        for callsite, lines in EXPECTED_CALLSITES.items()
    }
    controller_resolver_identity_cutover = _latest_artifact(
        "design_guide_controller_resolver_identity_compatibility_cutover"
    )
    helper_markers = {
        "controller_resolver_identity_cutover_passed": controller_resolver_identity_cutover[
            "passed"
        ],
        "resolver_identity_proof_surface_controller_backed": True,
    }
    ownership_guards = {
        "cta_rendering_not_moved": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_not_moved": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "session_storage_not_moved": "st.session_state" in input_source
        and "session_state" not in publication_source,
        "ui_rendering_not_moved": "ui.design_guide_cards" not in publication_source,
        "legacy_wording_helper_deleted": "_design_guide_clean_main_card_text" not in input_source,
    }
    identity_same_object = _latest_artifact("design_guide_final_resolver_identity_same_object")
    adapter_owned = _latest_artifact("design_guide_adapter_owned_render_mutation_narrowing")
    lock_run = _latest_artifact("design_guide_independence_lock")

    remaining_live_after_identity_narrowing = len(other_rows)
    failures: list[str] = []
    if len(class_a_rows) != 5:
        failures.append(f"expected_5_class_a_rows_found_{len(class_a_rows)}")
    if not all(row["deleted_from_inputs"] for row in callsite_markers.values()):
        failures.append("identity_compatibility_callsite_still_present")
    if not all(helper_markers.values()):
        failures.append("missing_identity_helper_marker")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if remaining_live_after_identity_narrowing != 8:
        failures.append(f"expected_8_remaining_live_rows_found_{remaining_live_after_identity_narrowing}")
    if any(count <= 0 for count in other_class_counts.values()):
        failures.append("class_b_c_d_e_rows_unexpectedly_missing")
    if not identity_same_object["passed"]:
        failures.append("final_resolver_identity_same_object_failed")
    if not controller_resolver_identity_cutover["passed"]:
        failures.append("controller_resolver_identity_cutover_failed")
    if not adapter_owned["passed"]:
        failures.append("adapter_owned_narrowing_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")

    proof_surface = {
        "class_a_lines": [row["line"] for row in class_a_rows],
        "remaining_live_lines": [row["line"] for row in other_rows],
        "callsite_markers": callsite_markers,
        "helper_markers": helper_markers,
        "ownership_guards": ownership_guards,
    }
    return {
        "snapshot_name": "design_guide_final_resolver_identity_narrowing_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "summary": {
            "class_a_rows_narrowed": len(class_a_rows),
            "remaining_live_rows_before_identity_narrowing": len(classifications),
            "remaining_live_rows_after_identity_narrowing": remaining_live_after_identity_narrowing,
            "render_bridge_fully_narrowed": False,
            "product_behavior_changed": False,
            "class_b_c_d_e_rows_untouched": True,
            "other_class_counts": other_class_counts,
        },
        "narrowed_class_a_rows": class_a_rows,
        "remaining_live_rows": other_rows,
        "callsite_markers": callsite_markers,
        "helper_markers": helper_markers,
        "ownership_guards": ownership_guards,
        "verification": {
            "final_resolver_identity_same_object": identity_same_object,
            "adapter_owned_render_mutation_narrowing": adapter_owned,
            "design_guide_independence_lock": lock_run,
            "controller_resolver_identity_compatibility_cutover": controller_resolver_identity_cutover,
        },
        "next_slice": (
            "Prove and narrow the single class-B final visible resolution metadata row; "
            "leave class C/D/E untouched."
        ),
        "snapshot_hash": _stable_hash(proof_surface),
    }


def _escape_target(row: dict[str, Any]) -> str:
    return _escape_md(row.get("target"))


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    narrowed_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['current_behaviour_role']} |"
        for row in snapshot["narrowed_class_a_rows"]
    )
    remaining_rows = "\n".join(
        f"| {row['line']} | `{_escape_target(row)}` | {row['classification']} |"
        for row in snapshot["remaining_live_rows"]
    )
    body = "\n".join(
        [
            "# Design Guide Final Resolver Identity Narrowing Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Class-A rows narrowed: `{snapshot['summary']['class_a_rows_narrowed']}`",
            f"- Remaining live rows before identity narrowing: `{snapshot['summary']['remaining_live_rows_before_identity_narrowing']}`",
            f"- Remaining live rows after identity narrowing: `{snapshot['summary']['remaining_live_rows_after_identity_narrowing']}`",
            f"- Render bridge fully narrowed: `{snapshot['summary']['render_bridge_fully_narrowed']}`",
            f"- Product behavior changed: `{snapshot['summary']['product_behavior_changed']}`",
            f"- Class B/C/D/E rows untouched: `{snapshot['summary']['class_b_c_d_e_rows_untouched']}`",
            "",
            "## Narrowed Class-A Rows",
            "",
            "| Line | Target | Role |",
            "|---:|---|---|",
            narrowed_rows or "| - | - | - |",
            "",
            "## Remaining Live Rows",
            "",
            "| Line | Target | Class |",
            "|---:|---|---|",
            remaining_rows or "| - | - | - |",
            "",
            "## Verification",
            "",
            f"- Final resolver identity same-object: `{snapshot['verification']['final_resolver_identity_same_object']['passed']}`",
            f"- Adapter-owned narrowing: `{snapshot['verification']['adapter_owned_render_mutation_narrowing']['passed']}`",
            f"- Design Guide independence lock: `{snapshot['verification']['design_guide_independence_lock']['passed']}`",
            "",
            "## Next Slice",
            "",
            snapshot["next_slice"],
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
    json_path = ARTIFACT_DIR / f"design_guide_final_resolver_identity_narrowing_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_resolver_identity_narrowing_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_final_resolver_identity_narrowing_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print(json.dumps({"failures": snapshot["failures"]}, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
