"""Diagnostic audit for dormant governing-family adapters.

Phase 2 audits only `SHEAR_FAIL_GOVERNS`. The tool invokes the adapter against
synthetic and optional artifact-derived payloads, then fails if the adapter is
missing, generic-placeholder only, product-routing enabled, UI/session-coupled,
or capable of changing product decisions.
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

from design_brain.families import FamilyStrategyContext
from design_brain.families.registry import GOVERNING_FAMILY_REGISTRY, family_strategy_for
from design_brain.families.shear_fail import ADAPTER_VERSION


OUTPUT_DIR = ROOT / "artifacts" / "verification"
REQUIRED_FAMILIES = (
    "BENDING_FAIL_GOVERNS",
    "SHEAR_FAIL_GOVERNS",
    "COMBINED_BENDING_SHEAR_FAIL",
    "BENDING_OVERDESIGN_GOVERNS",
    "SHEAR_OVERDESIGN_GOVERNS",
    "COMBINED_OVERDESIGN",
    "MIN_BENDING_REO_GOVERNS",
    "MIN_SHEAR_REO_GOVERNS",
    "GEOMETRY_DETAILING_GOVERNS",
    "SERVICEABILITY_GOVERNS",
    "LOCKED_NO_REPAIR",
    "TARGET_BAND_REACHED",
    "EXACT_STOP_PROVEN",
)
REQUIRED_METHODS = (
    "classify",
    "generate_candidates",
    "rank_candidates",
    "build_evidence",
    "publish",
    "get_cta_rule",
)
FORBIDDEN_SHEAR_ADAPTER_TOKENS = (
    "import streamlit",
    "from streamlit",
    "st.session_state",
    "import inputs_page",
    "from inputs_page",
    "_queue_primary_design_guide_button_action",
    "_record_rendered_design_guide_primary_apply_payload",
    "handle_apply_buttons",
    "apply_recommendation_result",
    "resolve_design_guide_decision(",
    "resolve_design_guide_card(",
    "enforce_design_brain_publication_contract(",
)


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, list) else []


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _walk_payloads(value: Any, *, path: str = "$") -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        if "guidance_items" in value or "debug_trace" in value or "design_brain_result" in value:
            found.append((path, dict(value)))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_walk_payloads(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_payloads(child, path=f"{path}[{index}]"))
    return found


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
        next_positions = [match.end() + item.start() for item in next_starts if item]
        end = min(next_positions) if next_positions else min(len(compact), match.end() + 280)
        segment = compact[match.start() : end]
        util_match = re.search(r"Utilisation\s+([-+]?\d+(?:\.\d+)?)", segment, flags=re.IGNORECASE)
        if util_match:
            utils[family] = float(util_match.group(1))
        for status in ("FAIL", "NEAR LIMIT", "PASS", "CAPACITY", "NOT RUN", "INFO"):
            if re.search(rf"\b{re.escape(status)}\b", segment, flags=re.IGNORECASE):
                statuses[family] = status
                break
    return statuses, utils


def _visible_title_from_body(body_text: str) -> str:
    known_titles = [
        "Shear capacity is low",
        "Shear repair blocked",
        "Bending and shear capacity are low",
        "Design is efficient",
        "Shear cleanup blocked",
    ]
    lower = body_text.lower()
    for title in known_titles:
        if title.lower() in lower:
            return title
    return ""


def _browser_snapshot_payload(snapshot: dict) -> dict | None:
    body_text = str(snapshot.get("body_text") or snapshot.get("main_text_sample") or "")
    if "Design Guide" not in body_text or "Shear" not in body_text:
        return None
    statuses, utils = _status_and_util_from_body(body_text)
    if not statuses and not utils:
        return None
    title = _visible_title_from_body(body_text)
    buttons = _as_list(snapshot.get("buttons"))
    cta_enabled = False
    for button in buttons:
        row = _as_dict(button)
        text = str(row.get("text") or "")
        if "Run one-click auto design" in text or text.startswith("Apply"):
            cta_enabled = not bool(row.get("disabled"))
            break
    item = {
        "title_main": title,
        "title": title,
        "family": "shear" if "shear" in title.lower() else "general",
        "check_key": "shear" if "shear" in title.lower() else "general",
        "status": "FAIL" if statuses.get("shear") == "FAIL" else ("PASS" if "efficient" in title.lower() else ""),
        "guidance_intent": "required_fix" if statuses.get("shear") == "FAIL" else "already_efficient",
        "button_contract": {
            "enabled": cta_enabled,
            "actionable": cta_enabled,
            "action_type": "apply_resolved_candidate" if cta_enabled else None,
            "updates": {"browser_visible_cta": True} if cta_enabled else {},
        },
    }
    return {
        "guidance_items": [item],
        "debug_trace": {
            "overview": {
                "statuses": statuses,
                "utils": utils,
                "fail_keys": [family for family, status in statuses.items() if status == "FAIL"],
                "any_fail": any(status == "FAIL" for status in statuses.values()),
            },
            "button_contract_enabled": cta_enabled,
        },
        "browser_snapshot_source": True,
    }


def _walk_browser_snapshots(value: Any, *, path: str = "$") -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        payload = _browser_snapshot_payload(value)
        if payload is not None:
            found.append((path, payload))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_walk_browser_snapshots(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                found.extend(_walk_browser_snapshots(child, path=f"{path}[{index}]"))
    return found


def _synthetic_shear_fail_payload() -> dict:
    evidence = {
        "active_failures": ["shear"],
        "family_status_current": {"shear": {"status": "FAIL", "util": 1.35}},
        "active_fail_repair_candidate_rows": [
            {
                "candidate_id": "synthetic_shear_repair_spacing_step",
                "family": "shear",
                "title": "Shear capacity is low",
                "updates": {"s_lig": 150},
                "safe_executor_backed": True,
                "preview_pass": True,
                "preview_util": 0.94,
            }
        ],
        "repair_search_ran": True,
        "repair_search_exhaustive": False,
        "selected_candidate_id": "synthetic_shear_repair_spacing_step",
        "selected_candidate_updates": {"s_lig": 150},
        "selected_candidate_title": "Shear capacity is low",
        "selected_candidate_util": 0.94,
    }
    return {
        "guidance_items": [
            {
                "title_main": "Shear capacity is low",
                "title": "Shear capacity is low",
                "family": "shear",
                "check_key": "shear",
                "status": "FAIL",
                "guidance_intent": "required_fix",
                "candidate_search_evidence": evidence,
                "button_contract": {
                    "enabled": True,
                    "actionable": True,
                    "action_type": "apply_resolved_candidate",
                    "family": "shear",
                    "updates": {"s_lig": 150},
                    "preview_pass": True,
                },
            }
        ],
        "debug_trace": {
            "overview": {
                "statuses": {"shear": "FAIL", "bending": "PASS"},
                "utils": {"shear": 1.35, "bending": 0.82},
                "fail_keys": ["shear"],
                "any_fail": True,
            },
            "candidate_search_evidence": evidence,
        },
    }


def _context_from_payload(payload: dict) -> FamilyStrategyContext:
    debug = _as_dict(payload.get("debug_trace"))
    items = _as_list(payload.get("guidance_items"))
    primary = dict(items[0]) if items and isinstance(items[0], dict) else {}
    evidence = _as_dict(
        primary.get("candidate_search_evidence")
        or _as_dict(primary.get("action_payload")).get("candidate_search_evidence")
        or _as_dict(primary.get("resolved_candidate")).get("candidate_search_evidence")
        or debug.get("candidate_search_evidence")
    )
    return FamilyStrategyContext(
        governing_state="SHEAR_FAIL_GOVERNS",
        payload=payload,
        primary=primary,
        summary=_as_dict(debug.get("overview")),
        evidence=evidence,
        debug=debug,
    )


def _invoke_adapter(payload: dict, *, source: str, location: str) -> dict:
    strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
    if strategy is None:
        raise RuntimeError("SHEAR_FAIL_GOVERNS adapter not registered")
    context = _context_from_payload(payload)
    classification = strategy.classify(context)
    candidates = strategy.generate_candidates(context)
    ranking = strategy.rank_candidates(context, candidates)
    evidence = strategy.build_evidence(context, ranking)
    publication = strategy.publish(context, evidence)
    cta = strategy.get_cta_rule(context, evidence)  # type: ignore[arg-type]
    return {
        "source": source,
        "location": location,
        "classification": classification,
        "candidates": candidates,
        "ranking": ranking,
        "evidence": evidence,
        "publication": publication,
        "cta": cta,
    }


def _method_completeness(strategy: Any) -> dict:
    return {
        method: callable(getattr(strategy, method, None))
        for method in REQUIRED_METHODS
    }


def _static_safety_check() -> dict:
    path = ROOT / "design_brain" / "families" / "shear_fail.py"
    text = path.read_text(encoding="utf-8")
    hits = [token for token in FORBIDDEN_SHEAR_ADAPTER_TOKENS if token in text]
    return {
        "path": str(path),
        "forbidden_token_hits": hits,
        "ok": not hits,
    }


def _other_families_dormant() -> dict:
    context = FamilyStrategyContext(governing_state="BENDING_FAIL_GOVERNS")
    non_dormant = []
    for state, strategy_type in GOVERNING_FAMILY_REGISTRY.items():
        if state == "SHEAR_FAIL_GOVERNS":
            continue
        strategy = strategy_type()
        result = strategy.generate_candidates(context)
        if result.get("reason") != "family_strategy_shell_only" or result.get("product_routing_enabled") is not False:
            non_dormant.append(state)
    return {
        "checked_count": len(GOVERNING_FAMILY_REGISTRY) - 1,
        "non_dormant_families": non_dormant,
        "ok": not non_dormant,
    }


def _collect_payloads(inputs: list[str]) -> tuple[list[tuple[str, str, dict]], list[dict]]:
    payloads: list[tuple[str, str, dict]] = [("synthetic", "$.synthetic_shear_fail", _synthetic_shear_fail_payload())]
    skipped: list[dict] = []
    for item in inputs:
        path = Path(item).resolve()
        try:
            data = _load_json(path)
        except Exception as exc:  # noqa: BLE001 - diagnostic tool
            skipped.append({"source": str(path), "reason": f"json_load_failed:{type(exc).__name__}:{exc}"})
            continue
        found = _walk_payloads(data)
        if not found:
            found = _walk_browser_snapshots(data)
        if not found:
            skipped.append({"source": str(path), "reason": "no_design_brain_or_browser_payload_found"})
            continue
        for location, payload in found:
            payloads.append((str(path), location, payload))
    return payloads, skipped


def _evaluate_checks(entries: list[dict]) -> dict:
    failures: list[str] = []
    strategy = family_strategy_for("SHEAR_FAIL_GOVERNS")
    if strategy is None:
        failures.append("adapter_not_registered")
        methods = {method: False for method in REQUIRED_METHODS}
    else:
        methods = _method_completeness(strategy)
        for method, present in methods.items():
            if not present:
                failures.append(f"required_method_missing:{method}")
    registry_missing = [state for state in REQUIRED_FAMILIES if state not in GOVERNING_FAMILY_REGISTRY]
    if registry_missing:
        failures.append(f"registry_missing:{','.join(registry_missing)}")
    static_safety = _static_safety_check()
    if not static_safety["ok"]:
        failures.append("adapter_static_forbidden_tokens")
    dormant = _other_families_dormant()
    if not dormant["ok"]:
        failures.append("other_family_shells_not_dormant")
    for entry in entries:
        for stage in ("classification", "candidates", "ranking", "evidence", "publication", "cta"):
            result = _as_dict(entry.get(stage))
            if result.get("product_routing_enabled") is not False:
                failures.append(f"{entry.get('source')}:{stage}:product_routing_enabled_not_false")
            if result.get("read_only") is not True:
                failures.append(f"{entry.get('source')}:{stage}:not_read_only")
            if result.get("reason") == "family_strategy_shell_only":
                failures.append(f"{entry.get('source')}:{stage}:generic_placeholder_returned")
            if result.get("mutates_product_state"):
                failures.append(f"{entry.get('source')}:{stage}:mutates_product_state")
            if result.get("calls_ui_or_session_state"):
                failures.append(f"{entry.get('source')}:{stage}:calls_ui_or_session_state")
            if result.get("changes_candidate_selection"):
                failures.append(f"{entry.get('source')}:{stage}:changes_candidate_selection")
            if result.get("changes_publication"):
                failures.append(f"{entry.get('source')}:{stage}:changes_publication")
            if result.get("creates_executable_cta"):
                failures.append(f"{entry.get('source')}:{stage}:creates_executable_cta")
    return {
        "ok": not failures,
        "failures": failures,
        "method_completeness": methods,
        "registry_count": len(GOVERNING_FAMILY_REGISTRY),
        "registry_missing": registry_missing,
        "static_safety": static_safety,
        "other_families_dormant": dormant,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="*", help="Optional verifier JSON artifacts to audit in addition to synthetic shear fail.")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    payloads, skipped = _collect_payloads(args.inputs)
    entries = []
    for source, location, payload in payloads:
        entries.append(_invoke_adapter(payload, source=source, location=location))
    checks = _evaluate_checks(entries)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"shear_fail_family_adapter_audit_{timestamp}.json"
    report = {
        "schema": "governing_family_adapter_audit.v1",
        "phase": "Family Strategy Program - Phase 2",
        "adapter": "SHEAR_FAIL_GOVERNS",
        "adapter_version": ADAPTER_VERSION,
        "generated_at": timestamp,
        "product_routing_enabled": False,
        "entry_count": len(entries),
        "skipped": skipped,
        "checks": checks,
        "entries": entries,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0 if checks["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
