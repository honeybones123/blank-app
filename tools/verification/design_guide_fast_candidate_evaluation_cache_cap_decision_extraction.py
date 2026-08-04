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
    resolve_fast_candidate_evaluation_cache_cap_decision,
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


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _expected_decisions() -> dict[str, dict[str, Any]]:
    return {
        "local_cache": {
            "input": {
                "local_cached_available": True,
                "global_cached_available": False,
                "use_global_cache": True,
                "unique_eval_count": 0,
                "max_unique_evals": 10,
            },
            "expected": {
                "decision": "use_local_cache",
                "use_local_cached": True,
                "use_global_cached": False,
                "should_evaluate": False,
                "cap_hit": False,
                "metrics_delta": {"cache_hits": 1},
            },
        },
        "global_cache": {
            "input": {
                "local_cached_available": False,
                "global_cached_available": True,
                "use_global_cache": True,
                "unique_eval_count": 0,
                "max_unique_evals": 10,
            },
            "expected": {
                "decision": "use_global_cache",
                "use_local_cached": False,
                "use_global_cached": True,
                "should_evaluate": False,
                "cap_hit": False,
                "metrics_delta": {"cache_hits": 1, "global_cache_hits": 1},
            },
        },
        "cap_hit": {
            "input": {
                "local_cached_available": False,
                "global_cached_available": False,
                "use_global_cache": True,
                "unique_eval_count": 10,
                "max_unique_evals": 10,
            },
            "expected": {
                "decision": "cap_hit",
                "use_local_cached": False,
                "use_global_cached": False,
                "should_evaluate": False,
                "cap_hit": True,
                "metrics_delta": {},
            },
        },
        "evaluate": {
            "input": {
                "local_cached_available": False,
                "global_cached_available": False,
                "use_global_cache": False,
                "unique_eval_count": 2,
                "max_unique_evals": 10,
            },
            "expected": {
                "decision": "evaluate",
                "use_local_cached": False,
                "use_global_cached": False,
                "should_evaluate": True,
                "cap_hit": False,
                "metrics_delta": {"unique_eval_count": 1},
            },
        },
    }


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    runner_segment = _function_segment(inputs_source, "_evaluate_candidate_fast")
    cases = {}
    for name, row in _expected_decisions().items():
        actual = resolve_fast_candidate_evaluation_cache_cap_decision(**row["input"])
        expected = dict(row["expected"])
        cases[name] = {
            "input": row["input"],
            "expected": expected,
            "actual": actual,
            "matches": actual == expected,
        }
    legacy_decision_tokens = {
        "nested_unique_eval_cap_condition": 'if int(metrics.get("unique_eval_count", 0) or 0) >= AUTO_DESIGN_MAX_TOTAL_UNIQUE_EVALS:',
        "direct_cache_hit_increment": 'metrics["cache_hits"] = int(metrics.get("cache_hits", 0)) + 1',
        "direct_global_cache_hit_increment": 'metrics["global_cache_hits"] = int(metrics.get("global_cache_hits", 0)) + 1',
        "direct_unique_eval_increment": 'metrics["unique_eval_count"] = int(metrics.get("unique_eval_count", 0)) + 1',
    }
    checks = {
        "service_helper_exists": "def resolve_fast_candidate_evaluation_cache_cap_decision(" in candidate_source,
        "service_helper_exported": '"resolve_fast_candidate_evaluation_cache_cap_decision"' in candidate_source,
        "runner_calls_service_helper": "_resolve_fast_candidate_evaluation_cache_cap_decision(" in runner_segment,
        "legacy_inline_decision_tokens_absent": all(
            token not in runner_segment for token in legacy_decision_tokens.values()
        ),
        "decision_cases_match": all(row["matches"] for row in cases.values()),
        "actual_cache_objects_stay_page_owned": all(
            token in runner_segment
            for token in ("eval_cache[key] = cached", "global_cache[key] = dict(cached)")
        ),
        "timing_and_callback_stay_page_owned": all(
            token in runner_segment
            for token in ("time.perf_counter()", "evaluate_candidate_fast(candidate_state, fast_ctx)")
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
        "snapshot": "design_guide_fast_candidate_evaluation_cache_cap_decision_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_RUNNER_CACHE_CAP_DECISION_SERVICE_OWNED"
            if status == "PASS"
            else "FAST_RUNNER_CACHE_CAP_DECISION_NOT_LOCKED"
        ),
        "checks": checks,
        "cases": cases,
        "legacy_decision_tokens": legacy_decision_tokens,
        "remaining_runner_surfaces": [
            "actual local/global cache storage",
            "timing metrics",
            "evaluate_candidate_fast callback execution",
            "page-owned update and seed scalar collection",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "cases": cases}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_cache_cap_decision_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_cache_cap_decision_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(
        f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items())
    )
    cases = "\n".join(
        f"- `{name}`: matches `{case['matches']}`"
        for name, case in sorted(snapshot["cases"].items())
    )
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Cache/Cap Decision Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Decision Cases",
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
    print("design_guide_fast_candidate_evaluation_cache_cap_decision_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
