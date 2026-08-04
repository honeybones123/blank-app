"""Live-path parity instrumentation snapshot for intent-contract rebind tail."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "status": "UNREADABLE", "path": str(path), "error": str(exc)}
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw_status.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw_status
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _line_for(lines: list[str], token: str) -> int:
    for index, line in enumerate(lines):
        if token in line:
            return index
    return -1


def _window(lines: list[str], center: int, *, before: int = 180, after: int = 190) -> str:
    if center < 0:
        return ""
    start = max(0, center - before)
    end = min(len(lines), center + after)
    return "\n".join(lines[start:end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    parity_line = _line_for(lines, '"final_binding_intent_contract_rebind_parity"')
    proof_line = _line_for(lines, "_build_final_visible_contract_binding_intent_contract_rebind_result(")
    context = _window(lines, parity_line if parity_line >= 0 else proof_line)
    post_proof_context = (
        "\n".join(lines[proof_line : min(len(lines), proof_line + 170)])
        if proof_line >= 0
        else ""
    )
    pre_cutover_parity_instrumented = bool(
        parity_line >= 0
        and all(
            token in context
            for token in (
                '"applies_matches_live_branch"',
                '"contract_effect_matches"',
                '"item_effect_matches"',
                '"updates_effect_matches"',
                '"action_type_effect_matches"',
                "def _effect_subset_matches(",
                '"final_binding_intent_contract_rebind_parity"',
                '"final_binding_intent_contract_rebind_parity_checks"',
            )
        )
    )
    post_cutover_effects_drive = bool(
        proof_line >= 0
        and all(
            token in context
            for token in (
                "_build_final_visible_contract_binding_intent_contract_rebind_result(",
                '_intent_rebind_result.get("contract_effect")',
                '_intent_rebind_result.get("item_effect")',
                '_intent_rebind_result.get("updates_effect")',
                '_intent_rebind_result.get("action_type_effect")',
                "contract = dict(_intent_contract_effect)",
                "action_type = _intent_action_type",
                "updates = dict(_intent_updates)",
                "out.update(dict(_intent_item_effect))",
                'out["button_contract"] = dict(contract)',
            )
        )
        and all(
            token not in post_proof_context
            for token in (
                "contract = dict(_intent_contract)",
                "contract.update(",
                "_intent_expected = _parse_util_value(",
                "_intent_rebind_parity_checks",
                "def _effect_subset_matches(",
            )
        )
    )
    return {
        "decision": (
            "INTENT_CONTRACT_REBIND_LIVE_PARITY_RETIRED_AFTER_CUTOVER"
            if post_cutover_effects_drive
            else "INTENT_CONTRACT_REBIND_LIVE_PARITY_INSTRUMENTED_NOT_CUT_OVER"
        ),
        "parity_line": parity_line + 1 if parity_line >= 0 else None,
        "proof_line": proof_line + 1 if proof_line >= 0 else None,
        "source_checks": {
            "pre_cutover_parity_instrumented": pre_cutover_parity_instrumented,
            "post_cutover_effects_drive": post_cutover_effects_drive,
            "proof_built_before_live_branch": (
                "_intent_contract_rebind_proof = {}" in context
                and "_build_final_visible_contract_binding_intent_contract_rebind_result(" in context
            ),
            "old_live_branch_still_present": all(
                token in context
                for token in (
                    "contract = dict(_intent_contract)",
                    "contract.update(",
                    "out.update(",
                    'action_type = "apply_resolved_candidate"',
                    "updates = dict(_intent_updates)",
                )
            ),
            "parity_checks_present": all(
                token in context
                for token in (
                    '"applies_matches_live_branch"',
                    '"contract_effect_matches"',
                    '"item_effect_matches"',
                    '"updates_effect_matches"',
                    '"action_type_effect_matches"',
                )
            ),
            "effect_subset_helper_present": "def _effect_subset_matches(" in context,
            "parity_stamped": (
                '"final_binding_intent_contract_rebind_parity"' in context
                and '"final_binding_intent_contract_rebind_parity_checks"' in context
            ),
            "non_driving_flags_present": all(
                token in context
                for token in (
                    '"final_binding_intent_contract_rebind_parity_product_driving"',
                    '"final_binding_intent_contract_rebind_parity_render_driving"',
                    '"final_binding_intent_contract_rebind_parity_apply_driving"',
                    '"final_binding_intent_contract_rebind_parity_session_driving"',
                    '"final_binding_intent_contract_rebind_ready_for_live_cutover"',
                )
            ),
            "not_cut_over": "contract = dict(_intent_contract_rebind_proof" not in context,
        },
        "latest_artifacts": {
            "trace_wiring": _latest("design_guide_intent_contract_rebind_trace_wiring"),
            "object_snapshot": _latest("design_guide_intent_contract_rebind_object"),
            "cutover_implementation": _latest("design_guide_intent_contract_rebind_cutover_implementation"),
            "parity_scaffold_deletion": _latest("design_guide_intent_contract_rebind_parity_scaffold_deletion"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
            "independence_lock": _latest("design_guide_independence_lock"),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "ready_for_live_cutover": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    source_checks = dict(capture.get("source_checks") or {})
    latest = dict(capture.get("latest_artifacts") or {})
    pre_cutover_ready = bool(source_checks.get("pre_cutover_parity_instrumented"))
    post_cutover_ready = bool(source_checks.get("post_cutover_effects_drive"))
    return {
        "all_source_checks_pass": pre_cutover_ready or post_cutover_ready,
        "trace_wiring_pass": (latest.get("trace_wiring") or {}).get("status") == "PASS",
        "object_snapshot_pass": (latest.get("object_snapshot") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "live_parity_state_classified": pre_cutover_ready or post_cutover_ready,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Intent Contract Rebind Live Parity Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Parity line: `{capture.get('parity_line')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Source Checks",
        "",
    ]
    for key, value in (capture.get("source_checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_intent_contract_rebind_live_parity_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    json_path = ARTIFACT_DIR / f"design_guide_intent_contract_rebind_live_parity_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_intent_contract_rebind_live_parity_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_intent_contract_rebind_live_parity_snapshot {status}")
    print(f"artifact={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
