"""Summarise Apply, stale-revision and session-continuity evidence files.

The summariser is intentionally read-only.  It consumes browser evidence
produced by existing Runtime probes and never becomes a second state owner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


STALE_WORDS = ("stale", "superseded", "revision")
SESSION_KEYS = ("session_contract", "post_commit_audit", "session_state")


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def summarise(payloads: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    apply_attempts = apply_successes = apply_failures = stale_revision_count = session_loss_count = 0
    failure_reasons: dict[str, int] = {}
    evidence_files = 0
    for filename, payload in payloads:
        evidence_files += 1
        for item in _walk(payload):
            button_found = item.get("button_found")
            committed = item.get("product_apply_updates_committed")
            if button_found is True or committed is not None or "transaction_error" in item:
                apply_attempts += 1
                if committed is True:
                    apply_successes += 1
                elif committed is False or item.get("transaction_error"):
                    apply_failures += 1
                    reason = str(item.get("transaction_error") or item.get("apply_error") or "not_committed")
                    failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            raw_reason = " ".join(str(item.get(key) or "") for key in ("transaction_error", "apply_error", "stop_reason", "status"))
            if any(word in raw_reason.lower() for word in STALE_WORDS):
                stale_revision_count += 1
            for key in SESSION_KEYS:
                contract = item.get(key)
                if isinstance(contract, dict):
                    ok = contract.get("ok")
                    if ok is False or contract.get("state_loss") is True or contract.get("session_state_loss") is True:
                        session_loss_count += 1
    return {
        "evidence_files": evidence_files,
        "apply_attempts": apply_attempts,
        "apply_successes": apply_successes,
        "apply_failures": apply_failures,
        "apply_failure_reasons": failure_reasons,
        "stale_revision_events": stale_revision_count,
        "session_state_loss_events": session_loss_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payloads = []
    for path in args.files:
        try:
            payloads.append((str(path), json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SystemExit(f"cannot read JSON evidence {path}: {exc}")
    rendered = json.dumps(summarise(payloads), indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
