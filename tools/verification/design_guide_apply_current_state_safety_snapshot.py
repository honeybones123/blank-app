from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ROUTE_COORDINATORS = ROOT / "inputs_page_route_coordinators.py"
APP_CONTRACT_BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
ARTIFACTS_VERIFICATION = ROOT / "artifacts" / "verification"
ARTIFACTS_AUDITS = ROOT / "artifacts" / "audits"


def _line_number(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def _function_body(text: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    bodies: list[str] = []
    for match in matches:
        next_match = re.search(r"^def\s+\w+\(", text[match.end() :], re.MULTILINE)
        if not next_match:
            bodies.append(text[match.start() :])
        else:
            bodies.append(text[match.start() : match.end() + next_match.start()])
    if name == "_apply_resolved_candidate_payload":
        for body in bodies:
            if '_set_shared_updates(updates, source="guidance:apply_resolved_candidate")' in body:
                return body
    if name == "_build_design_guide_primary_apply_payload":
        for body in bodies:
            if "_design_guide_apply_updates_current_state_guard(" in body:
                return body
    return bodies[0]


def main() -> int:
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (INPUTS_PAGE, ROUTE_COORDINATORS, APP_CONTRACT_BRIDGE)
        if path.exists()
    )
    text += "\n" + (ROOT / "inputs_page_modules" / "apply_payload.py").read_text(
        encoding="utf-8", errors="replace"
    )
    text += "\n" + (ROOT / "inputs_page_modules" / "design_guide" / "primary_apply_payload.py").read_text(
        encoding="utf-8", errors="replace"
    )
    helper_body = _function_body(text, "_design_guide_apply_updates_current_state_guard")
    payload_body = _function_body(text, "_build_design_guide_primary_apply_payload")
    apply_body = _function_body(text, "apply_resolved_candidate_payload")
    authoritative_apply_route = _function_body(
        (ROOT / "inputs_page_route_coordinators.py").read_text(
            encoding="utf-8", errors="replace"
        ),
        "_execute_authoritative_apply_current_coordinator",
    )

    commit_guard_needles = (
        "current_apply_guard = _design_guide_apply_updates_current_state_guard",
        "current_apply_guard = legacy_page._design_guide_apply_updates_current_state_guard",
    )
    commit_guard_pos = min(
        (pos for needle in commit_guard_needles for pos in [apply_body.find(needle)] if pos >= 0),
        default=-1,
    )
    commit_pos = apply_body.find('_set_shared_updates(updates, source="guidance:apply_resolved_candidate")')

    checks = {
        "helper_exists": bool(helper_body),
        "helper_uses_evaluate_candidate_full": "evaluate_candidate_full(" in helper_body,
        "helper_blocks_noop_updates": "candidate_updates_already_match_current_state" in helper_body,
        "helper_blocks_explicit_fail": "current_state_apply_preview_has_fail_status" in helper_body,
        "helper_blocks_any_fail": "current_state_apply_preview_any_fail" in helper_body,
        "payload_builder_uses_guard": "current_state_apply_guard = _design_guide_apply_updates_current_state_guard" in payload_body,
        "payload_builder_refuses_failed_guard": 'current_state_apply_guard.get("pass")' in payload_body and "return {}" in payload_body,
        "apply_commit_uses_guard": commit_guard_pos >= 0,
        "apply_commit_guard_before_shared_update": commit_guard_pos >= 0 and commit_pos >= 0 and commit_guard_pos < commit_pos,
        "apply_commit_blocks_failed_guard": "current_state_apply_preview_blocked" in apply_body,
        # The legacy session payload key is retained only as a compatibility
        # constant.  The authoritative result store now owns the payload and
        # is cleared by the application-layer Apply command after dispatch.
        "legacy_payload_key_not_used_as_authority": text.count(
            "DESIGN_GUIDE_PRIMARY_APPLY_PAYLOAD_KEY"
        ) <= 1,
        "authoritative_result_cleared_after_dispatch": (
            "AuthoritativeDesignResultStore(st.session_state).clear()" in authoritative_apply_route
            and "if command.status in {\"dispatch_ok\", \"rerun_required\"}" in authoritative_apply_route
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "locations": {
            "guard_helper_line": _line_number(text, "def _design_guide_apply_updates_current_state_guard"),
            "payload_builder_guard_line": _line_number(text, "current_state_apply_guard = _design_guide_apply_updates_current_state_guard"),
            "apply_commit_guard_line": min(
                (
                    line
                    for needle in commit_guard_needles
                    for line in [_line_number(text, needle)]
                    if line is not None
                ),
                default=None,
            ),
            "shared_update_commit_line": _line_number(text, '_set_shared_updates(updates, source="guidance:apply_resolved_candidate")'),
            "authoritative_result_clear_line": _line_number(
                authoritative_apply_route,
                "AuthoritativeDesignResultStore(st.session_state).clear()",
            ),
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"design_guide_apply_current_state_safety_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"design_guide_apply_current_state_safety_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report_lines = [
        "# Design Guide Apply Current-State Safety Snapshot",
        "",
        f"Status: `{status}`",
        "",
        "## Checks",
    ]
    for key, value in checks.items():
        report_lines.append(f"- `{key}`: `{bool(value)}`")
    report_lines.extend(
        [
            "",
            "## Locations",
        ]
    )
    for key, value in payload["locations"].items():
        report_lines.append(f"- `{key}`: `{value}`")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
