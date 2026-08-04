"""Audit consumers of compute compatibility helper rows.

This is proof-only. It does not approve deletion and does not change product
behaviour. The goal is to distinguish live product consumers from verifier-only
compatibility metadata before the next physical extraction/deletion slice.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
DESIGN_BRAIN = ROOT / "design_brain"
VERIFICATION = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

HELPERS: dict[str, dict[str, Any]] = {
    "_mark_compute_debug_restamp_metadata_compatibility_only": {
        "rows_key": "final_publication_compute_debug_restamp_metadata_rows",
        "hash_key": "final_publication_compute_debug_restamp_metadata_hash",
        "row_ids": (
            "compute_stage_selected_title_action_family_restamp",
            "late_evidence_selected_action_restamp",
            "post_evidence_cleanup_contract_rebound_enabled_flag",
        ),
        "expected_call_count": 3,
        "allowed_product_scope": "debug_trace compatibility metadata only",
    },
    "_mark_compute_publication_evidence_a_class_compatibility_only": {
        "rows_key": "final_publication_compute_a_class_evidence_rows",
        "hash_key": "final_publication_compute_a_class_evidence_rows_hash",
        "row_ids": (
            "raw_selected_item_identity",
            "render_reason",
            "state_fingerprint",
            "raw_rebound_item_identity",
        ),
        "expected_call_count": 4,
        "allowed_product_scope": "debug_trace compatibility metadata only",
    },
}

CODE_GLOBS = ("*.py",)
COMPOSED_LOCK_PREFIXES = {
    "design_guide_independence_lock": "design_guide_independence_lock",
    "design_guide_render_bridge_lock": "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
    "compute_rebound_mutation_adapter_cutover": (
        "design_guide_compute_rebound_mutation_adapter_cutover"
    ),
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _line_numbers(source: str, token: str) -> list[int]:
    return [
        index
        for index, line in enumerate(source.splitlines(), start=1)
        if token in line
    ]


def _function_source(source: str, function_name: str) -> tuple[int | None, int | None, str]:
    marker = f"def {function_name}("
    start_index = source.find(marker)
    if start_index < 0:
        return None, None, ""
    start_line = source[:start_index].count("\n") + 1
    next_def_index = source.find("\ndef ", start_index + len(marker))
    next_class_index = source.find("\nclass ", start_index + len(marker))
    candidates = [idx for idx in (next_def_index, next_class_index) if idx >= 0]
    end_index = min(candidates) if candidates else len(source)
    end_line = source[:end_index].count("\n") + 1
    return start_line, end_line, source[start_index:end_index]


def _iter_code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for glob in CODE_GLOBS:
        files.extend(root.rglob(glob))
    return [
        path
        for path in files
        if "__pycache__" not in path.parts
        and ".venv" not in path.parts
        and "venv" not in path.parts
    ]


def _occurrences(token: str, *, roots: tuple[Path, ...] | None = None) -> list[dict[str, Any]]:
    files = [INPUTS_PAGE]
    search_roots = roots or (DESIGN_BRAIN, VERIFICATION)
    if DESIGN_BRAIN in search_roots and DESIGN_BRAIN.exists():
        files.extend(_iter_code_files(DESIGN_BRAIN))
    if VERIFICATION in search_roots and VERIFICATION.exists():
        files.extend(_iter_code_files(VERIFICATION))
    seen: set[Path] = set()
    rows: list[dict[str, Any]] = []
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(source.splitlines(), start=1):
            if token in line:
                rows.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": line_number,
                        "text": line.strip()[:220],
                    }
                )
    return rows


def _latest_artifact(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"found": True, "path": str(path), "status": None, "error": str(exc)}
    return {"found": True, "path": str(path), "status": payload.get("status"), "payload": payload}


def _call_parameter_ranges(source: str, helper: str) -> list[tuple[int, int]]:
    lines = source.splitlines()
    ranges: list[tuple[int, int]] = []
    for index, line in enumerate(lines, start=1):
        if f"{helper}(" not in line or line.lstrip().startswith("def "):
            continue
        depth = line.count("(") - line.count(")")
        end = index
        scan_index = index
        while depth > 0 and scan_index < len(lines):
            scan_index += 1
            next_line = lines[scan_index - 1]
            depth += next_line.count("(") - next_line.count(")")
            end = scan_index
        ranges.append((index, end))
    return ranges


def _in_ranges(line: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in ranges)


def _classify_occurrence(
    row: dict[str, Any],
    helper: str,
    helper_start: int | None,
    helper_end: int | None,
    call_ranges: list[tuple[int, int]],
) -> str:
    file_name = row["file"].replace("\\", "/")
    line = int(row["line"])
    if file_name == "inputs_page.py" and helper_start and helper_end and helper_start <= line < helper_end:
        return "helper_definition"
    if file_name == "inputs_page.py" and _in_ranges(line, call_ranges):
        return "live_helper_callsite_parameter"
    if file_name.startswith("tools/verification/"):
        return "verifier_or_inventory_consumer"
    if file_name.startswith("design_brain/"):
        return "design_brain_consumer"
    if file_name == "inputs_page.py":
        if helper in row["text"]:
            return "live_helper_callsite"
        return "inputs_page_consumer"
    return "unknown"


def _helper_audit(source: str, helper: str, meta: dict[str, Any]) -> dict[str, Any]:
    helper_start, helper_end, helper_source = _function_source(source, helper)
    call_ranges = _call_parameter_ranges(source, helper)
    definition_lines = _line_numbers(source, f"def {helper}(")
    call_lines = [
        line
        for line in _line_numbers(source, f"{helper}(")
        if line not in definition_lines
    ]
    helper_required_flags = {
        "compatibility_only": '"compatibility_only": True' in helper_source,
        "proof_only": '"proof_only": True' in helper_source,
        "cannot_override_final_publication": '"can_override_final_publication": False' in helper_source,
        "not_product_driving": '"product_driving": False' in helper_source,
        "not_render_driving": '"render_driving": False' in helper_source,
        "not_apply_driving": '"apply_driving": False' in helper_source,
        "not_session_driving": '"session_driving": False' in helper_source,
        "duplicate_stamp_bypass_guarded": "_final_publication_duplicate_stamp_bypass_decision(" in helper_source,
    }
    token_occurrences: dict[str, list[dict[str, Any]]] = {}
    consumer_counts: dict[str, int] = {}
    product_consumer_occurrences: list[dict[str, Any]] = []
    token_specs: list[tuple[str, str, tuple[Path, ...] | None]] = [
        ("rows_key", str(meta["rows_key"]), None),
        ("hash_key", str(meta["hash_key"]), None),
    ]
    # Row ids like "render_reason" and "state_fingerprint" are common field
    # names. Treat the row-id proof as the explicit helper call parameter, not
    # every unrelated product occurrence of those words.
    for row_id in meta["row_ids"]:
        token_specs.append((f"row_id:{row_id}", f'row_id="{row_id}"', (INPUTS_PAGE,)))
    for token_label, token, roots in token_specs:
        classified_rows: list[dict[str, Any]] = []
        for occurrence in _occurrences(str(token), roots=roots):
            classification = _classify_occurrence(
                occurrence,
                helper,
                helper_start,
                helper_end,
                call_ranges,
            )
            occurrence = dict(occurrence)
            occurrence["classification"] = classification
            classified_rows.append(occurrence)
            consumer_counts[classification] = consumer_counts.get(classification, 0) + 1
            if classification in {"inputs_page_consumer", "design_brain_consumer", "unknown"}:
                product_consumer_occurrences.append(occurrence)
        token_occurrences[token_label] = classified_rows

    expected_call_count = int(meta["expected_call_count"])
    helper_deleted = not definition_lines and not call_lines
    call_count_matches = len(call_lines) == expected_call_count
    helper_flags_ok = all(helper_required_flags.values())
    no_product_consumers = not product_consumer_occurrences
    if helper_deleted and no_product_consumers:
        classification = "A. helper deleted; verifier-only inventory references remain"
    elif helper_flags_ok and no_product_consumers and call_count_matches:
        classification = "B. verifier-only compatibility metadata; source callsites still live"
    else:
        classification = "E. needs investigation before deletion"
    return {
        "helper": helper,
        "definition_lines": definition_lines,
        "definition_span": [helper_start, helper_end],
        "call_lines": call_lines,
        "call_ranges": call_ranges,
        "call_count": len(call_lines),
        "expected_call_count": expected_call_count,
        "helper_deleted": helper_deleted,
        "call_count_matches": call_count_matches,
        "helper_required_flags": helper_required_flags,
        "token_occurrences": token_occurrences,
        "consumer_counts": consumer_counts,
        "product_consumer_occurrences": product_consumer_occurrences,
        "classification": classification,
        "deletion_ready_now": False,
        "next_action": (
            "Keep only verifier/inventory references until their snapshots are retargeted "
            "to the controller cutover and bridge-lock artifacts."
            if classification.startswith("A.")
            else
            "Update dependent verifier/inventory expectations to rely on controller "
            "mutation/publication lock artifacts, then remove this helper in a focused "
            "deletion slice."
            if classification.startswith("B.")
            else "Investigate unexpected product/design_brain consumers before any deletion."
        ),
    }


def _build_payload() -> dict[str, Any]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = INPUTS_PAGE.read_text(encoding="utf-8", errors="replace")
    helpers = [_helper_audit(source, helper, meta) for helper, meta in HELPERS.items()]
    latest_locks = {name: _latest_artifact(prefix) for name, prefix in COMPOSED_LOCK_PREFIXES.items()}
    failures: list[str] = []
    for name, artifact in latest_locks.items():
        if artifact.get("status") != "PASS":
            failures.append(f"{name}_latest_pass_artifact_missing")
    for helper in helpers:
        if helper["classification"].startswith("E."):
            failures.append(f"{helper['helper']}_unexpected_consumer_or_missing_flag")
        if helper["deletion_ready_now"]:
            failures.append(f"{helper['helper']}_unexpected_deletion_ready_without_separate_deadness_proof")

    payload = {
        "status": "PASS" if not failures else "FAIL",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "failures": failures,
        "summary": {
            "helpers_checked": len(helpers),
            "verifier_only_compatibility_metadata": sum(
                1 for helper in helpers if helper["classification"].startswith("B.")
            ),
            "unexpected_product_consumers": sum(
                len(helper["product_consumer_occurrences"]) for helper in helpers
            ),
            "deletion_ready_now": 0,
            "product_behavior_changed": False,
        },
        "helpers": helpers,
        "latest_locks": latest_locks,
        "next_safe_step": (
            "Create a deletion-readiness verifier that removes the old helper-row "
            "expectations from the dependent inventory snapshots, then delete one helper "
            "surface at a time only after composed locks stay green."
        ),
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    return payload


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Design Guide Compute Compatibility Helper Consumer Audit",
        "",
        f"Status: `{payload['status']}`",
        f"Snapshot hash: `{payload['snapshot_hash']}`",
        "",
        "## Summary",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in payload["summary"].items())
    lines.extend(["", "## Helper Classification", ""])
    lines.append(
        "| Helper | Calls | Classification | Product consumers | Next action |"
    )
    lines.append("|---|---:|---|---:|---|")
    for helper in payload["helpers"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{helper['helper']}`",
                    str(helper["call_count"]),
                    f"`{helper['classification']}`",
                    str(len(helper["product_consumer_occurrences"])),
                    str(helper["next_action"]).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Consumer Counts", ""])
    for helper in payload["helpers"]:
        lines.append(f"### `{helper['helper']}`")
        for key, value in sorted(helper["consumer_counts"].items()):
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    lines.extend(["## Latest Lock Artifacts", ""])
    for name, artifact in payload["latest_locks"].items():
        lines.append(f"- {name}: `{artifact.get('status')}` `{artifact.get('path')}`")
    lines.extend(["", "## Next Safe Step", "", str(payload["next_safe_step"])])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _build_payload()
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_compute_compatibility_helper_consumer_audit_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_compute_compatibility_helper_consumer_audit_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(payload, report_path)
    print(f"design_guide_compute_compatibility_helper_consumer_audit {payload['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
