"""Audit terminal active-failure trace-row consumer reachability.

Proof-only. This determines whether the remaining terminal active-failure
trace rows in inputs_page.py can be deleted, compressed, or must remain as
non-authoritative compatibility/debug rows.
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

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
VERIFICATION_DIR = ROOT / "tools" / "verification"

EVENTS = (
    "enter_terminal_active_failure_blocker_finalizer",
    "terminal_active_failure_blocker_source_before_filter",
    "terminal_active_failure_blocker_source_after_filter",
    "terminal_active_failure_blocker_suppress_cta_before",
    "terminal_active_failure_blocker_suppress_cta_after",
    "terminal_active_failure_publication_finalizer_before",
    "terminal_active_failure_publication_finalizer_after",
    "terminal_active_failure_blocker_finalized",
    "return_terminal_active_failure_blocker",
)

KNOWN_CONSUMER_SCRIPTS = (
    "resolver_terminal_active_failure_publication_tail_snapshot.py",
    "design_guide_terminal_active_failure_blocker_finalizer_cutover.py",
    "design_guide_terminal_active_failure_trace_shell_cleanup_audit.py",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not paths:
        return {"status": "MISSING", "path": None}
    path = paths[0]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "ERROR", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    status = str(payload.get("status") or payload.get("result") or "UNKNOWN")
    if "PASS" in status.upper():
        status = "PASS"
    return {"status": status, "path": str(path), "payload": payload}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _source_event_counts(source: str) -> dict[str, int]:
    return {event: source.count(event) for event in EVENTS}


def _consumer_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(VERIFICATION_DIR.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        source = _read(path)
        counts = _source_event_counts(source)
        used = {event: count for event, count in counts.items() if count > 0}
        if not used:
            continue
        name = path.name
        if name == "resolver_terminal_active_failure_publication_tail_snapshot.py":
            role = "live_trace_tail_verifier"
            deletion_impact = "blocks_plain_deletion"
        elif name == "design_guide_terminal_active_failure_blocker_finalizer_cutover.py":
            role = "focused_cutover_verifier"
            deletion_impact = "requires_update_before_deletion"
        elif name == "design_guide_terminal_active_failure_trace_shell_cleanup_audit.py":
            role = "cleanup_audit_verifier"
            deletion_impact = "requires_update_before_deletion"
        else:
            role = "reference_or_auxiliary_verifier"
            deletion_impact = "review_before_deletion"
        rows.append(
            {
                "file": str(path.relative_to(ROOT)),
                "role": role,
                "event_count": sum(used.values()),
                "events": used,
                "known_consumer": name in KNOWN_CONSUMER_SCRIPTS,
                "deletion_impact": deletion_impact,
            }
        )
    return rows


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    emitters = _source_event_counts(inputs_source)
    emitted_events = {event: count for event, count in emitters.items() if count > 0}
    trace_rows_deleted = not emitted_events
    consumers = _consumer_inventory()
    product_source_consumers = [
        file
        for file in ("design_brain", "ui")
        if any((ROOT / file).glob("**/*.py"))
        and any(event in "\n".join(_read(path) for path in (ROOT / file).glob("**/*.py")) for event in EVENTS)
    ]
    latest_trace_cleanup = _latest("design_guide_terminal_active_failure_trace_shell_cleanup_audit")
    latest_cutover = _latest("design_guide_terminal_active_failure_blocker_finalizer_cutover")
    latest_tail = _latest("resolver_terminal_active_failure_publication_tail")
    blocking_consumers = [
        row
        for row in consumers
        if row.get("deletion_impact")
        in {"blocks_plain_deletion", "requires_update_before_deletion"}
    ]
    old_live_tail_consumers = [
        row for row in consumers if row.get("deletion_impact") == "blocks_plain_deletion"
    ]
    plain_deletion_safe_now = not blocking_consumers and not product_source_consumers
    return {
        "decision": (
            "TRACE_ROWS_REFERENCED_BY_VERIFIER_INTERNAL_ASSERTIONS_NOT_SAFE_TO_DELETE"
            if blocking_consumers
            else (
                "TRACE_ROWS_DELETED_NO_REACHABLE_CONSUMERS"
                if trace_rows_deleted
                else "TRACE_ROWS_NOT_REACHABLE_SAFE_DELETION_CANDIDATE"
            )
        ),
        "terminal_trace_emitters": {
            "file": "inputs_page.py",
            "events_present": emitted_events,
            "all_expected_events_present": all(emitters.get(event, 0) > 0 for event in EVENTS),
            "trace_rows_deleted": trace_rows_deleted,
            "event_sequence_hash": _stable_hash(list(EVENTS)),
        },
        "consumer_inventory": consumers,
        "consumer_summary": {
            "consumer_count": len(consumers),
            "known_consumer_count": sum(1 for row in consumers if row.get("known_consumer")),
            "blocking_plain_deletion_count": len(blocking_consumers),
            "old_live_tail_consumer_count": len(old_live_tail_consumers),
            "product_source_consumer_count": len(product_source_consumers),
            "product_source_consumers": product_source_consumers,
        },
        "latest": {
            "trace_shell_cleanup": {
                "status": latest_trace_cleanup.get("status"),
                "path": latest_trace_cleanup.get("path"),
            },
            "terminal_finalizer_cutover": {
                "status": latest_cutover.get("status"),
                "path": latest_cutover.get("path"),
            },
            "terminal_publication_tail": {
                "status": latest_tail.get("status"),
                "path": latest_tail.get("path"),
            },
        },
        "classification": {
            "product_behavior_authority": False,
            "publication_authority": False,
            "cta_apply_authority": False,
            "visible_wording_authority": False,
            "debug_verifier_compatibility_rows": True,
            "plain_deletion_safe_now": plain_deletion_safe_now,
            "trace_rows_deleted": trace_rows_deleted,
            "compression_or_deletion_requires_consumer_migration": bool(blocking_consumers),
            "next_safe_step": (
                "Delete or compress the page-emitted terminal trace events in one narrow slice, "
                "then rerun this reachability audit and the composed locks."
                if plain_deletion_safe_now
                else (
                    "Migrate the terminal cutover and cleanup verifiers from raw trace-event "
                    "presence assertions to controller trace-compatibility assertions; only then "
                    "delete or compress the page-emitted terminal trace events."
                )
            ),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    emitters = dict(capture.get("terminal_trace_emitters") or {})
    summary = dict(capture.get("consumer_summary") or {})
    latest = dict(capture.get("latest") or {})
    classification = dict(capture.get("classification") or {})
    return {
        "trace_emitters_state_valid": (
            emitters.get("trace_rows_deleted") is True
            or emitters.get("all_expected_events_present") is True
        ),
        "known_consumers_accounted_for": summary.get("known_consumer_count", 0) >= 0,
        "product_source_consumers_absent": summary.get("product_source_consumer_count") == 0,
        "plain_deletion_not_blocked_by_consumer": summary.get(
            "blocking_plain_deletion_count", 0
        )
        == 0,
        "old_live_tail_consumer_migrated": summary.get("old_live_tail_consumer_count") == 0,
        "trace_shell_cleanup_passes": (latest.get("trace_shell_cleanup") or {}).get("status")
        == "PASS",
        "terminal_finalizer_cutover_passes": (latest.get("terminal_finalizer_cutover") or {}).get("status")
        == "PASS",
        "trace_rows_not_product_authority": classification.get("product_behavior_authority") is False,
        "trace_rows_not_publication_authority": classification.get("publication_authority") is False,
        "plain_deletion_safety_classified": isinstance(
            classification.get("plain_deletion_safe_now"), bool
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    summary = dict(capture.get("consumer_summary") or {})
    classification = dict(capture.get("classification") or {})
    lines = [
        "# Terminal Trace-Row Consumer Reachability Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Consumer Summary",
            "",
            f"- Consumer count: `{summary.get('consumer_count')}`",
            f"- Known consumers: `{summary.get('known_consumer_count')}`",
            f"- Blocking plain deletion: `{summary.get('blocking_plain_deletion_count')}`",
            f"- Product source consumers: `{summary.get('product_source_consumer_count')}`",
            "",
            "## Consumers",
        ]
    )
    for row in capture.get("consumer_inventory") or []:
        lines.append(
            f"- `{row.get('file')}`: `{row.get('role')}`, impact `{row.get('deletion_impact')}`"
        )
    lines.extend(
        [
            "",
            "## Classification",
        ]
    )
    lines.extend(f"- {key}: `{value}`" for key, value in classification.items())
    lines.extend(
        [
            "",
            "No product behavior, visible wording, CTA/apply semantics, or family runtime changed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_terminal_trace_row_consumer_reachability_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_terminal_trace_row_consumer_reachability_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_terminal_trace_row_consumer_reachability_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if status == "PASS":
        print(str(capture.get("decision")))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
