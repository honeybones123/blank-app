from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]

SOURCE_FINGERPRINT_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "design_brain/engine.py",
    "state_and_helpers.py",
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/browser_helpers.py",
    "tools/verification/artifact_contract.py",
    "tools/verification/source_fingerprint.py",
    "tools/verification/verifier_self_check.py",
    "tools/verification/previous_fixes_gate.py",
    "tools/run_design_guide_previous_fixes_gate.py",
    "tools/verification/golden_matrix_runner.py",
    "tools/run_design_guide_golden_matrix.py",
    "tools/verification/regression_contract_manifest.json",
)

CORRECTNESS_FINGERPRINT_FILES: tuple[str, ...] = (
    "app.py",
    "inputs_page.py",
    "design_brain/engine.py",
    "state_and_helpers.py",
    "tools/verification/regression_contract_manifest.json",
)

DIAGNOSTIC_FINGERPRINT_FILES: tuple[str, ...] = (
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/browser_helpers.py",
    "tools/verification/artifact_contract.py",
    "tools/verification/source_fingerprint.py",
    "tools/verification/verifier_self_check.py",
    "tools/run_design_guide_previous_fixes_gate.py",
    "tools/run_design_guide_golden_matrix.py",
)

VERIFIER_RUNTIME_FINGERPRINT_FILES: tuple[str, ...] = (
    "tools/browser_live_design_guide_fuzz_verifier.py",
    "tools/verification/helpers/browser_helpers.py",
    "tools/verification/previous_fixes_gate.py",
    "tools/verification/golden_matrix_runner.py",
    "tools/verification/root_cause_proof.py",
    "tools/verification/root_cause_proof_policy.py",
    "tools/verification/root_cause_proof_policy_snapshot.py",
)


def _normalise_rel(path: str) -> str:
    return str(path or "").replace("\\", "/")


def _hash_file_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    digest = hashlib.sha256()
    missing: list[str] = []
    files: list[dict[str, Any]] = []
    for entry in entries:
        rel = _normalise_rel(str(entry.get("path") or ""))
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        item = dict(entry)
        item["path"] = rel
        if not item.get("exists"):
            digest.update(b"MISSING")
            missing.append(rel)
        else:
            digest.update(str(item.get("sha256") or "").encode("ascii", errors="ignore"))
        digest.update(b"\0")
        files.append(item)
    return {
        "algorithm": "sha256",
        "fingerprint": digest.hexdigest(),
        "files": files,
        "missing": missing,
    }


def _compute_file_entries(root: Path, rels: tuple[str, ...]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for rel in tuple(_normalise_rel(item) for item in rels):
        path = root / rel
        if not path.exists():
            files.append({"path": rel, "exists": False, "sha256": None, "size": None})
            continue
        data = path.read_bytes()
        files.append(
            {
                "path": rel,
                "exists": True,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    return files


def _compute_tier_fingerprint(root: Path, rels: tuple[str, ...], *, tier: str) -> dict[str, Any]:
    result = _hash_file_entries(_compute_file_entries(root, rels))
    result["tier"] = tier
    return result


def _current_correctness_fingerprint_files(root: Path) -> tuple[str, ...]:
    """Return the source surface that can change a release-gate result.

    The original correctness list predated the extracted Design Brain and
    coordinator modules. Keeping it static allowed a live artifact to remain
    hash-compatible after those modules changed. Include the runtime-owned
    Python/contract files and verifier implementations so same-run binding is
    also source-complete.
    """

    files = set(CORRECTNESS_FINGERPRINT_FILES)
    files.update(
        {
            "design_guide_page.py",
            "inputs_page_app_contracts.py",
            "tools/verification/release_gate_manifest.json",
        }
    )
    for directory in (
        "design_brain",
        "application",
        "inputs_application",
        "inputs_page_modules",
        "ui",
        "tools/verification",
    ):
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".json"}:
                continue
            files.add(path.relative_to(root).as_posix())
    return tuple(sorted(files))


def derive_tier_fingerprint_from_report_source(
    report_source_fingerprint: dict[str, Any],
    tier_files: tuple[str, ...],
    *,
    tier: str,
) -> dict[str, Any] | None:
    """Derive a tier hash from old monolithic reports that stored per-file hashes."""
    source_files = {
        _normalise_rel(str(item.get("path") or "")): dict(item)
        for item in list((report_source_fingerprint or {}).get("files") or [])
        if isinstance(item, dict)
    }
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in tuple(_normalise_rel(item) for item in tier_files):
        if rel not in source_files:
            missing.append(rel)
            continue
        entries.append(source_files[rel])
    if missing:
        return None
    result = _hash_file_entries(entries)
    result["tier"] = tier
    result["derived_from_legacy_source_fingerprint"] = True
    return result


def compare_report_correctness_fingerprint(payload: dict[str, Any], *, repo: Path | None = None) -> dict[str, Any]:
    current = compute_source_fingerprint(repo=repo)
    report_correctness = dict(payload.get("correctness_fingerprint") or {})
    if not report_correctness.get("fingerprint"):
        report_correctness = derive_tier_fingerprint_from_report_source(
            dict(payload.get("source_fingerprint") or {}),
            _current_correctness_fingerprint_files((repo or REPO).resolve()),
            tier="correctness",
        ) or {}
    if not report_correctness.get("fingerprint"):
        return {
            "matches": False,
            "invalidation_reason": "report_missing_correctness_fingerprint",
            "full_gate_required": True,
            "report_correctness_fingerprint": report_correctness or None,
            "current_correctness_fingerprint": current.get("correctness_fingerprint"),
            "current_fingerprints": current,
        }
    current_correctness = dict(current.get("correctness_fingerprint") or {})
    matches = report_correctness.get("fingerprint") == current_correctness.get("fingerprint")
    return {
        "matches": bool(matches),
        "invalidation_reason": None if matches else "correctness_fingerprint_changed",
        "full_gate_required": not bool(matches),
        "report_correctness_fingerprint": report_correctness,
        "current_correctness_fingerprint": current_correctness,
        "diagnostic_fingerprint_matches": (
            dict(payload.get("diagnostic_fingerprint") or {}).get("fingerprint")
            == dict(current.get("diagnostic_fingerprint") or {}).get("fingerprint")
            if payload.get("diagnostic_fingerprint")
            else None
        ),
        "verifier_runtime_fingerprint_matches": (
            dict(payload.get("verifier_runtime_fingerprint") or {}).get("fingerprint")
            == dict(current.get("verifier_runtime_fingerprint") or {}).get("fingerprint")
            if payload.get("verifier_runtime_fingerprint")
            else None
        ),
        "current_fingerprints": current,
    }


@lru_cache(maxsize=4)
def _compute_source_fingerprint_cached(root_text: str) -> dict[str, Any]:
    """Compute one immutable fingerprint per verifier/application process."""

    root = Path(root_text)
    result = _hash_file_entries(_compute_file_entries(root, SOURCE_FINGERPRINT_FILES))
    result["tier"] = "legacy_full_source"
    result["correctness_fingerprint"] = _compute_tier_fingerprint(
        root,
        _current_correctness_fingerprint_files(root),
        tier="correctness",
    )
    result["diagnostic_fingerprint"] = _compute_tier_fingerprint(
        root,
        DIAGNOSTIC_FINGERPRINT_FILES,
        tier="diagnostic",
    )
    result["verifier_runtime_fingerprint"] = _compute_tier_fingerprint(
        root,
        VERIFIER_RUNTIME_FINGERPRINT_FILES,
        tier="verifier_runtime",
    )
    result["fingerprint_tiers"] = {
        "correctness": result["correctness_fingerprint"],
        "diagnostic": result["diagnostic_fingerprint"],
        "verifier_runtime": result["verifier_runtime_fingerprint"],
    }
    return result


def compute_source_fingerprint(*, repo: Path | None = None) -> dict[str, Any]:
    """Return the process-stable fingerprint for the current source tree.

    Verification runs execute in fresh processes, so this cache cannot make a
    later run accept an earlier source tree. It only prevents repeated reruns
    of the same Streamlit process from hashing thousands of files again.
    """

    root = (repo or REPO).resolve()
    return _compute_source_fingerprint_cached(str(root))
