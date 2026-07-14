"""Verify target-band refinement loop service handoff."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (  # noqa: E402
    build_target_band_refinement_payload_if_valid,
    diff_candidate_state_updates,
    resolve_candidate_target_band_distance,
    resolve_target_band_candidate_domains_for_updates,
    select_best_target_band_refinement_candidate,
    select_target_band_best_refinement_payload,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

TARGET_MIN = 0.85
TARGET_MAX = 1.0
FAIL_STATUS = "FAIL"
MODE_CONFIG = {"target_util_min": TARGET_MIN, "target_util_max": TARGET_MAX}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _goal_resolver(state: dict[str, Any]) -> str:
    return str((state or {}).get("design_optimisation_goal") or "balanced")


def _eval_from_state(state: dict[str, Any]) -> dict[str, Any]:
    util = float(state.get("util", 0.0) or 0.0)
    all_pass = bool(state.get("all_pass", True))
    status = "PASS" if all_pass else "FAIL"
    return {
        "state": dict(state),
        "overview": {
            "all_key_pass": all_pass,
            "worst_util": util,
            "governing_util": util,
            "utils": {"bending": util, "shear": util},
            "statuses": {"bending": status, "shear": status, "crack": "PASS", "deflection": "PASS"},
        },
        "worst_util": util,
    }


def _old_loop(
    *,
    candidate_states: list[dict[str, Any]],
    current_eval: dict[str, Any],
    current_state: dict[str, Any],
    current_distance: float,
    current_target_domains: list[str],
    attach_log: list[dict[str, Any]],
) -> dict[str, Any] | None:
    best_payload: dict[str, Any] | None = None
    for candidate_state in candidate_states:
        if bool(candidate_state.get("missing_eval", False)):
            continue
        candidate_eval = _eval_from_state(candidate_state)
        if candidate_eval is None:
            continue
        candidate_updates = diff_candidate_state_updates(current_state, candidate_state)
        if current_target_domains:
            candidate_target_domains = resolve_target_band_candidate_domains_for_updates(
                current_target_domains,
                candidate_updates,
            )
            attach_log.append({"state_id": candidate_state.get("id"), "domains": list(candidate_target_domains)})
            candidate_eval["target_domains_for_band"] = list(candidate_target_domains)
        payload = build_target_band_refinement_payload_if_valid(
            candidate_state=candidate_state,
            candidate_eval=candidate_eval,
            candidate_updates=candidate_updates,
            current_eval=current_eval,
            current_distance=current_distance,
            mode_config=MODE_CONFIG,
            spacing_envelope_fail=bool(candidate_state.get("spacing_fail", False)),
            default_target_min=TARGET_MIN,
            default_target_max=TARGET_MAX,
            fail_status=FAIL_STATUS,
            optimisation_goal_resolver=_goal_resolver,
        )
        if payload is None:
            continue
        best_payload = select_target_band_best_refinement_payload(best_payload, payload)
    return best_payload


def _new_loop(
    *,
    candidate_states: list[dict[str, Any]],
    current_eval: dict[str, Any],
    current_state: dict[str, Any],
    current_distance: float,
    current_target_domains: list[str],
    attach_log: list[dict[str, Any]],
) -> dict[str, Any] | None:
    def state_pack_fn(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def evaluator_fn(state: dict[str, Any], **_: Any) -> dict[str, Any] | None:
        if bool(state.get("missing_eval", False)):
            return None
        return _eval_from_state(state)

    def target_domain_attachment_fn(eval_obj: dict[str, Any], domains: list[str], _mode_config: dict[str, Any] | None) -> None:
        attach_log.append({"state_id": (eval_obj.get("state") or {}).get("id"), "domains": list(domains)})
        eval_obj["target_domains_for_band"] = list(domains)

    def spacing_fn(eval_obj: dict[str, Any]) -> bool:
        return bool((eval_obj.get("state") or {}).get("spacing_fail", False))

    return select_best_target_band_refinement_candidate(
        candidate_states=candidate_states,
        current_eval=current_eval,
        current_state=current_state,
        current_distance=current_distance,
        current_target_domains=current_target_domains,
        mode_config=MODE_CONFIG,
        state_pack_fn=state_pack_fn,
        evaluator_fn=evaluator_fn,
        target_domain_attachment_fn=target_domain_attachment_fn,
        spacing_envelope_fail_fn=spacing_fn,
        source="refinement_probe",
        label="Refinement probe",
        action_type="apply_refinement",
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )


def _normalised_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    eval_obj = dict(payload.get("eval") or {})
    state = dict(payload.get("state") or {})
    return {
        "state": state,
        "distance": payload.get("distance"),
        "updates": dict(payload.get("updates") or {}),
        "target_domains_for_band": list(eval_obj.get("target_domains_for_band") or []),
    }


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_eval = _eval_from_state({"id": "current", "util": 0.40, "all_pass": True})
    current_state = {"id": "current", "util": 0.40, "all_pass": True, "bot1_count": 5, "s_lig": 200}
    current_distance = resolve_candidate_target_band_distance(
        current_eval,
        MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )
    candidate_states = [
        {"id": "missing", "util": 0.80, "missing_eval": True, "bot1_count": 4, "s_lig": 200},
        {"id": "spacing", "util": 0.82, "spacing_fail": True, "bot1_count": 4, "s_lig": 200},
        {"id": "not_pass", "util": 0.84, "all_pass": False, "bot1_count": 4, "s_lig": 200},
        {"id": "valid_worse", "util": 0.70, "bot1_count": 4, "s_lig": 200},
        {"id": "valid_best", "util": 0.90, "bot1_count": 4, "s_lig": 250},
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for base_domains in ([], ["bending"], ["bending", "shear"]):
        old_log: list[dict[str, Any]] = []
        new_log: list[dict[str, Any]] = []
        old = _old_loop(
            candidate_states=candidate_states,
            current_eval=current_eval,
            current_state=current_state,
            current_distance=current_distance,
            current_target_domains=list(base_domains),
            attach_log=old_log,
        )
        new = _new_loop(
            candidate_states=candidate_states,
            current_eval=current_eval,
            current_state=current_state,
            current_distance=current_distance,
            current_target_domains=list(base_domains),
            attach_log=new_log,
        )
        row = {
            "base_domains": list(base_domains),
            "old": _normalised_payload(old),
            "new": _normalised_payload(new),
            "old_attach_log": old_log,
            "new_attach_log": new_log,
            "matches": _normalised_payload(old) == _normalised_payload(new) and old_log == new_log,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, helper = _function_segment(inputs_source, "_one_click_best_next_hop_improving_candidate")
    rows, mismatches = _case_rows()
    static_checks = {
        "service_present": "def select_best_target_band_refinement_candidate(" in candidate_source,
        "page_delegates_loop": "_select_best_target_band_refinement_candidate(" in helper,
        "page_keeps_context_build": "_build_auto_design_context(" in helper,
        "page_keeps_generator": "generate_compliant_refinement_candidates(" in helper,
        "page_injects_state_pack": "state_pack_fn=_build_canonical_design_state_pack" in helper,
        "page_injects_evaluator": "evaluator_fn=evaluate_candidate_full" in helper,
        "page_injects_attachment": "target_domain_attachment_fn=_one_click_attach_eval_target_domains" in helper,
        "page_injects_spacing_check": "spacing_envelope_fail_fn=_one_click_has_unresolved_spacing_envelope_fail" in helper,
        "old_inline_loop_removed": "for candidate_state in candidate_states:" not in helper
        and "evaluate_candidate_full(" not in helper,
    }
    forbidden_service_hits = [
        token
        for token in (
            "one_click",
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    static_checks["forbidden_service_hits"] = forbidden_service_hits
    status = "PASS"
    if mismatches or not all(value is True for key, value in static_checks.items() if key != "forbidden_service_hits") or forbidden_service_hits:
        status = "FAIL"
    return {
        "status": status,
        "surface": "target_band_refinement_loop_service_handoff",
        "inputs_segment": {"function": "_one_click_best_next_hop_improving_candidate", "start_line": start, "end_line": end},
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "static_checks": static_checks,
        "ownership": {
            "moved_to_candidate_evaluation": [
                "generated refinement state iteration",
                "candidate evaluation callback orchestration",
                "candidate update diff and target-domain merge use",
                "payload screening and best-payload selection",
            ],
            "remains_page_owned": [
                "auto-design context construction",
                "refinement candidate generation",
                "canonical state pack callback",
                "full candidate evaluator callback",
                "target-domain attachment callback",
                "spacing-envelope callback",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract or bound auto-design context construction and refinement candidate generation",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_refinement_loop_service_handoff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_refinement_loop_service_handoff_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Refinement Loop Service Handoff",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved the generated refinement candidate evaluation/selection loop into `design_brain.candidate_evaluation` with page callbacks injected.",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Parity", f"- Cases checked: `{payload['case_count']}`", f"- Mismatches: `{len(payload['mismatches'])}`", "", "## Remaining Page-Owned Logic"])
    for item in payload["ownership"]["remains_page_owned"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"]), "", f"JSON artifact: `{json_path}`"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_artifacts(payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
