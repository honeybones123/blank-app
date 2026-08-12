from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
APPLICATION_DIR = ROOT / "application"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _compile(paths: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    return {
        "command": "python -m py_compile " + " ".join(paths),
        "returncode": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
    }


def _imports_streamlit(path: Path) -> bool:
    tree = ast.parse(_read(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "streamlit" or alias.name.startswith("streamlit.") for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if str(node.module or "") == "streamlit" or str(node.module or "").startswith("streamlit."):
                return True
    return False


def _run_store_checks() -> dict[str, Any]:
    from application import (
        AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY,
        AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY,
        AuthoritativeDesignResultStore,
        ensure_design_result,
    )
    from application.contracts.design_brain import (
        EngineeringInputSnapshot,
        build_authoritative_design_result,
    )

    calls: list[str] = []
    session: dict[str, Any] = {}
    store = AuthoritativeDesignResultStore(session)
    snapshot_a = EngineeringInputSnapshot(
        geometry={"D": 300, "b": 250},
        materials={"fc": 32},
        reinforcement={"bottom": {"count": 3, "dia": 16}},
        design_actions={"Mu": 600, "Vu": 450},
        design_settings={"mode": "normal"},
        contract_versions={"design_brain": "v2"},
    )
    snapshot_b = EngineeringInputSnapshot(
        geometry={"D": 350, "b": 250},
        materials={"fc": 32},
        reinforcement={"bottom": {"count": 3, "dia": 16}},
        design_actions={"Mu": 600, "Vu": 450},
        design_settings={"mode": "normal"},
        contract_versions={"design_brain": "v2"},
    )

    def compute(snapshot: EngineeringInputSnapshot):
        calls.append(snapshot.engineering_hash)
        return build_authoritative_design_result(
            engineering_snapshot=snapshot,
            current_calculations={"utilisation": len(calls)},
            governing_family="SHEAR_FAIL_GOVERNS",
            family_outcome="ACTION",
            selected_candidate={"candidate_id": f"candidate-{len(calls)}"},
            selected_updates={"sv": 150 + len(calls)},
            final_publication={"outcome_state": "ACTION"},
            display_model={"title": "Apply shear repair"},
            cta_model={"enabled": True},
            apply_payload={"updates": {"sv": 150 + len(calls)}},
        )

    first = ensure_design_result(result_store=store, snapshot=snapshot_a, compute_fn=compute)
    second = ensure_design_result(result_store=store, snapshot=snapshot_a, compute_fn=compute)
    calls_after_same_hash = list(calls)
    forced = ensure_design_result(result_store=store, snapshot=snapshot_a, compute_fn=compute, force=True)
    changed = ensure_design_result(result_store=store, snapshot=snapshot_b, compute_fn=compute)

    def mismatched_compute(snapshot: EngineeringInputSnapshot):
        return build_authoritative_design_result(
            engineering_snapshot=snapshot_a,
            governing_family="TARGET_BAND_REACHED",
            family_outcome="PASS",
            final_publication={"outcome_state": "PASS"},
            display_model={"title": "OK"},
            cta_model={"enabled": False},
            apply_payload={},
        )

    mismatch_rejected = False
    try:
        ensure_design_result(
            result_store=AuthoritativeDesignResultStore({}),
            snapshot=snapshot_b,
            compute_fn=mismatched_compute,
        )
    except ValueError:
        mismatch_rejected = True

    decision = dict(session.get(AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY) or {})

    return {
        "session_key_is_authoritative_design_result": AUTHORITATIVE_DESIGN_RESULT_SESSION_KEY == "authoritative_design_result",
        "decision_key_is_private_audit_state": AUTHORITATIVE_DESIGN_RESULT_LAST_DECISION_KEY.startswith("_"),
        "first_call_computed_once": len(calls) >= 1 and first.engineering_hash == snapshot_a.engineering_hash,
        "same_hash_reused_exact_object": second is first,
        "same_hash_did_not_recompute": calls_after_same_hash == [snapshot_a.engineering_hash],
        "force_recomputed": forced is not first and calls.count(snapshot_a.engineering_hash) == 2,
        "changed_hash_recomputed": changed.engineering_hash == snapshot_b.engineering_hash and len(calls) == 3,
        "store_current_is_latest_result": store.current() is changed,
        "mismatched_compute_result_rejected": mismatch_rejected,
        "last_decision_recorded": bool(decision),
        "last_decision_reason": decision.get("reason"),
        "no_streamlit_imports": not any(_imports_streamlit(path) for path in APPLICATION_DIR.glob("*.py")),
    }


def _all_pass(checks: dict[str, Any]) -> bool:
    return all(value is True or (isinstance(value, str) and value) for value in checks.values())


def _write_report(snapshot: dict[str, Any], path: Path) -> None:
    lines = [
        "# Authoritative Design Result Store Lock",
        "",
        f"Status: `{snapshot['status']}`",
        "",
        "## Scope",
        "",
        "This proves the application-layer session store and run coordinator for phases 1-2. It does not move live Design Guide rendering, CTA, Apply, or publication ownership yet.",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- `{snapshot['compile']['command']}` -> `{snapshot['compile']['status']}`",
            "",
            "## Remaining Cutover",
            "",
            "- Wire committed live input snapshots into this coordinator.",
            "- Mirror current final publication and primary Apply payload into `AuthoritativeDesignResult`.",
            "- Prove same-hash render reruns perform zero Design Brain work before deleting legacy cache writers.",
            "",
            f"JSON: `{snapshot['artifact']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    compile_result = _compile(
        [
            "application/__init__.py",
            "application/design_result_store.py",
            "application/design_run_coordinator.py",
            "application/contracts/design_brain.py",
            "tools/verification/authoritative_design_result_store_lock.py",
        ]
    )
    checks = _run_store_checks()
    status = "LOCKED" if compile_result["status"] == "PASS" and _all_pass(checks) else "FAIL"
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    artifact_path = ARTIFACT_DIR / f"authoritative_design_result_store_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"authoritative_design_result_store_lock_{stamp}.md"
    snapshot = {
        "schema": "authoritative_design_result_store_lock.v1",
        "status": status,
        "compile": compile_result,
        "checks": checks,
        "artifact": str(artifact_path),
        "report": str(report_path),
    }
    artifact_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_report(snapshot, report_path)
    print(f"{status}: {artifact_path}")
    print(f"REPORT: {report_path}")
    return 0 if status == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())


