"""Verify target-band domain attachment policy extraction."""

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
    resolve_candidate_target_domain_needing_work,
    resolve_target_band_eval_domain_attachment,
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


def _eval(
    *,
    bending: float,
    shear: float,
    bending_status: str = "PASS",
    shear_status: str = "PASS",
) -> dict[str, Any]:
    return {
        "state": {"design_optimisation_goal": "balanced"},
        "overview": {
            "all_key_pass": bending_status == "PASS" and shear_status == "PASS",
            "worst_util": max(float(bending), float(shear)),
            "governing_util": max(float(bending), float(shear)),
            "utils": {"bending": float(bending), "shear": float(shear)},
            "statuses": {"bending": bending_status, "shear": shear_status, "crack": "PASS", "deflection": "PASS"},
        },
        "worst_util": max(float(bending), float(shear)),
    }


def _old_attachment(
    eval_obj: dict[str, Any] | None,
    target_domains_for_band: Any,
    *,
    bending_demand_negligible: bool,
    shear_demand_negligible: bool,
) -> dict[str, Any]:
    if not isinstance(eval_obj, dict):
        return {"target_domains_for_band": [], "target_domain_for_band": None, "clear": True}
    raw_domains = [domain for domain in ("bending", "shear") if domain in set(target_domains_for_band or [])]
    overview = dict(eval_obj.get("overview") or {})
    statuses = dict(overview.get("statuses") or {})

    def domain_relevant(domain: str) -> bool:
        status = str(statuses.get(domain) or "").strip().upper()
        if status == "FAIL":
            return True
        if domain == "shear":
            return not bool(shear_demand_negligible)
        if domain == "bending":
            return not bool(bending_demand_negligible)
        return True

    domains = [domain for domain in raw_domains if domain_relevant(domain)]
    if not domains:
        return {"target_domains_for_band": [], "target_domain_for_band": None, "clear": True}
    candidate = dict(eval_obj)
    candidate["target_domains_for_band"] = domains
    work_domain = resolve_candidate_target_domain_needing_work(
        candidate,
        MODE_CONFIG,
        default_target_min=TARGET_MIN,
        default_target_max=TARGET_MAX,
        fail_status=FAIL_STATUS,
        optimisation_goal_resolver=_goal_resolver,
    )
    return {
        "target_domains_for_band": list(domains),
        "target_domain_for_band": str(work_domain or "") or None,
        "clear": False,
    }


def _case_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        ("both_relevant_bending_needs_work", _eval(bending=0.70, shear=0.93), ["bending", "shear"], False, False),
        ("negligible_shear_removed", _eval(bending=0.70, shear=0.93), ["bending", "shear"], False, True),
        ("fail_status_keeps_negligible_shear", _eval(bending=0.95, shear=1.2, shear_status="FAIL"), ["shear"], False, True),
        ("all_domains_negligible_clear", _eval(bending=0.90, shear=0.93), ["bending", "shear"], True, True),
        ("shear_order_tie_wins_work_domain", _eval(bending=0.70, shear=0.70), ["bending", "shear"], False, False),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, eval_obj, target_domains, bending_negligible, shear_negligible in cases:
        old = _old_attachment(
            eval_obj,
            target_domains,
            bending_demand_negligible=bending_negligible,
            shear_demand_negligible=shear_negligible,
        )
        new = resolve_target_band_eval_domain_attachment(
            eval_obj,
            target_domains,
            MODE_CONFIG,
            bending_demand_negligible=bending_negligible,
            shear_demand_negligible=shear_negligible,
            default_target_min=TARGET_MIN,
            default_target_max=TARGET_MAX,
            fail_status=FAIL_STATUS,
            optimisation_goal_resolver=_goal_resolver,
        )
        row = {
            "case": name,
            "old": old,
            "new": new,
            "matches": old == new,
        }
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)
    return rows, mismatches


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    start, end, attach_helper = _function_segment(inputs_source, "_one_click_attach_eval_target_domains")
    _, _, work_domain_wrapper = _function_segment(inputs_source, "_candidate_target_domain_needing_work")
    rows, mismatches = _case_rows()
    static_checks = {
        "attachment_service_present": "def resolve_target_band_eval_domain_attachment(" in candidate_source,
        "work_domain_service_present": "def resolve_candidate_target_domain_needing_work(" in candidate_source,
        "page_attachment_delegates": "_resolve_target_band_eval_domain_attachment(" in attach_helper,
        "page_supplies_demand_booleans": "_bending_demands_negligible(actions)" in attach_helper
        and "_shear_demands_negligible(actions)" in attach_helper,
        "page_action_context_retained": "_build_design_actions_context_isolated(" in attach_helper,
        "inline_domain_relevant_removed": "def _domain_relevant(" not in attach_helper,
        "inline_work_domain_scoring_removed": "scored: list[tuple" not in work_domain_wrapper,
        "work_domain_wrapper_delegates": "_resolve_candidate_target_domain_needing_work(" in work_domain_wrapper,
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
        "surface": "target_band_domain_attachment_policy",
        "inputs_segment": {"function": "_one_click_attach_eval_target_domains", "start_line": start, "end_line": end},
        "case_count": len(rows),
        "parity_rows": rows,
        "mismatches": mismatches,
        "static_checks": static_checks,
        "ownership": {
            "moved_to_candidate_evaluation": [
                "domain relevance from status plus demand-negligible flags",
                "target-domain clear/attach projection",
                "target-domain needing-work selection",
            ],
            "remains_page_owned": [
                "isolated design-action context construction",
                "bending/shear negligible demand calculation",
                "in-place mutation of eval object for existing page callsites",
            ],
        },
        "product_behavior_changed": False,
        "next_safe_slice": "generator/evaluator handoff proof for _one_click_best_next_hop_improving_candidate",
    }


def write_artifacts(payload: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_target_band_domain_attachment_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_target_band_domain_attachment_service_extraction_{stamp}.md"
    payload["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Target-Band Domain Attachment Service Extraction",
        "",
        f"## Summary: {payload['status']}",
        "",
        "Moved demand-aware target-domain attachment policy into `design_brain.candidate_evaluation`.",
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
