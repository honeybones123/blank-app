"""Audit verifier scale, authority, freshness, and execution cost.

This is a read-only audit. It does not execute product code, delete verifiers,
or promote historical artifacts into release evidence.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
VERIFICATION_DIR = ROOT / "tools" / "verification"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _category(name: str) -> str:
    stem = name.lower()
    if any(token in stem for token in ("browser", "live", "fuzz")):
        return "browser_live"
    if any(token in stem for token in ("lock", "regression", "contract_check", "compliance")):
        return "lock_regression"
    if any(token in stem for token in ("retire", "deletion", "cleanup")):
        return "retirement_cleanup"
    if any(token in stem for token in ("audit", "snapshot", "readiness", "parity")):
        return "audit_snapshot"
    return "other"


def _manifest() -> dict:
    path = VERIFICATION_DIR / "release_gate_manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"path": str(path), "error": str(exc), "release_gates": []}
    return {"path": str(path), **value}


def _script_from_command(command: str) -> str | None:
    match = re.search(r"tools[\\/]verification[\\/]([^\s]+\.py)", command)
    return match.group(1).replace("\\", "/") if match else None


def _source_flags(path: Path) -> dict[str, bool]:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        source = ""
    return {
        "runs_subprocess": "subprocess" in source,
        "uses_browser": any(token in source for token in ("playwright", "browser", "node_repl", "iab")),
        "uses_latest_artifact_by_mtime": any(
            token in source for token in ("sorted(", "stat().st_mtime", "glob(")
        ),
        "has_timeout": any(token in source for token in ("timeout", "TimeoutExpired", "timeout_s")),
    }


def build_payload() -> dict:
    scripts = sorted(VERIFICATION_DIR.glob("*.py"))
    manifest = _manifest()
    gates = [gate for gate in manifest.get("release_gates", []) if isinstance(gate, dict)]
    manifest_scripts = {
        script
        for gate in gates
        if (script := _script_from_command(str(gate.get("command") or "")))
    }
    categories = Counter(_category(path.name) for path in scripts)
    flags = Counter()
    for path in scripts:
        flags.update({key: int(value) for key, value in _source_flags(path).items()})

    latest_universal = sorted(ARTIFACT_DIR.glob("design_brain_universal_live_family_lock_*.json"))
    latest_smooth = sorted(ARTIFACT_DIR.glob("design_brain_family_smooth_operation_lock_*.json"))
    stale_dependency = False
    stale_detail = ""
    if latest_universal and latest_smooth:
        universal_mtime = latest_universal[-1].stat().st_mtime
        smooth_payload = json.loads(latest_smooth[-1].read_text(encoding="utf-8"))
        referenced = Path(str(smooth_payload.get("universal_live_family_artifact") or ""))
        if referenced.exists() and referenced.stat().st_mtime < universal_mtime:
            stale_dependency = True
            stale_detail = f"{latest_smooth[-1].name} references {referenced.name}, older than the latest universal artifact."

    findings = [
        {
            "id": "verifier_volume",
            "severity": "high",
            "finding": f"{len(scripts)} active verifier scripts feed only {len(gates)} canonical release gates.",
            "recommendation": "Retire or classify non-gate scripts; only manifest gates and their named prerequisites should block release.",
        },
        {
            "id": "latest_artifact_authority",
            "severity": "high",
            "finding": "Canonical checks select artifacts by filename prefix and modification time.",
            "recommendation": "Require run_id, source_code_hash, requested_recipe, applied_recipe, and completion timestamp; reject stale or mismatched artifacts.",
        },
        {
            "id": "stale_composed_evidence",
            "severity": "high" if stale_dependency else "medium",
            "finding": stale_detail or "Composed-lock artifact freshness was not fully provable from the available artifact set.",
            "recommendation": "A composed lock must consume child artifacts from the same run manifest, not an independently discovered latest file.",
        },
        {
            "id": "live_runtime_cost",
            "severity": "high",
            "finding": "The universal live family gate runs browser/family scenarios serially and can spend roughly one timeout window per family.",
            "recommendation": "Split structural, deterministic, and browser gates; cache unchanged recipes by code/input hash; run independent families in bounded parallel workers; resume only from hash-matched completed rows.",
        },
        {
            "id": "browser_session_contamination",
            "severity": "medium",
            "finding": "Browser verifiers can attach to an existing Streamlit session, so retained DOM/fragments can contaminate duplicate-widget observations.",
            "recommendation": "Use a fresh browser context per recipe and record context/session id; reserve attached-session probes for diagnostics.",
        },
        {
            "id": "taxonomy_signal",
            "severity": "medium",
            "finding": "Naming taxonomy overlaps: audit/snapshot/readiness/parity scripts are mixed with executable locks and historical cleanup tools.",
            "recommendation": "Add machine-readable verifier metadata: kind, authority, prerequisites, live_required, artifact_prefix, timeout_class, retirement_status.",
        },
    ]
    return {
        "schema": "verifier.system_audit.v1",
        "status": "PASS",
        "audit_only": True,
        "product_behaviour_changed": False,
        "inventory": {
            "active_verifier_scripts": len(scripts),
            "canonical_release_gates": len(gates),
            "scripts_in_release_manifest": len(manifest_scripts),
            "active_scripts_not_in_release_manifest": len(set(path.name for path in scripts) - {Path(item).name for item in manifest_scripts}),
            "categories": dict(categories),
            "source_flags": dict(flags),
        },
        "manifest": {
            "path": manifest.get("path"),
            "gate_ids": [gate.get("id") for gate in gates],
        },
        "findings": findings,
        "recommended_execution_model": [
            "Preflight: compile and verifier self-checks.",
            "Fast deterministic gate: pure contract, hash, ownership, and publication checks.",
            "Focused live gate: only changed families/recipes, with fresh browser contexts.",
            "Full live certification: scheduled or explicit release command, not every chat turn.",
            "Meta lock: accept only same-run, hash-matched child artifacts.",
        ],
        "safe_first_slices": [
            "Add run manifest and source/artifact hash requirements to release gates.",
            "Make composed locks consume explicit child artifact paths from that manifest.",
            "Retire duplicate one-off scripts only after reachability and manifest-reference proof.",
            "Parallelize independent live family recipes after browser isolation is in place.",
        ],
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"verifier_system_audit_{stamp}.json"
    md_path = AUDIT_DIR / f"verifier_system_audit_{stamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Verifier System Audit",
        "",
        "Status: `PASS` (audit completed; this does not certify product readiness)",
        "",
        "## Inventory",
        "",
        f"- Active verifier scripts: `{payload['inventory']['active_verifier_scripts']}`",
        f"- Canonical release gates: `{payload['inventory']['canonical_release_gates']}`",
        f"- Active scripts outside the release manifest: `{payload['inventory']['active_scripts_not_in_release_manifest']}`",
        "",
        "## Findings",
        "",
    ]
    for finding in payload["findings"]:
        lines.extend([f"### {finding['id']} ({finding['severity']})", "", f"Finding: {finding['finding']}", f"Recommendation: {finding['recommendation']}", ""])
    lines.extend(["## Recommended Execution Model", ""])
    lines.extend(f"- {item}" for item in payload["recommended_execution_model"])
    lines.extend(["", "## Safe First Slices", ""])
    lines.extend(f"- {item}" for item in payload["safe_first_slices"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("verifier system audit PASS")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
