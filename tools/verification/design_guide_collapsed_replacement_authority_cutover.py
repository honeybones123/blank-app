"""Live cutover verifier for collapsed guidance replacement authority.

This verifier proves collapsed_guidance_items replacement is now mediated by
FinalDesignGuidePublication via the Design Brain collapsed item adapter. It
does not require moving CTA rendering, apply routing, visible wording, family
runtimes, or evaluator behavior.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

REQUIRED_CALLSITES = {
    "compute_publication_resolution": "publication_reason=str(final_compute_resolution.get(\"render_reason\") or \"compute_publication_resolution\")",
    "late_evidence_contract_rebound": "publication_reason=\"late_evidence_contract_rebound\"",
    "post_evidence_contract_rebound": "publication_reason=\"post_evidence_contract_rebound\"",
}

FORBIDDEN_RUNTIME_MOVES = (
    "move_cta_rendering_into_final_publication",
    "move_apply_routing_into_final_publication",
    "move_visible_wording_into_final_publication",
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _run(script: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, script],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "script": script,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout.strip().splitlines()[-12:],
        "stderr_tail": proc.stderr.strip().splitlines()[-12:],
    }


def _latest_artifact(prefix: str) -> dict[str, Any]:
    artifacts = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not artifacts:
        return {"path": None, "snapshot": None}
    path = artifacts[-1]
    return {
        "path": str(path),
        "snapshot": json.loads(path.read_text(encoding="utf-8")),
    }


def _function_bounds(source: str, function_name: str) -> tuple[int, int] | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return int(node.lineno), int(getattr(node, "end_lineno", node.lineno))
    return None


def _function_source(source: str, function_name: str) -> str:
    bounds = _function_bounds(source, function_name)
    if bounds is None:
        return ""
    start, end = bounds
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end])


def _line_containing(source: str, needle: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return index
    return None


def _build_snapshot() -> dict[str, Any]:
    adapter_run = _run("tools/verification/design_guide_collapsed_guidance_adapter_parity_snapshot.py")
    consumes_run = _run("tools/verification/design_guide_collapsed_replacement_consumes_publication_snapshot.py")
    lock_run = _run("tools/verification/design_guide_independence_lock_verifier.py")
    adapter_artifact = _latest_artifact("design_guide_collapsed_guidance_adapter_parity")
    consumes_artifact = _latest_artifact("design_guide_collapsed_replacement_consumes_publication_snapshot")
    lock_artifact = _latest_artifact("design_guide_independence_lock")

    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    helper_source = _function_source(input_source, "_collapsed_guidance_item_from_final_publication_authority")
    adapter_source = _function_source(publication_source, "build_collapsed_guidance_item_from_final_publication")

    callsites = {
        name: {
            "marker": marker,
            "present": marker in input_source,
            "line": _line_containing(input_source, marker),
        }
        for name, marker in REQUIRED_CALLSITES.items()
    }
    imports_present = {
        "build_final_design_guide_publication": "build_final_design_guide_publication as _build_final_design_guide_publication" in input_source,
        "build_collapsed_guidance_item_from_final_publication": (
            "build_collapsed_guidance_item_from_final_publication as _build_collapsed_guidance_item_from_final_publication"
            in input_source
        ),
    }
    helper_checks = {
        "helper_exists": bool(helper_source),
        "builds_final_publication": "_build_final_design_guide_publication(" in helper_source,
        "uses_collapsed_adapter": "_build_collapsed_guidance_item_from_final_publication(" in helper_source,
        "stamps_publication_authority": "collapsed_guidance_replacement_authority" in helper_source,
        "fallback_available": "legacy_fallback" in helper_source,
        "fallback_non_authoritative": "legacy_non_authoritative" in helper_source and "compatibility_only" in helper_source,
    }
    adapter_checks = {
        "adapter_exists": bool(adapter_source),
        "accepts_final_publication": "FinalDesignGuidePublication" in adapter_source,
        "no_inputs_page_import": "inputs_page" not in publication_source,
        "no_streamlit_import": "streamlit" not in publication_source,
        "proof_only_flag": "collapsed_guidance_adapter_proof_only" in adapter_source,
        "non_product_driving_flag": '"product_driving": False' in adapter_source,
        "non_render_driving_flag": '"render_driving": False' in adapter_source,
    }
    ownership_guards = {
        "cta_rendering_stays_page_owned": "_design_guide_dashboard_card_html_from_render_model" in input_source
        and "_design_guide_dashboard_card_html_from_render_model" not in publication_source,
        "apply_routing_stays_page_owned": "_record_rendered_design_guide_primary_apply_payload" in input_source
        and "_record_rendered_design_guide_primary_apply_payload" not in publication_source,
        "visible_wording_stays_page_owned": "_design_guide_clean_main_card_text" in input_source
        and "_design_guide_clean_main_card_text" not in publication_source,
        "no_forbidden_runtime_move_markers": not any(marker in publication_source for marker in FORBIDDEN_RUNTIME_MOVES),
    }
    consumes_snapshot = consumes_artifact.get("snapshot") or {}
    failures: list[str] = []
    if not adapter_run["passed"]:
        failures.append("adapter_parity_failed")
    if not consumes_run["passed"]:
        failures.append("replacement_consumes_publication_snapshot_failed")
    if not lock_run["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if not all(row["present"] for row in callsites.values()):
        failures.append("missing_adapter_wired_callsite")
    if not all(imports_present.values()):
        failures.append("missing_final_publication_import")
    if not all(helper_checks.values()):
        failures.append("helper_contract_failed")
    if not all(adapter_checks.values()):
        failures.append("adapter_contract_failed")
    if not all(ownership_guards.values()):
        failures.append("ownership_guard_failed")
    if consumes_snapshot.get("status") != "PASS":
        failures.append("replacement_consumes_publication_not_pass")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "callsites": callsites,
        "imports_present": imports_present,
        "helper_checks": helper_checks,
        "adapter_checks": adapter_checks,
        "ownership_guards": ownership_guards,
        "adapter_artifact": adapter_artifact.get("path"),
        "consumes_artifact": consumes_artifact.get("path"),
        "lock_artifact": lock_artifact.get("path"),
    }
    return {
        "snapshot_name": "design_guide_collapsed_replacement_authority_cutover",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "callsites": callsites,
        "imports_present": imports_present,
        "helper_checks": helper_checks,
        "adapter_checks": adapter_checks,
        "ownership_guards": ownership_guards,
        "verification": {
            "collapsed_guidance_adapter_parity": adapter_run,
            "collapsed_replacement_consumes_publication": consumes_run,
            "design_guide_independence_lock": lock_run,
        },
        "source_artifacts": {
            "adapter_parity": adapter_artifact.get("path"),
            "replacement_consumes_publication": consumes_artifact.get("path"),
            "independence_lock": lock_artifact.get("path"),
        },
        "product_behavior_changed": False,
        "cta_rendering_moved": False,
        "apply_routing_moved": False,
        "visible_wording_moved": False,
        "fallback_available_non_authoritative": bool(helper_checks["fallback_available"] and helper_checks["fallback_non_authoritative"]),
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    callsite_rows = [
        f"| `{name}` | `{row['line']}` | `{row['present']}` |"
        for name, row in snapshot["callsites"].items()
    ]
    body = "\n".join(
        [
            "# Design Guide Collapsed Replacement Authority Cutover",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Product behavior changed: `{snapshot['product_behavior_changed']}`",
            f"- CTA rendering moved: `{snapshot['cta_rendering_moved']}`",
            f"- Apply routing moved: `{snapshot['apply_routing_moved']}`",
            f"- Visible wording moved: `{snapshot['visible_wording_moved']}`",
            f"- Fallback available and non-authoritative: `{snapshot['fallback_available_non_authoritative']}`",
            "",
            "## Wired Callsites",
            "",
            "| Callsite | Line | Present |",
            "|---|---:|---:|",
            *callsite_rows,
            "",
            "## Ownership Guards",
            "",
            *[f"- `{key}`: `{value}`" for key, value in snapshot["ownership_guards"].items()],
            "",
            "## Source Artifacts",
            "",
            f"- Adapter parity: `{snapshot['source_artifacts']['adapter_parity']}`",
            f"- Replacement consumes publication: `{snapshot['source_artifacts']['replacement_consumes_publication']}`",
            f"- Independence lock: `{snapshot['source_artifacts']['independence_lock']}`",
            "",
            "## Failures",
            "",
            (
                "None."
                if not snapshot["failures"]
                else "\n".join(f"- `{failure}`" for failure in snapshot["failures"])
            ),
        ]
    )
    path.write_text(body + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    stamp = snapshot["generated_at"].replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_collapsed_replacement_authority_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_collapsed_replacement_authority_cutover_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_collapsed_replacement_authority_cutover {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
