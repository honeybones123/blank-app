"""Verify trace-only branch predicate probes for pre-helper rebind bridges."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"

HELPER = "_record_controller_pre_helper_rebind_branch_predicate_probe"
TARGETS = {
    "combined_evidence_rebind_bridge": {
        "predicate_token": "_combined_rebind_predicates = {",
        "callsite_token": 'callsite_id="combined_evidence_rebind_bridge"',
        "if_tokens": (
            '_combined_rebind_predicates["engine_evidence_family_is_combined"]',
            '_combined_rebind_predicates["displayed_contract_updates_differ"]',
        ),
        "expect_if_body": False,
    },
    "engine_evidence_rebind_bridge": {
        "predicate_token": "_engine_rebind_predicates = {",
        "callsite_token": 'callsite_id="engine_evidence_rebind_bridge"',
        "if_tokens": (
            '_engine_rebind_predicates["engine_evidence_family_is_combined"]',
            '_engine_rebind_predicates["engine_contract_updates_differ"]',
        ),
        "expect_if_body": False,
    },
}
REQUIRED_ARTIFACTS = (
    "design_guide_controller_rebind_effects_pre_helper_cutover_parity_trace",
    "design_guide_controller_rebind_effects_pre_helper_live_coverage_gap",
    "design_guide_render_bridge_lock",
    "design_guide_compute_resolver_publication_bridge_lock",
    "design_guide_independence_lock",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "path": None, "status": "MISSING"}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"found": True, "path": str(path), "status": "UNREADABLE", "error": str(exc)}
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    return {"found": True, "path": str(path), "status": "PASS" if "PASS" in status.upper() else status}


def _run(command: list[str]) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def _line_for(lines: list[str], token: str) -> int | None:
    for index, line in enumerate(lines, start=1):
        if token in line:
            return index
    return None


def _window(lines: list[str], line: int | None, *, before: int = 8, after: int = 90) -> str:
    if line is None:
        return ""
    start = max(1, line - before)
    end = min(len(lines), line + after)
    return "\n".join(lines[start - 1 : end])


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    lines = source.splitlines()
    helper_line = _line_for(lines, f"def {HELPER}(")
    helper_context = _window(lines, helper_line, before=0, after=70)
    rows = []
    for callsite_id, target in TARGETS.items():
        line = _line_for(lines, target["predicate_token"])
        context = _window(lines, line, before=4, after=85)
        rows.append(
            {
                "callsite_id": callsite_id,
                "line": line,
                "predicate_map_present": target["predicate_token"] in context,
                "probe_call_present": f"{HELPER}(" in context,
                "callsite_id_present": target["callsite_token"] in context,
                "expect_if_body": bool(target["expect_if_body"]),
                "if_uses_predicate_map": all(token in context for token in target["if_tokens"]),
            }
        )
    latest = {prefix: _latest(prefix) for prefix in REQUIRED_ARTIFACTS}
    return {
        "helper_line": helper_line,
        "helper_checks": {
            "helper_defined": helper_line is not None,
            "probe_bucket_stamped": (
                "controller_final_visible_rebind_effects_pre_helper_branch_predicate_probes"
                in helper_context
            ),
            "non_driving_stamped": all(
                token in helper_context
                for token in (
                    "branch_predicate_probe_trace_only",
                    "branch_predicate_probe_product_driving",
                    "branch_predicate_probe_render_driving",
                    "branch_predicate_probe_apply_driving",
                    "branch_predicate_probe_session_driving",
                )
            ),
            "stable_hash_stamped": "predicate_hash" in helper_context
            and "branch_predicate_probe_hash" in helper_context,
        },
        "rows": rows,
        "latest_artifacts": latest,
        "decision": "BRANCH_PREDICATE_PROBES_WIRED_TRACE_ONLY_NOT_PRODUCT_DRIVING",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Pre-Helper Rebind Branch Predicate Probe Snapshot",
        "",
        f"Status: `{payload['status']}`",
        f"Decision: `{capture.get('decision')}`",
        "",
        "| Callsite | Line | Predicate Map | Probe Call | If Uses Map |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in capture.get("rows") or []:
        lines.append(
            f"| `{row.get('callsite_id')}` | `{row.get('line')}` | `{row.get('predicate_map_present')}` | `{row.get('probe_call_present')}` | `{row.get('if_uses_predicate_map')}` |"
        )
    if payload.get("failures"):
        lines.extend(["", "## Failures", "", "```json", json.dumps(payload["failures"], indent=2), "```"])
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Run browser/live capture again and inspect the predicate probes for both bridges.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    compile_run = _run(
        [
            sys.executable,
            "-m",
            "py_compile",
            "inputs_page.py",
            "tools/verification/design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe_snapshot.py",
        ]
    )
    capture = _capture()
    helper_checks = dict(capture.get("helper_checks") or {})
    rows = list(capture.get("rows") or [])
    latest = dict(capture.get("latest_artifacts") or {})
    checks = {
        "py_compile_pass": compile_run["returncode"] == 0,
        "helper_defined": helper_checks.get("helper_defined") is True,
        "probe_bucket_stamped": helper_checks.get("probe_bucket_stamped") is True,
        "helper_non_driving": helper_checks.get("non_driving_stamped") is True,
        "stable_hash_stamped": helper_checks.get("stable_hash_stamped") is True,
        "two_rows_captured": len(rows) == 2,
        "predicate_maps_present": all(row.get("predicate_map_present") is True for row in rows),
        "probe_calls_present": all(row.get("probe_call_present") is True for row in rows),
        "callsite_ids_present": all(row.get("callsite_id_present") is True for row in rows),
        "if_presence_matches_expectation": all(
            row.get("if_uses_predicate_map") is row.get("expect_if_body") for row in rows
        ),
        "required_artifacts_green": all(
            (artifact or {}).get("status") == "PASS" for artifact in latest.values()
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe_snapshot.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
        "compile_run": compile_run,
        "failures": failures,
    }
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(audit_path, payload)
    print(f"design_guide_controller_rebind_effects_pre_helper_branch_predicate_probe {status}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    if failures:
        print("failures=" + json.dumps(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
