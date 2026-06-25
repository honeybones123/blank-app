"""Proof-only snapshot for remaining Design Guide resolver authority bridges.

The snapshot compares the four remaining live restamper/resolve authority
bridges against FinalDesignGuidePublication authority surfaces. It is static
and proof-only: no product path is executed and no behaviour is changed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import ast
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

EXPECTED_BRIDGES = {
    "compute_stage_final_visible_resolver": {
        "line_source": "final_compute_resolution = resolve_final_visible_design_guide_item(",
        "function": "_resolve_compute_design_guidance_publication_handoff",
        "target": "resolve_final_visible_design_guide_item",
        "truth_owner": "compute-stage visible item selection",
        "future_owner": "FinalDesignGuidePublication plus Design Brain publication resolver",
        "unique_truth": [
            "chooses collapsed guidance item",
            "sets compute render reason",
            "restamps selected_title/action/family debug fields",
        ],
        "missing_proof": [
            "same-object resolver parity against FinalDesignGuidePublication",
            "collapsed_guidance_items replacement derived from publication object",
            "debug selected fields marked non-authoritative",
        ],
    },
    "compute_late_evidence_contract_rebound": {
        "line_source": "_late_rebound_item = _publish_final_visible_design_guide_contract_binding(",
        "function": "_apply_compute_late_evidence_contract_rebound",
        "target": "_publish_final_visible_design_guide_contract_binding",
        "truth_owner": "compute-stage late evidence CTA/action rebound",
        "future_owner": "Design Brain engine evidence handoff plus FinalDesignGuidePublication",
        "unique_truth": [
            "accepts late evidence updates",
            "replaces primary item and collapsed guidance item",
            "sets compute-stage button contract/action debug fields",
        ],
        "missing_proof": [
            "late evidence rebound input/output snapshot",
            "rebound CTA hash parity with FinalDesignGuidePublication.cta",
            "collapsed guidance mutation is publication-derived",
        ],
    },
    "post_core_evidence_rebound": {
        "line_source": "_post_evidence_rebound = _publish_final_visible_design_guide_contract_binding(",
        "function": "_orchestrate_compute_post_core_publication_handoff",
        "target": "_publish_final_visible_design_guide_contract_binding",
        "truth_owner": "post-core evidence rebound before compute publication handoff",
        "future_owner": "Design Brain engine post-core reconciliation plus FinalDesignGuidePublication",
        "unique_truth": [
            "rewrites collapsed guidance item after post-core evidence",
            "marks post evidence cleanup rebound",
            "feeds mutated item into compute resolver",
        ],
        "missing_proof": [
            "post-core rebound accepted/skipped snapshot",
            "same-object publication compatibility before resolver",
            "no alternate family/item selection compared with Design Brain engine decision",
        ],
    },
    "render_stage_final_visible_resolver": {
        "line_source": "_final_visible_resolution = resolve_final_visible_design_guide_item(",
        "function": "_render_fast_design_guidance_panel",
        "target": "resolve_final_visible_design_guide_item",
        "truth_owner": "render-stage final visible item selection",
        "future_owner": "FinalDesignGuidePublication",
        "unique_truth": [
            "chooses render-stage final visible item",
            "sets final render reason",
            "feeds final render model and later exact-blocker adjustment paths",
        ],
        "missing_proof": [
            "render resolver same-object proof against FinalDesignGuidePublication",
            "proof render input list cannot override publication object",
            "zero-shear/exact-blocker adjustments represented in publication evidence",
        ],
    },
}


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
        "stdout_tail": proc.stdout.strip().splitlines()[-10:],
        "stderr_tail": proc.stderr.strip().splitlines()[-10:],
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


def _line_for_source(source: str, needle: str, *, function_hint: str | None = None) -> int | None:
    lines = source.splitlines()
    function_range: tuple[int, int] | None = None
    if function_hint:
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_hint:
                    function_range = (int(node.lineno), int(getattr(node, "end_lineno", node.lineno)))
                    break
        except SyntaxError:
            function_range = None
    for index, line in enumerate(lines, start=1):
        if needle not in line:
            continue
        if function_range:
            if not (function_range[0] <= index <= function_range[1]):
                continue
        return index
    return None


def _context(source: str, line: int | None, radius: int = 24) -> str:
    if line is None:
        return ""
    lines = source.splitlines()
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(lines[start - 1 : end])


def _surface_hash(context: str, tokens: tuple[str, ...]) -> str | None:
    lines = [
        line.strip()
        for line in context.splitlines()
        if any(token in line for token in tokens)
    ]
    if not lines:
        return None
    return _stable_hash(lines)


def _bridge_surface(bridge_id: str, spec: dict[str, Any], source: str) -> dict[str, Any]:
    line = _line_for_source(source, str(spec["line_source"]), function_hint=str(spec["function"]))
    context = _context(source, line)
    final_publication_markers = {
        "final_publication_authority_hash": "final_publication_authority_hash" in context,
        "publication_hash": "publication_hash" in context,
        "compatibility_only_callsite": "compatibility_only_callsite" in context,
        "FinalDesignGuidePublication": "FinalDesignGuidePublication" in context,
    }
    button_contract_hash = _surface_hash(
        context,
        ("button_contract", "_contract", "contract_updates", "button_contract_enabled"),
    )
    display_hash = _surface_hash(
        context,
        ("selected_title", "render_reason", "guidance_items", "visible_guidance_items", "title"),
    )
    blocker_hash = _surface_hash(
        context,
        (
            "exact_blockers_by_family",
            "post_click_exact_blockers_by_family",
            "candidate_search_evidence",
            "blocker",
        ),
    )
    selected_family_hash = _surface_hash(
        context,
        ("selected_action_family", "family", "check_key"),
    )
    outcome_hash = _surface_hash(
        context,
        ("render_reason", "guidance_branch", "button_contract_enabled", "design_guide_terminal_state"),
    )
    publication_hash = _surface_hash(
        context,
        ("_record_design_guide_publication_snapshot", "publication_context", "final_visible_resolution"),
    )
    authority_hash = _stable_hash(
        {
            "bridge_id": bridge_id,
            "context_hash": _stable_hash(context),
            "button_contract_hash": button_contract_hash,
            "display_hash": display_hash,
            "blocker_hash": blocker_hash,
            "selected_family_hash": selected_family_hash,
            "outcome_hash": outcome_hash,
        }
    )
    matches_final_publication = bool(
        final_publication_markers["final_publication_authority_hash"]
        and final_publication_markers["publication_hash"]
        and final_publication_markers["compatibility_only_callsite"]
    )
    still_adds_unique_truth = not matches_final_publication
    return {
        "bridge_id": bridge_id,
        "location": None if line is None else f"inputs_page.py:{line}",
        "function": spec["function"],
        "symbol": spec["target"],
        "decision_truth_owned": spec["truth_owner"],
        "selected_family": {
            "source": "dynamic source context",
            "hash": selected_family_hash,
        },
        "outcome_state": {
            "source": "dynamic source context",
            "hash": outcome_hash,
        },
        "button_contract_cta_hash": button_contract_hash,
        "display_card_hash": display_hash,
        "blocker_evidence_hash": blocker_hash,
        "publication_hash": publication_hash,
        "authority_hash": authority_hash,
        "final_design_guide_publication_markers": final_publication_markers,
        "matches_final_design_guide_publication": matches_final_publication,
        "still_adds_unique_truth": still_adds_unique_truth,
        "unique_truth": list(spec["unique_truth"]),
        "recommended_future_owner": spec["future_owner"],
        "missing_proof_before_narrowing": list(spec["missing_proof"]),
        "future_classification": "live authority bridge" if still_adds_unique_truth else "future compatibility stamp",
        "can_narrow_now": False,
        "deletion_candidate": False,
        "context_hash": _stable_hash(context),
    }


def _final_publication_baseline() -> dict[str, Any]:
    source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    required_tokens = {
        "FinalDesignGuidePublication": "class FinalDesignGuidePublication" in source,
        "FinalDesignGuideCTA": "class FinalDesignGuideCTA" in source,
        "FinalDesignGuideDisplay": "class FinalDesignGuideDisplay" in source,
        "stable_hash": "def stable_final_publication_hash" in source,
        "publication_builder": "def build_final_design_guide_publication" in source,
    }
    return {
        "module": "design_brain/final_publication.py",
        "required_tokens": required_tokens,
        "baseline_hash": _stable_hash(
            {
                "required_tokens": required_tokens,
                "source_hash": _stable_hash(source),
            }
        ),
    }


def _build_snapshot() -> dict[str, Any]:
    reachability = _run("tools/verification/design_guide_duplicate_restamper_reachability_snapshot.py")
    classification = _run("tools/verification/design_guide_remaining_restamper_mutation_classification_snapshot.py")
    independence = _run("tools/verification/design_guide_independence_lock_verifier.py")
    reachability_artifact = _latest_artifact("design_guide_duplicate_restamper_reachability")
    classification_artifact = _latest_artifact("design_guide_remaining_restamper_mutation_classification")
    input_source = INPUTS_PAGE.read_text(encoding="utf-8")
    bridges = [
        _bridge_surface(bridge_id, spec, input_source)
        for bridge_id, spec in EXPECTED_BRIDGES.items()
    ]
    final_publication = _final_publication_baseline()
    failures: list[str] = []
    if not reachability["passed"]:
        failures.append("duplicate_restamper_reachability_failed")
    if not classification["passed"]:
        failures.append("remaining_restamper_classification_failed")
    if not independence["passed"]:
        failures.append("design_guide_independence_lock_failed")
    if len(bridges) != 4:
        failures.append(f"expected_4_bridges_found_{len(bridges)}")
    for bridge in bridges:
        if bridge["location"] is None:
            failures.append(f"missing_bridge_location:{bridge['bridge_id']}")
    for name, present in final_publication["required_tokens"].items():
        if not present:
            failures.append(f"missing_final_publication_token:{name}")
    unique_truth_count = sum(1 for bridge in bridges if bridge["still_adds_unique_truth"])
    if unique_truth_count != 4:
        failures.append(f"expected_4_unique_truth_bridges_found_{unique_truth_count}")
    deletion_candidates = [bridge for bridge in bridges if bridge["deletion_candidate"]]
    if deletion_candidates:
        failures.append("unexpected_deletion_candidate")

    status = "PASS" if not failures else "FAIL"
    proof_surface = {
        "bridges": bridges,
        "final_publication": final_publication,
        "reachability_artifact": reachability_artifact.get("path"),
        "classification_artifact": classification_artifact.get("path"),
    }
    return {
        "snapshot_name": "design_guide_resolver_authority_bridge_snapshot",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "final_design_guide_publication": final_publication,
        "source_reachability_artifact": reachability_artifact.get("path"),
        "source_classification_artifact": classification_artifact.get("path"),
        "bridge_count": len(bridges),
        "bridges": bridges,
        "summary": {
            "matches_final_design_guide_publication": sum(
                1 for bridge in bridges if bridge["matches_final_design_guide_publication"]
            ),
            "still_adds_unique_truth": unique_truth_count,
            "can_narrow_now": sum(1 for bridge in bridges if bridge["can_narrow_now"]),
            "deletion_candidates": len(deletion_candidates),
            "next_recommended_slice": "Add compute/render resolver same-object proof before any further narrowing.",
        },
        "verification": {
            "duplicate_restamper_reachability": reachability,
            "remaining_restamper_classification": classification,
            "design_guide_independence_lock": independence,
        },
        "product_behavior_changed": False,
        "snapshot_hash": _stable_hash(proof_surface),
        "failures": failures,
    }


def _write_markdown(snapshot: dict[str, Any], path: Path) -> None:
    bridge_rows = [
        "| `{location}` | `{function}` | `{symbol}` | `{matches}` | `{unique}` | `{narrow}` | `{delete}` |".format(
            location=bridge["location"],
            function=bridge["function"],
            symbol=bridge["symbol"],
            matches=bridge["matches_final_design_guide_publication"],
            unique=bridge["still_adds_unique_truth"],
            narrow=bridge["can_narrow_now"],
            delete=bridge["deletion_candidate"],
        )
        for bridge in snapshot["bridges"]
    ]
    details: list[str] = []
    for bridge in snapshot["bridges"]:
        details.extend(
            [
                f"### `{bridge['bridge_id']}`",
                "",
                f"Location: `{bridge['location']}`",
                f"Decision truth owned: {bridge['decision_truth_owned']}",
                f"Recommended future owner: {bridge['recommended_future_owner']}",
                f"Matches FinalDesignGuidePublication: `{bridge['matches_final_design_guide_publication']}`",
                f"Still adds unique truth: `{bridge['still_adds_unique_truth']}`",
                "",
                "Hashes:",
                f"- selected family hash: `{bridge['selected_family']['hash']}`",
                f"- outcome state hash: `{bridge['outcome_state']['hash']}`",
                f"- CTA/button contract hash: `{bridge['button_contract_cta_hash']}`",
                f"- display/card hash: `{bridge['display_card_hash']}`",
                f"- blocker evidence hash: `{bridge['blocker_evidence_hash']}`",
                f"- publication hash: `{bridge['publication_hash']}`",
                f"- authority hash: `{bridge['authority_hash']}`",
                "",
                "Unique truth:",
                *[f"- {item}" for item in bridge["unique_truth"]],
                "",
                "Missing proof before narrowing:",
                *[f"- {item}" for item in bridge["missing_proof_before_narrowing"]],
                "",
            ]
        )
    body = "\n".join(
        [
            "# Design Guide Resolver Authority Bridge Snapshot",
            "",
            f"Timestamp: `{snapshot['generated_at']}`",
            f"Result: `{snapshot['status']}`",
            f"Snapshot hash: `{snapshot['snapshot_hash']}`",
            "",
            "## Summary",
            "",
            f"- Bridge count: `{snapshot['bridge_count']}`",
            f"- Bridges matching `FinalDesignGuidePublication`: `{snapshot['summary']['matches_final_design_guide_publication']}`",
            f"- Bridges still adding unique truth: `{snapshot['summary']['still_adds_unique_truth']}`",
            f"- Can narrow now: `{snapshot['summary']['can_narrow_now']}`",
            f"- Deletion candidates: `{snapshot['summary']['deletion_candidates']}`",
            f"- Next recommended slice: {snapshot['summary']['next_recommended_slice']}",
            "",
            "## Bridge Comparison",
            "",
            "| Location | Function | Symbol | Matches Final Publication | Adds Unique Truth | Can Narrow | Delete |",
            "|---|---|---|---:|---:|---:|---:|",
            *bridge_rows,
            "",
            "## Bridge Details",
            "",
            *details,
            "## Verification",
            "",
            f"- Duplicate restamper reachability passed: `{snapshot['verification']['duplicate_restamper_reachability']['passed']}`",
            f"- Remaining restamper classification passed: `{snapshot['verification']['remaining_restamper_classification']['passed']}`",
            f"- Design Guide independence lock passed: `{snapshot['verification']['design_guide_independence_lock']['passed']}`",
            "",
            "## Scope",
            "",
            "- Product behavior changed: `False`",
            "- This snapshot is proof-only.",
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
    json_path = ARTIFACT_DIR / f"design_guide_resolver_authority_bridge_snapshot_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_resolver_authority_bridge_snapshot_{stamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(snapshot, md_path)
    print(f"design_guide_resolver_authority_bridge_snapshot {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if snapshot["failures"]:
        print("Failures:")
        for failure in snapshot["failures"]:
            print(f"- {failure}")
    return 0 if snapshot["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
