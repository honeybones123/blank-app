"""Audit the verification estate and compose a universal coverage decision.

This verifier is intentionally a coverage audit, not a replacement for the
family or browser gates.  It inventories the available checks, selects the
smallest non-duplicative acceptance suite, and records whether each claim is
currently proven, only supported by fresh evidence, or not proven.

It does not start Streamlit, click the browser, mutate engineering inputs, or
change product behaviour.  Live evidence is consumed from existing artifacts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

MAX_FRESH_HOURS = 24.0

CODE_HASH_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "inputs_page_route_coordinators.py",
    "inputs_page_app_contract_bridge.py",
    "design_guide_page.py",
)
CODE_HASH_DIRS: tuple[str, ...] = (
    "design_brain",
    "ui",
    "inputs_page_modules",
)

COMPILE_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "inputs_page_route_coordinators.py",
    "design_brain/final_publication.py",
    "design_brain/candidate_registry.py",
    "inputs_page_modules/fragments.py",
    "inputs_page_modules/recommendation_compute.py",
    "inputs_page_modules/design_guide/current_coordinators.py",
    "inputs_page_modules/design_guide/primary_button_queue.py",
    "inputs_page_modules/design_guide/primary_apply_payload_recorder.py",
    "inputs_page_modules/apply_payload.py",
    "tools/verification/design_brain_universal_verification_coverage_audit.py",
)

CANONICAL_GATES: tuple[dict[str, Any], ...] = (
    {
        "key": "shared_component_matrix",
        "claim": "All shared Design Brain components are locked.",
        "prefix": "design_brain_shared_component_lock_matrix",
        "roots": ("verification",),
        "kind": "structural_shared",
    },
    {
        "key": "family_architecture_end_to_end",
        "claim": "Family ownership, runtime, publication, and UI paths agree.",
        "prefix": "family_architecture_end_to_end_audit",
        "roots": ("verification",),
        "kind": "structural_family",
    },
    {
        "key": "official_family_runtime_certification",
        "claim": "Every required family outcome has current live runtime evidence.",
        "prefix": "remaining_family_runtime_certification",
        "roots": ("audits",),
        "kind": "live_family",
    },
    {
        "key": "family_browser_visual",
        "claim": "Representative family outputs match the live browser publication.",
        "prefix": "design_guide_family_browser_live_visual_consistency",
        "roots": ("verification",),
        "kind": "live_visual",
    },
    {
        "key": "base_browser_visual",
        "claim": "The base Design Guide browser surface has no visual consistency failures.",
        "prefix": "design_guide_browser_live_visual_consistency",
        "roots": ("verification",),
        "kind": "live_visual",
    },
    {
        "key": "apply_10x",
        "claim": "The controlled Apply workflow is stable for ten repetitions.",
        "prefix": "app_stability_inputs_apply_10x_workflow_lock",
        "roots": ("verification",),
        "kind": "live_workflow",
    },
    {
        "key": "post_apply_readiness",
        "claim": "Post-Apply result ownership and readiness are locked.",
        "prefix": "design_brain_shared_post_apply_readiness_lock",
        "roots": ("verification",),
        "kind": "shared_runtime",
    },
    {
        "key": "publication_hash_cache_reuse",
        "claim": "Publication authority and cache reuse are deterministic.",
        "prefix": "design_brain_shared_publication_hash_cache_reuse_lock",
        "roots": ("verification",),
        "kind": "shared_runtime",
    },
    {
        "key": "smoothness",
        "claim": "The current post-Apply smoothness path is stable.",
        "prefix": "app_stability_post_apply_smoothness_root_cause_lock",
        "roots": ("verification",),
        "kind": "live_workflow",
    },
    {
        "key": "universal_fuzz",
        "claim": "The legacy all-family fuzz runner passes action and publication checks.",
        "prefix": "family_10_fuzz_audit",
        "roots": ("verification",),
        "kind": "legacy_universal",
    },
    {
        "key": "universal_live_family_lock",
        "claim": "The top-level universal live family lock is current and locked.",
        "prefix": "design_brain_universal_live_family_lock",
        "roots": ("verification",),
        "kind": "universal_lock",
    },
    {
        "key": "universal_meta_lock",
        "claim": "The final universal verification meta-lock is current and locked.",
        "prefix": "design_brain_universal_verification_meta_lock",
        "roots": ("verification",),
        "kind": "universal_lock",
    },
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "UNREADABLE", "error": str(exc)}
    return value if isinstance(value, dict) else {"status": "UNREADABLE", "error": "json root is not object"}


def _latest(prefix: str, roots: tuple[str, ...]) -> tuple[Path | None, dict[str, Any]]:
    paths: list[Path] = []
    for root_name in roots:
        root = ARTIFACT_DIR if root_name == "verification" else AUDIT_DIR
        paths.extend(root.glob(f"{prefix}_*.json"))
    if not paths:
        return None, {}
    path = max(paths, key=lambda item: item.stat().st_mtime)
    return path, _read_json(path)


def _status(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("universal_lock_status")
        or payload.get("meta_lock_status")
        or "MISSING"
    ).strip().upper()


def _age_hours(path: Path | None) -> float | None:
    if not path:
        return None
    return round(max(0.0, time.time() - path.stat().st_mtime) / 3600.0, 3)


def _code_state_hash() -> str:
    digest = hashlib.sha256()
    files: list[Path] = []
    for relative in CODE_HASH_FILES:
        path = ROOT / relative
        if path.is_file():
            files.append(path)
    for relative in CODE_HASH_DIRS:
        folder = ROOT / relative
        if folder.is_dir():
            files.extend(folder.rglob("*.py"))
            files.extend(folder.rglob("*.json"))
    for path in sorted({path for path in files if "__pycache__" not in path.parts}, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _payload_passes_gate(key: str, payload: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    status = _status(payload)
    if key == "official_family_runtime_certification":
        if status != "PASS":
            failures.append(f"status={status}")
        if int(payload.get("certified_count") or 0) < int(payload.get("required_count") or 1):
            failures.append("certified_count_below_required_count")
        if int(payload.get("attempted_count") or 0) < int(payload.get("required_count") or 1):
            failures.append("attempted_count_below_required_count")
        if any(dict(row).get("failures") for row in payload.get("families") or [] if isinstance(row, dict)):
            failures.append("family_failure_rows_present")
    elif key == "apply_10x":
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if status != "PASS":
            failures.append(f"status={status}")
        if int(summary.get("passed_iterations") or 0) < 10:
            failures.append("passed_iterations_below_10")
        if int(summary.get("failed_iterations") or 0) != 0:
            failures.append("failed_iterations_nonzero")
    elif key == "universal_fuzz":
        if status != "LIVE_EXECUTION_PASS":
            failures.append(f"status={status}")
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        if int(summary.get("families_live_failed") or 0) != 0:
            failures.append("families_live_failed_nonzero")
        if int(summary.get("button_action_failures") or 0) != 0:
            failures.append("button_action_failures_nonzero")
        if int(summary.get("publication_mismatches") or 0) != 0:
            failures.append("publication_mismatches_nonzero")
    elif key == "universal_live_family_lock":
        if str(payload.get("universal_lock_status") or "").upper() != "LOCKED":
            failures.append("universal_lock_status_not_locked")
        if status not in {"PASS", "LIVE_EXECUTION_PASS"}:
            failures.append(f"status={status}")
    elif key == "universal_meta_lock":
        if str(payload.get("meta_lock_status") or "").upper() != "LOCKED":
            failures.append("meta_lock_status_not_locked")
    elif key in {"post_apply_readiness", "publication_hash_cache_reuse"}:
        if status != "LOCKED":
            failures.append(f"status={status}")
    else:
        if status not in {"PASS", "PASSED", "LOCKED", "LIVE_EXECUTION_PASS"}:
            failures.append(f"status={status}")
    return not failures, failures


def _gate_rows() -> list[dict[str, Any]]:
    current_hash = _code_state_hash()
    rows: list[dict[str, Any]] = []
    for gate in CANONICAL_GATES:
        path, payload = _latest(str(gate["prefix"]), tuple(gate["roots"]))
        passed, failures = _payload_passes_gate(str(gate["key"]), payload)
        age = _age_hours(path)
        reported_hash = payload.get("code_state_hash") or payload.get("current_code_state_hash")
        code_binding = "MATCH" if reported_hash and reported_hash == current_hash else "MISSING_OR_DIFFERENT"
        fresh = age is not None and age <= MAX_FRESH_HOURS
        if not path:
            evidence_status = "NOT_PROVEN"
        elif not passed:
            evidence_status = "FAILED"
        elif not fresh:
            evidence_status = "STALE_PASS"
        elif code_binding == "MATCH":
            evidence_status = "PROVEN"
        else:
            evidence_status = "FRESH_PASS_UNBOUND"
        rows.append(
            {
                "key": gate["key"],
                "claim": gate["claim"],
                "kind": gate["kind"],
                "prefix": gate["prefix"],
                "path": str(path) if path else None,
                "status": _status(payload),
                "evidence_status": evidence_status,
                "passed_gate": passed,
                "fresh_within_hours": fresh,
                "age_hours": age,
                "code_binding": code_binding,
                "failures": failures,
                "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
            }
        )
    return rows


def _script_inventory() -> dict[str, Any]:
    files = sorted((ROOT / "tools" / "verification").rglob("*.py"))
    active = [path for path in files if "archived" not in path.parts]
    archived = [path for path in files if "archived" in path.parts]
    category_terms = {
        "universal": ("universal", "coverage_audit"),
        "shared": ("shared", "component_lock", "candidate_evaluation_registry"),
        "family": ("family", "bending", "shear", "bottom_reo"),
        "browser_live": ("browser", "live", "fuzz", "playwright"),
        "stability_apply": ("stability", "apply", "smoothness", "post_apply"),
        "publication_ui": ("publication", "render", "cta", "display", "session"),
    }
    counts = {key: 0 for key in category_terms}
    for path in active:
        name = path.name.lower()
        for category, terms in category_terms.items():
            if any(term in name for term in terms):
                counts[category] += 1
    return {
        "active_script_count": len(active),
        "archived_script_count": len(archived),
        "category_counts": counts,
        "active_scripts": [str(path.relative_to(ROOT)).replace("\\", "/") for path in active],
        "archived_scripts": [str(path.relative_to(ROOT)).replace("\\", "/") for path in archived],
    }


def _run_compile() -> dict[str, Any]:
    command = [sys.executable, "-m", "py_compile", *COMPILE_FILES]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
    return {
        "command": " ".join(command),
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def _family_coverage() -> dict[str, Any]:
    path, payload = _latest("remaining_family_runtime_certification", ("audits",))
    rows = [row for row in payload.get("families") or [] if isinstance(row, dict)]
    families = sorted({str(row.get("family") or "") for row in rows if row.get("family")})
    mutation_rows = [
        mutation
        for row in rows
        for mutation in (dict(row.get("mutation_detection") or {}).get("mutation_rows") or [])
        if isinstance(mutation, dict)
    ]
    caught = sum(1 for row in mutation_rows if str(row.get("status") or "").upper() == "CAUGHT")
    return {
        "artifact": str(path) if path else None,
        "required_count": payload.get("required_count"),
        "attempted_count": payload.get("attempted_count"),
        "certified_count": payload.get("certified_count"),
        "families": families,
        "failure_sensitivity_mutations": len(mutation_rows),
        "failure_sensitivity_caught": caught,
        "failure_sensitivity_pass": bool(mutation_rows) and caught == len(mutation_rows),
    }


def _markdown(snapshot: dict[str, Any]) -> str:
    rows = snapshot["canonical_gates"]
    lines = [
        "# Universal Verification Coverage Audit",
        "",
        f"Generated: `{snapshot['generated_at']}`",
        "",
        "## Decision",
        "",
        f"**Universal certification status: `{snapshot['universal_status']}`**",
        "",
        snapshot["decision_summary"],
        "",
        "The audit separates structural proof, live runtime proof, browser evidence, freshness, and source-code binding. A green artifact is not counted as fully current when it is stale, failed, or unbound to the present source tree.",
        "",
        "## Canonical Suite",
        "",
        "| Claim | Evidence | Status | Current source bound | Notes |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['claim']} | `{row['prefix']}` | `{row['evidence_status']}` | `{row['code_binding']}` | {'; '.join(row['failures']) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Family Coverage",
            "",
            f"Official live family evidence: `{snapshot['family_coverage']['certified_count']}/{snapshot['family_coverage']['required_count']}` certified.",
            f"Failure-sensitivity mutations caught: `{snapshot['family_coverage']['failure_sensitivity_caught']}/{snapshot['family_coverage']['failure_sensitivity_mutations']}`.",
            "",
            "Families covered by the official runtime artifact:",
            "",
            ", ".join(f"`{family}`" for family in snapshot["family_coverage"]["families"]),
            "",
            "## Verification Estate",
            "",
            f"Active verification scripts: `{snapshot['script_inventory']['active_script_count']}`.",
            f"Archived verification scripts: `{snapshot['script_inventory']['archived_script_count']}`.",
            f"Categories: `{snapshot['script_inventory']['category_counts']}`.",
            "",
            "## Gaps",
            "",
        ]
    )
    for gap in snapshot["gaps"]:
        lines.append(f"- {gap}")
    lines.extend(
        [
            "",
            "## Recommended Use",
            "",
            "1. Use the shared component matrix and family architecture audit for structural ownership.",
            "2. Use official 14/14 live family certification for family runtime, Apply, and mutation-sensitivity evidence.",
            "3. Use browser visual and smoothness locks for live presentation and interaction evidence.",
            "4. Keep the legacy all-family fuzz runner as a separate failure-sensitive regression gate until its action/publication mismatches are resolved.",
            "5. Do not promote the universal meta-lock until all required evidence is current, source-bound, and green.",
            "",
            "## Compile Gate",
            "",
            f"`{snapshot['compile']['command']}`",
            "",
            f"Result: `{ 'PASS' if snapshot['compile']['passed'] else 'FAIL' }`.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_snapshot() -> dict[str, Any]:
    canonical = _gate_rows()
    compile_result = _run_compile()
    family_coverage = _family_coverage()
    script_inventory = _script_inventory()
    gaps: list[str] = []
    for row in canonical:
        if row["evidence_status"] in {"FAILED", "NOT_PROVEN", "STALE_PASS"}:
            gaps.append(f"{row['key']}: {row['evidence_status']} ({'; '.join(row['failures']) or 'missing or stale evidence'})")
        elif row["evidence_status"] == "FRESH_PASS_UNBOUND":
            gaps.append(f"{row['key']}: fresh pass is not bound to the current source hash")
    if not family_coverage["failure_sensitivity_pass"]:
        gaps.append("official_family_runtime_certification: mutation failure-sensitivity coverage is incomplete")
    if not compile_result["passed"]:
        gaps.append("static_compile: compile gate failed")
    hard_green = all(row["evidence_status"] == "PROVEN" for row in canonical) and compile_result["passed"]
    if hard_green:
        status = "UNIVERSAL_PROVEN"
        summary = "All canonical structural, family, live browser, stability, fuzz, and source-binding gates are current and green."
    else:
        status = "UNIVERSAL_NOT_PROVEN"
        summary = "The audit found useful green evidence, but at least one universal gate is failed, stale, or not bound to the current source tree."
    return {
        "schema": "design_brain.universal_verification_coverage_audit.v1",
        "generated_at": _stamp(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_code_state_hash": _code_state_hash(),
        "max_fresh_hours": MAX_FRESH_HOURS,
        "universal_status": status,
        "decision_summary": summary,
        "canonical_gates": canonical,
        "family_coverage": family_coverage,
        "script_inventory": script_inventory,
        "compile": compile_result,
        "gaps": gaps,
    }


def main() -> int:
    snapshot = build_snapshot()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = snapshot["generated_at"]
    json_path = ARTIFACT_DIR / f"design_brain_universal_verification_coverage_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"design_brain_universal_verification_coverage_audit_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(snapshot), encoding="utf-8")
    print(f"Universal verification coverage audit: {snapshot['universal_status']}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")
    for gap in snapshot["gaps"]:
        print(f"GAP: {gap}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
