"""Diagnostic audit for the read-only Design Brain governing-state classifier.

This script scans verifier JSON artifacts or explicit JSON files and compares
the visible Design Guide outcome with the read-only governing-state classifier.
It is intentionally non-failing by default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.governing_state import classify_governing_state


DEFAULT_SCAN_ROOT = ROOT / "artifacts" / "verification"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "verification"


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _load_json(path: Path) -> Any:
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                rows.append(json.loads(text))
        return rows
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _walk_payloads(value: Any, *, path: str = "$") -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        if (
            "design_brain_result" in value
            or "debug_trace" in value
            or "guidance_items" in value
            or "governing_state_classifier" in value
        ):
            found.append((path, dict(value)))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_walk_payloads(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_payloads(child, path=f"{path}[{index}]"))
    return found


def _walk_browser_snapshots(value: Any, *, path: str = "$") -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        body_text = str(value.get("body_text") or value.get("main_text_sample") or "")
        if "Design Guide" in body_text and any(
            token in body_text
            for token in (
                "Bending capacity is low",
                "Shear capacity is low",
                "Design is efficient",
                "cleanup blocked",
                "repair blocked",
                "Run one-click auto design",
            )
        ):
            found.append((path, dict(value)))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_walk_browser_snapshots(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_browser_snapshots(child, path=f"{path}[{index}]"))
    return found


def _family_from_label(label: str) -> str:
    text = label.lower()
    if "shear" in text:
        return "shear"
    if "bending" in text:
        return "bending"
    if "crack" in text:
        return "crack"
    if "deflection" in text:
        return "deflection"
    return label.strip().lower()


def _status_and_util_from_body(body_text: str) -> tuple[dict[str, str], dict[str, float]]:
    statuses: dict[str, str] = {}
    utils: dict[str, float] = {}
    compact = re.sub(r"\s+", " ", body_text or "")
    labels = [
        ("bending", r"Bending(?:\s+[^\s]+)?\s+ULS"),
        ("shear", r"Shear(?:\s+[^\s]+)?\s+ULS"),
        ("crack", r"Crack control(?:\s+[^\s]+)?\s+SLS"),
        ("deflection", r"Deflection(?:\s+[^\s]+)?\s+SLS"),
    ]
    for index, (family, pattern) in enumerate(labels):
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if not match:
            continue
        next_starts = [
            re.search(next_pattern, compact[match.end() :], flags=re.IGNORECASE)
            for _, next_pattern in labels[index + 1 :]
        ]
        next_positions = [match.end() + m.start() for m in next_starts if m]
        end = min(next_positions) if next_positions else min(len(compact), match.end() + 280)
        segment = compact[match.start() : end]
        util_match = re.search(r"Utilisation\s+([-+]?\d+(?:\.\d+)?)", segment, flags=re.IGNORECASE)
        if util_match:
            try:
                utils[family] = float(util_match.group(1))
            except ValueError:
                pass
        for status in ("FAIL", "NEAR LIMIT", "PASS", "CAPACITY", "NOT RUN", "INFO"):
            if re.search(rf"\b{re.escape(status)}\b", segment, flags=re.IGNORECASE):
                statuses[family] = status
                break
    return statuses, utils


def _visible_title_from_body(body_text: str) -> str:
    known_titles = [
        "Bending and shear capacity are low",
        "Bending capacity is low",
        "Shear capacity is low",
        "Bending and shear repair blocked",
        "Bending repair blocked",
        "Shear repair blocked",
        "Bending and shear cleanup blocked",
        "Bending cleanup blocked",
        "Shear cleanup blocked",
        "Design is efficient - target band achieved",
        "Design is efficient - no further safe cleanup available",
        "Design is efficient",
        "Cleanup is advisory for this design state",
    ]
    lower = body_text.lower()
    for title in known_titles:
        if title.lower() in lower:
            return title
    return ""


def _browser_snapshot_payload(snapshot: dict) -> dict:
    body_text = str(snapshot.get("body_text") or "")
    statuses, utils = _status_and_util_from_body(body_text)
    any_fail = any(status == "FAIL" for status in statuses.values())
    title = _visible_title_from_body(body_text)
    if "Bending and shear" in title:
        family = "combined"
    else:
        family = _family_from_label(title)
    button_texts = [str(item or "") for item in _as_list(snapshot.get("button_texts"))]
    cta_visible = any(
        text.strip() in {"Run one-click auto design", "Apply Recommendation", "Apply Auto Design"}
        or text.strip().startswith("Apply ")
        for text in button_texts
    )
    cta_enabled = False
    for button in _as_list(snapshot.get("buttons")):
        if not isinstance(button, dict):
            continue
        text = str(button.get("text") or "")
        if (
            text.strip() in {"Run one-click auto design", "Apply Recommendation", "Apply Auto Design"}
            or text.strip().startswith("Apply ")
        ):
            cta_enabled = not bool(button.get("disabled"))
            break
    intent = "already_efficient" if "design is efficient" in title.lower() else (
        "specific_blocker" if "blocked" in title.lower() else (
            "required_fix" if any_fail else "advisory_warning"
        )
    )
    item = {
        "title_main": title,
        "title": title,
        "family": family,
        "check_key": family,
        "status": "FAIL" if any_fail else ("PASS" if "efficient" in title.lower() else ""),
        "guidance_intent": intent,
        "button_contract": {
            "enabled": bool(cta_enabled),
            "actionable": bool(cta_enabled),
            "action_type": "apply_resolved_candidate" if cta_enabled else None,
            "family": family,
            "updates": {"browser_visible_cta": True} if cta_enabled else {},
            "preview_pass": True if cta_enabled else False,
            "blocking_reason": None if cta_enabled else "browser_snapshot_no_enabled_cta",
        },
    }
    if "efficient" in title.lower():
        item["design_guide_terminal_state"] = "optimal"
    return {
        "guidance_items": [item] if title else [],
        "debug_trace": {
            "overview": {
                "statuses": statuses,
                "utils": utils,
                "any_fail": bool(any_fail),
                "all_key_pass": bool(statuses and not any_fail),
                "worst_util": max(utils.values()) if utils else None,
                "fail_keys": [family for family, status in statuses.items() if status == "FAIL"],
            },
            "browser_snapshot_classifier_source": True,
            "button_contract_enabled": bool(cta_enabled),
        },
        "browser_snapshot_source": True,
    }


def _visible_primary(payload: dict) -> dict:
    items = _as_list(payload.get("guidance_items"))
    if items and isinstance(items[0], dict):
        return dict(items[0])
    debug = _as_dict(payload.get("debug_trace"))
    item = _as_dict(debug.get("primary_item") or debug.get("visible_primary_item"))
    return item


def _visible_outcome(payload: dict) -> dict:
    result = _as_dict(payload.get("design_brain_result"))
    debug = _as_dict(payload.get("debug_trace"))
    primary = _visible_primary(payload)
    card = _as_dict(result.get("card") or debug.get("design_guide_engine_decision", {}).get("card"))
    contract = _as_dict(
        primary.get("button_contract")
        or debug.get("displayed_primary_button_contract")
        or debug.get("primary_button_contract")
        or debug.get("button_contract")
        or _as_dict(result.get("cta"))
    )
    title = str(
        primary.get("title_main")
        or primary.get("title")
        or card.get("title")
        or debug.get("primary_card_title")
        or ""
    ).strip()
    intent = str(
        primary.get("guidance_intent")
        or card.get("intent")
        or debug.get("primary_guidance_intent")
        or result.get("outcome_id")
        or ""
    ).strip()
    status = str(primary.get("status") or result.get("status") or card.get("badge") or "").strip()
    terminal_state = str(
        primary.get("design_guide_terminal_state")
        or debug.get("design_guide_terminal_state")
        or ""
    ).strip()
    cta_enabled = bool(contract.get("enabled") or contract.get("actionable") or _as_dict(result.get("cta")).get("enabled"))
    return {
        "title": title,
        "intent": intent,
        "status": status,
        "terminal_state": terminal_state,
        "cta_enabled": bool(cta_enabled),
        "outcome_id": result.get("outcome_id"),
        "card_kind": result.get("card_kind"),
        "is_terminal": bool(result.get("is_terminal") or terminal_state),
    }


def _classification_kind(visible: dict, classifier: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    state = str(classifier.get("governing_state") or "UNKNOWN")
    title = str(visible.get("title") or "").lower()
    intent = str(visible.get("intent") or "").lower()
    status = str(visible.get("status") or "").upper()
    terminal = bool(visible.get("is_terminal") or visible.get("terminal_state"))
    cta_enabled = bool(visible.get("cta_enabled"))
    active_failures = set(classifier.get("active_failures") or [])
    action_required = bool(classifier.get("candidate_action_required"))
    exact_stop = bool(classifier.get("exact_stop_possible"))

    terminal_or_blocked = bool(
        terminal
        or intent in {"already_efficient", "specific_blocker", "passing_exact_stop", "blocked_specific_reason"}
        or status in {"PASS", "OPTIMAL", "BLOCKED", "INFO"}
        or "design is efficient" in title
        or "blocked" in title
    )

    if terminal_or_blocked and state == "UNKNOWN":
        reasons.append("terminal_or_blocked_visible_without_governing_state")
        return "contract violation", reasons
    if active_failures and ("design is efficient" in title or intent == "already_efficient"):
        reasons.append("active_failure_visible_as_efficient")
        return "contract violation", reasons
    if active_failures and terminal and not action_required and not exact_stop:
        reasons.append("active_failure_terminal_without_action_or_exact_stop")
        return "contract violation", reasons
    if cta_enabled and not action_required:
        reasons.append("visible_cta_enabled_but_classifier_did_not_find_action_required")
        return "suspect", reasons
    if (
        state in {"BENDING_OVERDESIGN_GOVERNS", "SHEAR_OVERDESIGN_GOVERNS", "COMBINED_OVERDESIGN"}
        and terminal_or_blocked
        and not exact_stop
        and not action_required
    ):
        reasons.append("overdesign_terminal_without_exact_stop_or_action")
        return "suspect", reasons

    reasons.append("visible_outcome_consistent_with_read_only_classifier")
    return "expected", reasons


def _audit_payload(source: str, location: str, payload: dict) -> dict:
    debug = _as_dict(payload.get("debug_trace"))
    result = _as_dict(payload.get("design_brain_result") or debug.get("design_brain_result"))
    primary = _visible_primary(payload)
    classifier = _as_dict(
        result.get("governing_state_classifier")
        or debug.get("governing_state_classifier")
    )
    if not classifier:
        classifier = classify_governing_state(
            payload=payload,
            primary=primary,
            result=result,
        )
    visible = _visible_outcome(payload)
    mismatch_class, reasons = _classification_kind(visible, classifier)
    return {
        "source": source,
        "location": location,
        "visible_outcome": visible,
        "classifier": classifier,
        "mismatch_class": mismatch_class,
        "reasons": reasons,
    }


def _discover_files(inputs: list[str], scan_root: Path) -> list[Path]:
    if inputs:
        return [Path(item).resolve() for item in inputs]
    if not scan_root.exists():
        return []
    return sorted(path for path in scan_root.rglob("*.json") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*", help="Optional JSON files to audit. Defaults to artifacts/verification/**/*.json.")
    parser.add_argument("--scan-root", default=str(DEFAULT_SCAN_ROOT), help="Directory to scan when no input files are given.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for the audit JSON artifact.")
    parser.add_argument("--fail-on-contract-violation", action="store_true", help="Opt-in failing mode for future gates.")
    args = parser.parse_args()

    scan_root = Path(args.scan_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    skipped: list[dict] = []
    for path in _discover_files(args.inputs, scan_root):
        try:
            data = _load_json(path)
        except Exception as exc:  # noqa: BLE001 - diagnostic scanner
            skipped.append({"source": str(path), "reason": f"json_load_failed:{type(exc).__name__}:{exc}"})
            continue
        payloads = _walk_payloads(data)
        if not payloads:
            payloads = [
                (location, _browser_snapshot_payload(snapshot))
                for location, snapshot in _walk_browser_snapshots(data)
            ]
        if not payloads:
            skipped.append({"source": str(path), "reason": "no_design_brain_payload_found"})
            continue
        for location, payload in payloads:
            entries.append(_audit_payload(str(path), location, payload))

    counts: dict[str, int] = {}
    for entry in entries:
        key = str(entry.get("mismatch_class") or "unknown")
        counts[key] = counts.get(key, 0) + 1

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    output_path = output_dir / f"governing_state_classifier_audit_{timestamp}.json"
    report = {
        "schema": "governing_state_classifier_audit.v1",
        "generated_at": timestamp,
        "non_failing_default": True,
        "checked_payload_count": len(entries),
        "skipped_count": len(skipped),
        "counts": counts,
        "entries": entries,
        "skipped": skipped,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(str(output_path))
    if args.fail_on_contract_violation and counts.get("contract violation", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
