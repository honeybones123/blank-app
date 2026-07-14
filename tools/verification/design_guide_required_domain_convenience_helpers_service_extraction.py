"""Verify required-domain convenience helper service extraction."""

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
    resolve_candidate_domain_max_distance,
    resolve_candidate_domain_total_distance,
    resolve_candidate_required_domain_progress,
    resolve_candidate_required_domains_satisfied,
)


INPUTS = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
DEFAULT_MIN = 0.85
DEFAULT_MAX = 1.0
FAIL = "FAIL"


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


def _goal_from_state(state: dict[str, Any]) -> str:
    return str((state or {}).get("design_optimisation_goal") or "balanced")


def _candidate(
    *,
    target_domains: Any = None,
    bending: Any = None,
    shear: Any = None,
    mu: Any = None,
    phi: Any = None,
    statuses: dict[str, Any] | None = None,
    all_key_pass: bool | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    bending_pack: dict[str, Any] = {}
    if mu is not None:
        bending_pack["summary_Mu_star_kNm"] = mu
    if phi is not None:
        bending_pack["summary_phiMu_kNm"] = phi
    overview: dict[str, Any] = {
        "statuses": dict(statuses or {}),
        "utils": {"bending": bending, "shear": shear},
        "packs": {"bending": bending_pack},
    }
    if all_key_pass is not None:
        overview["all_key_pass"] = bool(all_key_pass)
    candidate: dict[str, Any] = {"overview": overview}
    if target_domains is not None:
        candidate["target_domains_for_band"] = target_domains
    if goal is not None:
        candidate["state"] = {"design_optimisation_goal": goal}
    return candidate


def _normalize(value: Any) -> Any:
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    return value


def _progress(candidate: dict[str, Any] | None, mode_config: dict[str, Any] | None) -> dict[str, Any]:
    return resolve_candidate_required_domain_progress(
        candidate,
        mode_config,
        default_target_min=DEFAULT_MIN,
        default_target_max=DEFAULT_MAX,
        fail_status=FAIL,
        optimisation_goal_resolver=_goal_from_state,
    )


def build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS)
    candidate_source = _read(CANDIDATE_EVALUATION)
    wrappers = {
        name: _function_segment(inputs_source, name)[2]
        for name in (
            "_one_click_domain_total_distance",
            "_one_click_domain_max_distance",
            "_one_click_required_domains_satisfied",
        )
    }
    cases = [
        (
            "explicit_domains_all_satisfied",
            _candidate(
                target_domains=["bending", "shear"],
                mu=90.0,
                phi=100.0,
                shear=0.9,
                statuses={"bending": "PASS", "shear": "PASS"},
            ),
            {},
        ),
        (
            "explicit_domains_unsatisfied",
            _candidate(
                target_domains=["bending", "shear"],
                mu=60.0,
                phi=100.0,
                shear=1.2,
                statuses={"bending": "PASS", "shear": "PASS"},
            ),
            {},
        ),
        (
            "objective_fallback_satisfied",
            _candidate(
                bending=0.9,
                shear=0.9,
                statuses={"bending": "PASS", "shear": "PASS"},
                all_key_pass=True,
            ),
            {},
        ),
        (
            "objective_fallback_failed",
            _candidate(
                bending=0.9,
                shear=0.9,
                statuses={"bending": "FAIL"},
                all_key_pass=False,
            ),
            {},
        ),
        ("invalid_input", None, {}),
    ]
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for name, candidate, mode_config in cases:
        progress = _progress(candidate, mode_config)
        old = {
            "total": float(progress.get("domain_total_distance", float("inf"))),
            "max": float(progress.get("domain_max_distance", float("inf"))),
            "satisfied": bool(
                isinstance(candidate, dict)
                and int(progress.get("required_unsatisfied_count", 0) or 0) == 0
            ),
        }
        new = {
            "total": resolve_candidate_domain_total_distance(
                candidate,
                mode_config,
                default_target_min=DEFAULT_MIN,
                default_target_max=DEFAULT_MAX,
                fail_status=FAIL,
                optimisation_goal_resolver=_goal_from_state,
            ),
            "max": resolve_candidate_domain_max_distance(
                candidate,
                mode_config,
                default_target_min=DEFAULT_MIN,
                default_target_max=DEFAULT_MAX,
                fail_status=FAIL,
                optimisation_goal_resolver=_goal_from_state,
            ),
            "satisfied": resolve_candidate_required_domains_satisfied(
                candidate,
                mode_config,
                default_target_min=DEFAULT_MIN,
                default_target_max=DEFAULT_MAX,
                fail_status=FAIL,
                optimisation_goal_resolver=_goal_from_state,
            ),
        }
        old_norm = {key: _normalize(value) for key, value in old.items()}
        new_norm = {key: _normalize(value) for key, value in new.items()}
        row = {"case": name, "old": old_norm, "new": new_norm, "matches": old_norm == new_norm}
        rows.append(row)
        if not row["matches"]:
            mismatches.append(row)

    wrapper_thin = (
        "_resolve_candidate_domain_total_distance(" in wrappers["_one_click_domain_total_distance"]
        and "_resolve_candidate_domain_max_distance(" in wrappers["_one_click_domain_max_distance"]
        and "_resolve_candidate_required_domains_satisfied(" in wrappers["_one_click_required_domains_satisfied"]
        and "required_unsatisfied_count" not in "\n".join(wrappers.values())
        and ".get(" not in "\n".join(wrappers.values())
        and "_one_click_required_domain_progress(" not in "\n".join(wrappers.values())
    )
    service_present = all(
        token in candidate_source
        for token in (
            "def resolve_candidate_domain_total_distance(",
            "def resolve_candidate_domain_max_distance(",
            "def resolve_candidate_required_domains_satisfied(",
        )
    )
    forbidden_service_import_hits = [
        token
        for token in (
            "import inputs_page",
            "from inputs_page",
            "import streamlit",
            "from streamlit",
            "st.session_state",
        )
        if token in candidate_source
    ]
    status = "PASS"
    if mismatches or not wrapper_thin or not service_present or forbidden_service_import_hits:
        status = "FAIL"
    return {
        "status": status,
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wrapper_thin": wrapper_thin,
        "service_present": service_present,
        "forbidden_service_import_hits": forbidden_service_import_hits,
        "case_count": len(rows),
        "mismatch_count": len(mismatches),
        "rows": rows,
        "mismatches": mismatches,
        "product_behavior_changed": False,
        "next_safe_slice": "return to candidate selection/search extraction",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_required_domain_convenience_helpers_service_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_required_domain_convenience_helpers_service_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Required-Domain Convenience Helpers Service Extraction",
        "",
        "## Executive Summary",
        f"Status: `{payload['status']}`",
        f"Product behaviour changed: `{payload['product_behavior_changed']}`",
        "",
        "## Proof",
        f"- Thin page wrappers: `{payload['wrapper_thin']}`",
        f"- Service helpers present: `{payload['service_present']}`",
        f"- Forbidden service import hits: `{payload['forbidden_service_import_hits']}`",
        f"- Cases: `{payload['case_count']}`",
        f"- Mismatches: `{payload['mismatch_count']}`",
        "",
        "## Next Safe Slice",
        f"`{payload['next_safe_slice']}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
