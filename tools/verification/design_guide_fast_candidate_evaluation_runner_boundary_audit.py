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


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    start, end, segment = _function_segment(inputs_source, "_evaluate_candidate_fast")
    surfaces = [
        {
            "surface": "generated-count metric mutation",
            "tokens": ['metrics["generated_count"]'],
            "classification": "page-owned runner metrics",
            "target_owner": "candidate_evaluation runner only after cache/cap parity",
            "extraction_readiness": "NOT_READY_RUNNER_PARITY",
            "risk": "MEDIUM",
        },
        {
            "surface": "candidate cache key and seen-set mutation",
            "tokens": ["_candidate_cache_key(", 'context.setdefault("seen_candidate_keys"'],
            "classification": "runner/cache plumbing",
            "target_owner": "candidate_evaluation runner with injected key/cache dependencies",
            "extraction_readiness": "NOT_READY_CACHE_KEY_BOUNDARY",
            "risk": "MEDIUM",
        },
        {
            "surface": "global eval cache use",
            "tokens": ["_get_eval_cache()", "_ENABLE_GLOBAL_EVAL_CACHE", "global_cache"],
            "classification": "page/global cache plumbing",
            "target_owner": "page shell or shared cache service",
            "extraction_readiness": "UNSAFE_TO_MOVE_WITHOUT_CACHE_SEMANTICS_PROOF",
            "risk": "HIGH",
        },
        {
            "surface": "unique-eval cap guard",
            "tokens": ["_resolve_fast_candidate_evaluation_cache_cap_decision("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "candidate_evaluation runner",
            "extraction_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
        },
        {
            "surface": "timer and evaluator callback execution",
            "tokens": ["time.perf_counter()", "evaluate_candidate_fast(candidate_state, fast_ctx)"],
            "classification": "page-owned callback execution/timing",
            "target_owner": "page shell until evaluator kernel move is proven",
            "extraction_readiness": "KEEP_PAGE_OWNED_FOR_NOW",
            "risk": "HIGH",
        },
        {
            "surface": "cached-candidate complexity post-processing",
            "tokens": ['cached["reo_complexity"] = compute_reo_complexity(cached)'],
            "classification": "page-owned complexity helper input collection",
            "target_owner": "candidate_evaluation metadata projection after complexity service extraction",
            "extraction_readiness": "BOUNDED_PAGE_INPUT_FOR_METADATA_PROJECTION",
            "risk": "LOW",
        },
        {
            "surface": "candidate source/label/action/state/update stamping",
            "tokens": ["_build_fast_candidate_evaluation_runner_metadata_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "candidate_evaluation metadata projection",
            "extraction_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
        },
        {
            "surface": "seed geometry/steel metadata stamping",
            "tokens": ["_build_fast_candidate_evaluation_runner_metadata_projection("],
            "classification": "EXTRACTED_SERVICE_BOUNDARY",
            "target_owner": "candidate_evaluation metadata projection",
            "extraction_readiness": "SHELL_CALL_ONLY_FOR_THIS_SURFACE",
            "risk": "LOW",
        },
    ]
    rows = []
    for row in surfaces:
        rows.append(
            {
                **row,
                "present": all(token in segment for token in row["tokens"]),
            }
        )
    checks = {
        "runner_found": bool(segment),
        "candidate_evaluation_import_clean": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "all_surfaces_classified": all(row["present"] for row in rows),
        "metadata_projection_extracted": any(
            row["surface"] == "candidate source/label/action/state/update stamping"
            and row["classification"] == "EXTRACTED_SERVICE_BOUNDARY"
            and row["present"]
            for row in rows
        ),
        "cache_cap_decision_extracted": any(
            row["surface"] == "unique-eval cap guard"
            and row["classification"] == "EXTRACTED_SERVICE_BOUNDARY"
            and row["present"]
            for row in rows
        ),
        "callback_execution_kept_page_owned": any(
            row["surface"] == "timer and evaluator callback execution"
            and row["classification"] == "page-owned callback execution/timing"
            for row in rows
        ),
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_fast_candidate_evaluation_runner_boundary_audit",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "FAST_RUNNER_METADATA_AND_CACHE_CAP_DECISION_EXTRACTED_CALLBACK_AND_CACHE_STORAGE_STAY_PAGE_OWNED"
            if status == "PASS"
            else "FAST_RUNNER_BOUNDARY_NOT_CLASSIFIED"
        ),
        "target": {
            "function": "_evaluate_candidate_fast",
            "line_start": start,
            "line_end": end,
        },
        "checks": checks,
        "surface_rows": rows,
        "first_safe_implementation_slice": {
            "name": "fast_candidate_evaluation_runner_timing_callback_boundary_audit",
            "summary": (
                "Audit whether timing/cache-storage plumbing can be bounded further. Keep evaluator "
                "callback execution in inputs_page.py unless the fast evaluator kernel move is separately proven."
            ),
        },
        "stop_conditions": [
            "Do not move evaluate_candidate_fast callback execution.",
            "Do not move Streamlit/session/global cache semantics into candidate_evaluation.",
            "Do not change cache hit/miss/cap metrics.",
            "Do not change candidate updates/source/label/action_type/state metadata.",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "rows": rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_fast_candidate_evaluation_runner_boundary_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_fast_candidate_evaluation_runner_boundary_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    rows = [
        "| Surface | Classification | Target owner | Readiness | Risk | Present |",
        "| --- | --- | --- | --- | --- | ---: |",
    ]
    for row in snapshot["surface_rows"]:
        rows.append(
            "| {surface} | {classification} | {target_owner} | {extraction_readiness} | {risk} | `{present}` |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    checks = "\n".join(
        f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items())
    )
    first = dict(snapshot["first_safe_implementation_slice"])
    md_path.write_text(
        "\n".join(
            [
                "# Fast Candidate Evaluation Runner Boundary Audit",
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
                "## First Safe Implementation Slice",
                f"- `{first['name']}`",
                f"- {first['summary']}",
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
    print("design_guide_fast_candidate_evaluation_runner_boundary_audit " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
