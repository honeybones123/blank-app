"""Readiness proof for excluding volatile Design Guide publication fields.

Proof-only. This consumes the latest field-level publication hash-diff artifact
and proves whether removing volatile proof/debug/timing/hash fields would leave
the same canonical publication truth across a same-input reload.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_publication_hash_diff_snapshot import (  # noqa: E402
    VOLATILE_FRAGMENTS,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _latest(prefix: str) -> Path | None:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    return paths[-1] if paths else None


def _is_volatile(path: str) -> bool:
    lower = path.lower()
    return any(fragment in lower for fragment in VOLATILE_FRAGMENTS)


def _canonicalize(value: Any, *, path: str = "$") -> Any:
    if _is_volatile(path):
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in sorted(value.items(), key=lambda item: str(item[0])):
            child_path = f"{path}.{key}"
            if _is_volatile(child_path):
                continue
            canonical = _canonicalize(child, path=child_path)
            if canonical in (None, {}, []):
                continue
            out[str(key)] = canonical
        return out
    if isinstance(value, list):
        return [
            canonical
            for index, child in enumerate(value)
            if (canonical := _canonicalize(child, path=f"{path}[{index}]")) not in (None, {}, [])
        ]
    return value


def _surface(payload: dict[str, Any], key: str) -> Any:
    value = dict(payload or {}).get(key)
    return value if value is not None else {}


def _compare(before: dict[str, Any], after: dict[str, Any], key: str) -> dict[str, Any]:
    before_canonical = _canonicalize(_surface(before, key), path=f"$.{key}")
    after_canonical = _canonicalize(_surface(after, key), path=f"$.{key}")
    before_hash = _stable_hash(before_canonical)
    after_hash = _stable_hash(after_canonical)
    return {
        "surface": key,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "matches_after_volatility_exclusion": before_hash == after_hash,
        "before_preview": before_canonical,
        "after_preview": after_canonical,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Publication Volatility Exclusion Readiness Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Ready for implementation: `{cls.get('ready_for_volatility_exclusion')}`",
        f"- Source diff artifact: `{payload.get('source_diff_artifact')}`",
        "",
        "## Surface Comparison",
        "",
        "| Surface | Matches after exclusion |",
        "|---|---:|",
    ]
    for row in cls.get("surface_comparisons") or []:
        lines.append(f"| {row.get('surface')} | {row.get('matches_after_volatility_exclusion')} |")
    lines.extend(["", "## Next Safe Slice", "", str(cls.get("recommended_next_slice") or "")])
    return "\n".join(lines) + "\n"


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source_path = _latest("design_guide_publication_hash_diff")
    stamp = _stamp()
    failures: list[str] = []
    if source_path is None:
        payload = {
            "schema": "design_guide_publication_volatility_exclusion_readiness.v1",
            "created_at": stamp,
            "status": "FAIL",
            "product_behaviour_changed": False,
            "source_diff_artifact": None,
            "classification": {
                "diagnosis": "MISSING_HASH_DIFF_ARTIFACT",
                "ready_for_volatility_exclusion": False,
                "recommended_next_slice": "Run design_guide_publication_hash_diff_snapshot.py first.",
                "surface_comparisons": [],
            },
            "failures": ["missing_hash_diff_artifact"],
        }
    else:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        before = dict(source.get("before") or {})
        after = dict(source.get("after") or {})
        source_cls = dict(source.get("classification") or {})
        comparisons = [
            _compare(before, after, "final_publication_verifier_payload"),
            _compare(before, after, "displayed_primary_button_contract"),
            _compare(before, after, "display_truth"),
            _compare(before, after, "controller"),
        ]
        mismatches = [row for row in comparisons if not row.get("matches_after_volatility_exclusion")]
        source_clean = (
            source.get("status") == "PASS"
            and source_cls.get("diagnosis") == "VOLATILE_PROOF_DEBUG_FIELDS_ONLY"
            and int(source_cls.get("product_truth_row_count") or 0) == 0
            and int(source_cls.get("unknown_row_count") or 0) == 0
        )
        if not source_clean:
            failures.append("source_diff_not_volatile_only")
        if mismatches:
            failures.append("canonical_surfaces_still_differ")
        ready = not failures
        payload = {
            "schema": "design_guide_publication_volatility_exclusion_readiness.v1",
            "created_at": stamp,
            "status": "PASS" if ready else "FAIL",
            "product_behaviour_changed": False,
            "source_diff_artifact": str(source_path),
            "classification": {
                "diagnosis": "READY_VOLATILE_FIELDS_CAN_BE_EXCLUDED" if ready else "NOT_READY",
                "ready_for_volatility_exclusion": ready,
                "source_diff_diagnosis": source_cls.get("diagnosis"),
                "surface_comparisons": comparisons,
                "mismatch_count": len(mismatches),
                "recommended_next_slice": (
                    "Implement a narrow canonicalization/exclusion of volatile proof/debug/timing fields before FinalDesignGuidePublication authority hashing."
                    if ready
                    else "Resolve remaining canonical mismatches before changing hash behavior."
                ),
            },
            "failures": failures,
            "snapshot_hash": _stable_hash({"source": str(source_path), "comparisons": comparisons, "failures": failures}),
        }
    json_path = ARTIFACT_DIR / f"design_guide_publication_volatility_exclusion_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_volatility_exclusion_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(f"design_guide_publication_volatility_exclusion_readiness {payload['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    print(json.dumps(payload["classification"], indent=2, sort_keys=True, default=str)[:4000])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
