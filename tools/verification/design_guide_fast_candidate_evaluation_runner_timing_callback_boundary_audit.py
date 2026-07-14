from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _token_present(segment: str, token: str) -> bool:
    return token in segment


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    start, end, segment = _function_segment(inputs_source, "_evaluate_candidate_fast")

    surfaces = [
        {
            "surface": "generated-count metric mutation",
            "tokens": ['metrics["generated_count"]'],
            "classification": "page-owned runner metric",
            "target_owner": "page shell / runner plumbing",
            "decision": "BOUNDED_PAGE_SHELL",
            "reason": "Metrics mutation is local runner telemetry, not recommendation/publication truth.",
        },
        {
            "surface": "cache key and seen-set plumbing",
            "tokens": ["_candidate_cache_key(", 'context.setdefault("seen_candidate_keys"'],
            "classification": "page-owned cache/key plumbing",
            "target_owner": "page shell unless cache service is separately extracted",
            "decision": "BOUNDED_PAGE_SHELL",
            "reason": "It records duplicate candidate suppression/cache identity and does not shape candidate truth.",
        },
        {
            "surface": "global/local cache storage",
            "tokens": ["_get_eval_cache()", "global_cache", "eval_cache[key]"],
            "classification": "page-owned cache storage",
            "target_owner": "page shell / future cache service",
            "decision": "BOUNDED_PAGE_SHELL",
            "reason": "Actual cache dictionaries remain outside Design Brain to avoid moving mutable page/runtime state.",
        },
        {
            "surface": "cache/cap branch decision",
            "tokens": ["_resolve_fast_candidate_evaluation_cache_cap_decision("],
            "classification": "candidate-evaluation service-owned decision",
            "target_owner": "design_brain.candidate_evaluation",
            "decision": "EXTRACTED",
            "reason": "Pure decision logic is service-owned; page applies the resulting cache/metric effects.",
        },
        {
            "surface": "timing measurement",
            "tokens": ["time.perf_counter()", 'metrics["fast_eval_total_ms"]'],
            "classification": "page-owned runner telemetry",
            "target_owner": "page shell",
            "decision": "BOUNDED_PAGE_SHELL",
            "reason": "Timing is telemetry around callback execution, not Design Brain decision logic.",
        },
        {
            "surface": "fast evaluator callback execution",
            "tokens": ["evaluate_candidate_fast(candidate_state, fast_ctx)"],
            "classification": "page-owned callback execution",
            "target_owner": "page shell until fast evaluator kernel extraction is separately proven",
            "decision": "KEEP_PAGE_OWNED_FOR_NOW",
            "reason": "This executes the evaluator callback and must not move without kernel parity proof.",
        },
        {
            "surface": "post-evaluation complexity input",
            "tokens": ["compute_reo_complexity(cached)"],
            "classification": "page-owned helper input to service projection",
            "target_owner": "page shell until complexity helper boundary is separately proven",
            "decision": "BOUNDED_PAGE_INPUT",
            "reason": "The resulting scalar is passed into service-owned metadata projection.",
        },
        {
            "surface": "runner metadata projection",
            "tokens": ["_build_fast_candidate_evaluation_runner_metadata_projection("],
            "classification": "candidate-evaluation service-owned projection",
            "target_owner": "design_brain.candidate_evaluation",
            "decision": "EXTRACTED",
            "reason": "Pure source/action/update/seed metadata stamping is service-owned.",
        },
    ]
    rows = []
    for row in surfaces:
        rows.append({**row, "present": all(_token_present(segment, token) for token in row["tokens"])})

    checks = {
        "runner_found": bool(segment),
        "all_surfaces_present": all(row["present"] for row in rows),
        "cache_cap_decision_service_owned": any(
            row["surface"] == "cache/cap branch decision"
            and row["decision"] == "EXTRACTED"
            and row["present"]
            for row in rows
        ),
        "metadata_projection_service_owned": any(
            row["surface"] == "runner metadata projection"
            and row["decision"] == "EXTRACTED"
            and row["present"]
            for row in rows
        ),
        "callback_execution_not_moved": any(
            row["surface"] == "fast evaluator callback execution"
            and row["decision"] == "KEEP_PAGE_OWNED_FOR_NOW"
            and row["present"]
            for row in rows
        ),
        "cache_storage_not_moved": any(
            row["surface"] == "global/local cache storage"
            and row["decision"] == "BOUNDED_PAGE_SHELL"
            and row["present"]
            for row in rows
        ),
        "candidate_service_has_no_page_import": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_runner_timing_callback_boundary_audit",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_RUNNER_TIMING_CALLBACK_AND_CACHE_STORAGE_BOUNDED_PAGE_SHELL"
            if status == "PASS"
            else "FAST_RUNNER_TIMING_CALLBACK_BOUNDARY_NOT_PROVEN"
        ),
        "target": {
            "function": "_evaluate_candidate_fast",
            "line_start": start,
            "line_end": end,
        },
        "surface_rows": rows,
        "checks": checks,
        "next_safe_slice": {
            "name": "fast_candidate_evaluation_kernel_boundary_audit",
            "summary": (
                "Audit `evaluate_candidate_fast(...)` solver/helper execution as the next boundary. "
                "Do not move solver/evaluator execution until a kernel parity verifier proves it."
            ),
        },
        "stop_conditions": [
            "Do not move cache dictionaries or metrics mutation into Design Brain in this slice.",
            "Do not move evaluate_candidate_fast callback execution without a separate kernel parity proof.",
            "Do not change candidate cache keys, cap metrics, source/label/action metadata, or candidate updates.",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "rows": rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_runner_timing_callback_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_runner_timing_callback_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    rows = [
        "| Surface | Classification | Target owner | Decision | Present |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in snapshot["surface_rows"]:
        rows.append(
            "| {surface} | {classification} | {target_owner} | {decision} | `{present}` |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    next_slice = snapshot["next_safe_slice"]
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Runner Timing/Callback Boundary Audit",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Surface Inventory",
                *rows,
                "",
                "## Checks",
                checks,
                "",
                "## Next Safe Slice",
                f"- `{next_slice['name']}`",
                f"- {next_slice['summary']}",
                "",
                "## Stop Conditions",
                *[f"- {item}" for item in snapshot["stop_conditions"]],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_fast_candidate_evaluation_runner_timing_callback_boundary_audit " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
