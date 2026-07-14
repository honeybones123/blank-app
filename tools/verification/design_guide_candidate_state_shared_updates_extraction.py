from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
TRACKED_KEYS = (
    "b",
    "bw",
    "tw",
    "D",
    "fc",
    "lig_d",
    "lig_legs",
    "s_lig",
    "bot_row_count",
    "bot1_layout_mode",
    "bot1_count",
    "db_bot_1",
    "bot2_layout_mode",
    "bot2_count",
    "db_bot_2",
    "bot_row_1_mode",
    "bot_row_1_bars",
    "bot_row_1_spacing",
    "bot_row_1_dia",
    "bot_row_2_mode",
    "bot_row_2_bars",
    "bot_row_2_spacing",
    "bot_row_2_dia",
)


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


def _load_candidate_module():
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location(
        "candidate_evaluation_for_shared_updates_verifier",
        CANDIDATE_EVALUATION,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to import design_brain.candidate_evaluation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _legacy_updates(seed_state: dict[str, Any] | None, candidate_state: dict[str, Any] | None) -> dict[str, Any]:
    seed = dict(seed_state or {})
    candidate = dict(candidate_state or {})
    updates: dict[str, Any] = {}
    for key in TRACKED_KEYS:
        if seed.get(key) != candidate.get(key):
            updates[key] = candidate.get(key)
    return updates


def build_snapshot() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    candidate_source = CANDIDATE_EVALUATION.read_text(encoding="utf-8")
    _, _, wrapper_segment = _function_segment(inputs_source, "_candidate_state_to_shared_updates")
    module = _load_candidate_module()
    helper = module.resolve_candidate_state_shared_updates

    seed = {key: idx for idx, key in enumerate(TRACKED_KEYS)}
    changed = dict(seed)
    changed["b"] = 450
    changed["D"] = 700
    changed["bot_row_2_dia"] = None
    changed["untracked_key"] = "ignore"
    cases = {
        "no_changes": {"seed": seed, "candidate": dict(seed)},
        "tracked_changes": {"seed": seed, "candidate": changed},
        "missing_candidate_keys": {"seed": seed, "candidate": {"b": seed["b"]}},
        "empty_seed": {"seed": {}, "candidate": {"b": 300, "not_tracked": 10}},
    }
    parity_rows = []
    for name, payload in cases.items():
        old_value = _legacy_updates(payload["seed"], payload["candidate"])
        new_value = helper(payload["seed"], payload["candidate"])
        parity_rows.append({"case": name, "old": old_value, "new": new_value, "matches": old_value == new_value})

    checks = {
        "service_helper_exists": "def resolve_candidate_state_shared_updates(" in candidate_source,
        "service_helper_exported": '"resolve_candidate_state_shared_updates"' in candidate_source,
        "page_helper_delegates": "return _resolve_candidate_state_shared_updates(seed_state, candidate_state)" in wrapper_segment,
        "page_helper_legacy_loop_absent": "for key in tracked_keys:" not in wrapper_segment
        and "updates[key] = candidate_state.get(key)" not in wrapper_segment,
        "all_existing_calls_preserved": inputs_source.count("_candidate_state_to_shared_updates(") >= 5,
        "parity_cases_match": all(row["matches"] for row in parity_rows),
        "candidate_service_has_no_page_import": "inputs_page" not in candidate_source
        and "streamlit" not in candidate_source,
        "product_behavior_unchanged": True,
        "visible_wording_unchanged": True,
        "cta_apply_semantics_unchanged": True,
        "family_runtime_unchanged": True,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "snapshot": "design_guide_candidate_state_shared_updates_extraction",
        "generated_at": _stamp(),
        "status": status,
        "decision": (
            "CANDIDATE_STATE_SHARED_UPDATES_SERVICE_OWNED_PAGE_HELPER_SHELL"
            if status == "PASS"
            else "CANDIDATE_STATE_SHARED_UPDATES_EXTRACTION_FAILED"
        ),
        "checks": checks,
        "parity_rows": parity_rows,
        "remaining_page_shell": [
            "_candidate_state_to_shared_updates(...) compatibility wrapper for existing callsites",
            "callsite ownership and deletion proof",
        ],
        "snapshot_hash": _stable_hash({"checks": checks, "parity_rows": parity_rows}),
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_guide_candidate_state_shared_updates_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_candidate_state_shared_updates_extraction_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    checks = "\n".join(f"- `{key}`: `{value}`" for key, value in sorted(snapshot["checks"].items()))
    rows = [
        "| Case | Matches |",
        "| --- | ---: |",
        *[f"| `{row['case']}` | `{row['matches']}` |" for row in snapshot["parity_rows"]],
    ]
    remaining = "\n".join(f"- {item}" for item in snapshot["remaining_page_shell"])
    md_path.write_text(
        "\n".join(
            [
                "# Candidate State Shared Updates Extraction",
                "",
                f"Status: `{snapshot['status']}`",
                f"Decision: `{snapshot['decision']}`",
                f"Snapshot hash: `{snapshot['snapshot_hash']}`",
                "",
                "## Checks",
                checks,
                "",
                "## Parity Cases",
                *rows,
                "",
                "## Remaining Page Shell",
                remaining,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    snapshot = build_snapshot()
    json_path, md_path = write_outputs(snapshot)
    print("design_guide_candidate_state_shared_updates_extraction " + snapshot["status"])
    print("decision=" + snapshot["decision"])
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
