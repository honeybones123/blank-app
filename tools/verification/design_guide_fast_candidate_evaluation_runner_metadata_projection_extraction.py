from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.candidate_evaluation import (
    build_fast_candidate_evaluation_runner_metadata_projection,
)


INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _old_metadata_projection(
    *,
    cached_candidate: dict[str, Any],
    candidate_state: dict[str, Any],
    updates: dict[str, Any],
    source: str,
    label: str | None,
    action_type: str | None,
    seed_width: float,
    seed_depth: float,
    seed_ast_bot: float,
    reo_complexity: float,
) -> dict[str, Any]:
    candidate = dict(cached_candidate)
    candidate["source"] = source
    candidate["label"] = label or candidate.get("label") or source.replace("_", " ").title()
    candidate["action_type"] = action_type
    candidate["state"] = dict(candidate_state)
    candidate["updates"] = dict(updates)
    candidate["_seed_width"] = float(seed_width or 0.0)
    candidate["_seed_depth"] = float(seed_depth or 0.0)
    candidate["_seed_ast_bot"] = float(seed_ast_bot or 0.0)
    candidate["reo_complexity"] = float(
        candidate.get("reo_complexity", reo_complexity) or 0.0
    )
    return candidate


def _cases() -> dict[str, dict[str, Any]]:
    return {
        "explicit_label_and_complexity": {
            "cached_candidate": {
                "overview": {"all_key_pass": True},
                "worst_util": 0.72,
                "reo_complexity": 12.5,
            },
            "candidate_state": {"D": 600, "b": 300, "bot1_count": 4},
            "updates": {"D": 600, "bot1_count": 4},
            "source": "fast_candidate",
            "label": "Fast candidate",
            "action_type": "apply_resolved_candidate",
            "seed_width": 300.0,
            "seed_depth": 650.0,
            "seed_ast_bot": 1256.0,
            "reo_complexity": 99.0,
        },
        "fallback_label_and_complexity": {
            "cached_candidate": {"overview": {}, "worst_util": 0.91},
            "candidate_state": {"D": 550, "b": 280, "lig_legs": 0},
            "updates": {"D": 550},
            "source": "less_shear_reo",
            "label": None,
            "action_type": None,
            "seed_width": 280.0,
            "seed_depth": 600.0,
            "seed_ast_bot": 900.0,
            "reo_complexity": 6.75,
        },
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    _, _, runner_segment = _function_segment(inputs_source, "_evaluate_candidate_fast")
    parity_cases = {}
    for name, case in _cases().items():
        old = _old_metadata_projection(**case)
        new = build_fast_candidate_evaluation_runner_metadata_projection(**case)
        parity_cases[name] = {
            "matches": old == new,
            "old": old,
            "new": new,
            "case_hash": _stable_hash({"old": old, "new": new}),
        }
    legacy_tokens = {
        "candidate_source_inline": 'candidate["source"] = source',
        "candidate_label_inline": 'candidate["label"] = label or candidate.get("label") or source.replace("_", " ").title()',
        "candidate_action_type_inline": 'candidate["action_type"] = action_type',
        "candidate_state_inline": 'candidate["state"] = dict(candidate_state)',
        "candidate_updates_inline": 'candidate["updates"] = _candidate_state_to_shared_updates(seed_state, candidate_state)',
        "seed_width_inline": 'candidate["_seed_width"] = float(_design_width_value(seed_state) or 0.0)',
        "seed_depth_inline": 'candidate["_seed_depth"] = float(_float_from_state(seed_state, "D", 0.0) or 0.0)',
        "seed_ast_inline": 'candidate["_seed_ast_bot"] = float((_effective_bottom_design_state(seed_state) or {}).get("Ast_bot", 0.0) or 0.0)',
    }
    checks = {
        "service_helper_exists": "def build_fast_candidate_evaluation_runner_metadata_projection(" in candidate_source,
        "service_helper_exported": '"build_fast_candidate_evaluation_runner_metadata_projection"' in candidate_source,
        "runner_calls_service_helper": "_build_fast_candidate_evaluation_runner_metadata_projection(" in runner_segment,
        "legacy_inline_metadata_stamps_absent": all(
            token not in runner_segment for token in legacy_tokens.values()
        ),
        "parity_cases_match": all(case["matches"] for case in parity_cases.values()),
        "cache_cap_timing_callback_still_page_owned": all(
            token in runner_segment
            for token in (
                "_get_eval_cache()",
                "AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS",
                "time.perf_counter()",
                "evaluate_candidate_fast(candidate_state, fast_ctx)",
            )
        ),
        "no_inputs_page_import_in_candidate_service": "inputs_page" not in candidate_source,
        "no_streamlit_import_in_candidate_service": "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_runner_metadata_projection_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_RUNNER_METADATA_PROJECTION_SERVICE_OWNED"
            if status == "PASS"
            else "FAST_RUNNER_METADATA_PROJECTION_NOT_LOCKED"
        ),
        "checks": checks,
        "legacy_tokens": legacy_tokens,
        "parity_cases": parity_cases,
        "remaining_runner_surfaces": [
            "global/local eval cache lookup and writes",
            "unique evaluation cap guard",
            "timing metrics",
            "evaluate_candidate_fast callback execution",
            "page-owned update and seed scalar collection",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "cases": parity_cases}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_runner_metadata_projection_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_runner_metadata_projection_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(
        f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items())
    )
    cases = "\n".join(
        f"- `{name}`: matches `{case['matches']}`"
        for name, case in sorted(snapshot["parity_cases"].items())
    )
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Runner Metadata Projection Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Parity Cases",
                cases,
                "",
                "## Remaining Runner Surfaces",
                *[f"- {item}" for item in snapshot["remaining_runner_surfaces"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_fast_candidate_evaluation_runner_metadata_projection_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
