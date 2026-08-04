"""Field-level Design Guide publication hash diff snapshot.

Proof-only. This verifier compares the final publication/debug surfaces before
and after a same-input reload when the input fingerprint is stable but
publication/display hashes change. It identifies whether the changing fields
are product truth or derived proof/debug/compatibility metadata.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verification.design_guide_rerun_trigger_source_profile import (  # noqa: E402
    DEFAULT_RECIPE,
    _best_browser_state,
    _extract_hashes,
    _hash_value_digests,
    _query,
    _start_streamlit,
    _stable_hash,
    _stable_json,
    _wait_for_http,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

PRODUCT_TRUTH_KEYS = {
    "selected_family",
    "selected_family_id",
    "outcome_state",
    "title",
    "status",
    "badge",
    "summary",
    "blocker_reason",
    "publication_reason",
    "enabled",
    "actionable",
    "action_type",
    "updates",
    "candidate_search_evidence",
    "exact_stop_proof",
    "target_band_proof",
    "published_item_id",
    "post_click_design_guide_state",
}

VOLATILE_FRAGMENTS = (
    "hash",
    "memo_cache",
    "bypass",
    "trace",
    "timestamp",
    "elapsed_ms",
    "duration_ms",
    "perf",
    "generated_at",
    "actual_card_render_probe",
    "legacy_publication_session_key_metadata",
    "duplicate_stamp",
    "compatibility",
    "controller_publication_authority",
    "final_visible_resolution_adapter",
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _compact(value: Any, *, depth: int = 4, max_items: int = 20) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list, tuple, set)):
            return f"<{type(value).__name__}>"
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                out["..."] = f"{len(value) - max_items} more"
                break
            out[str(key)] = _compact(item, depth=depth - 1, max_items=max_items)
        return out
    if isinstance(value, (list, tuple, set)):
        seq = list(value)
        out = [_compact(item, depth=depth - 1, max_items=max_items) for item in seq[:max_items]]
        if len(seq) > max_items:
            out.append(f"... {len(seq) - max_items} more")
        return out
    return value


def _debug_bundle(state: dict[str, Any]) -> dict[str, Any]:
    return dict(((state.get("design_guide_probe") or {}).get("debug_bundle")) or {})


def _publication_surfaces(state: dict[str, Any]) -> dict[str, Any]:
    bundle = _debug_bundle(state)
    verifier = dict(bundle.get("final_publication_verifier_payload") or {})
    return {
        "debug_bundle_hashes": _extract_hashes(state),
        "final_publication_verifier_payload": verifier,
        "displayed_primary_button_contract": dict(
            bundle.get("displayed_primary_button_contract")
            or bundle.get("primary_button_contract")
            or bundle.get("button_contract")
            or {}
        ),
        "display_truth": {
            key: bundle.get(key)
            for key in (
                "primary_card_title",
                "primary_status",
                "primary_card_intent",
                "primary_displayed_util",
                "primary_display_truth_source",
                "final_publication_display_hash",
                "final_publication_authority_hash",
                "publication_hash",
            )
        },
        "controller": {
            key: bundle.get(key)
            for key in sorted(bundle)
            if str(key).startswith("design_guide_controller_publication_authority")
            or str(key).startswith("controller_publication_authority")
        },
        "duplicate_stamp_state": {
            "decisions": _compact(bundle.get("final_publication_duplicate_stamp_bypass_decisions"), depth=3),
            "state": _compact(bundle.get("final_publication_duplicate_stamp_bypass_state"), depth=3),
        },
    }


def _value_digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _is_volatile_path(path: str) -> bool:
    lower = path.lower()
    return any(fragment in lower for fragment in VOLATILE_FRAGMENTS)


def _is_product_truth_path(path: str) -> bool:
    parts = [part for part in path.replace("[", ".").replace("]", "").split(".") if part]
    return any(part in PRODUCT_TRUTH_KEYS for part in parts)


def _diff(left: Any, right: Any, *, prefix: str = "$", depth: int = 8, limit: int = 160) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if depth < 0:
        if _value_digest(left) == _value_digest(right):
            return []
        return [
            {
                "path": prefix,
                "kind": "changed_beyond_depth",
                "left_hash": _value_digest(left),
                "right_hash": _value_digest(right),
            }
        ]
    if isinstance(left, dict) and isinstance(right, dict):
        rows: list[dict[str, Any]] = []
        keys = sorted(set(left) | set(right), key=str)
        for key in keys:
            if len(rows) >= limit:
                break
            child_path = f"{prefix}.{key}"
            if key not in left:
                rows.append(
                    {
                        "path": child_path,
                        "kind": "added",
                        "left_hash": None,
                        "right_hash": _value_digest(right.get(key)),
                        "volatile": _is_volatile_path(child_path),
                        "product_truth": _is_product_truth_path(child_path),
                        "right_preview": str(right.get(key))[:220],
                    }
                )
            elif key not in right:
                rows.append(
                    {
                        "path": child_path,
                        "kind": "removed",
                        "left_hash": _value_digest(left.get(key)),
                        "right_hash": None,
                        "volatile": _is_volatile_path(child_path),
                        "product_truth": _is_product_truth_path(child_path),
                        "left_preview": str(left.get(key))[:220],
                    }
                )
            else:
                rows.extend(_diff(left.get(key), right.get(key), prefix=child_path, depth=depth - 1, limit=limit - len(rows)))
        return rows[:limit]
    if isinstance(left, list) and isinstance(right, list):
        if _value_digest(left) == _value_digest(right):
            return []
        return [
            {
                "path": prefix,
                "kind": "list_changed",
                "left_hash": _value_digest(left),
                "right_hash": _value_digest(right),
                "volatile": _is_volatile_path(prefix),
                "product_truth": _is_product_truth_path(prefix),
                "left_len": len(left),
                "right_len": len(right),
            }
        ]
    if left == right:
        return []
    return [
        {
            "path": prefix,
            "kind": "changed",
            "left_hash": _value_digest(left),
            "right_hash": _value_digest(right),
            "volatile": _is_volatile_path(prefix),
            "product_truth": _is_product_truth_path(prefix),
            "left_preview": str(left)[:220],
            "right_preview": str(right)[:220],
        }
    ]


def _capture(base_url: str, *, recipe: str, headed: bool) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.set_default_timeout(30_000)
        url = _query(base_url, {"page": "inputs", "browser_recipe": recipe})
        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3500)
        before_state = _best_browser_state(page, recipe, timeout_s=10.0)
        page.reload(wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_timeout(3500)
        after_state = _best_browser_state(page, recipe, timeout_s=10.0)
        browser.close()
    return {
        "url": url,
        "recipe": recipe,
        "before": _publication_surfaces(before_state),
        "after": _publication_surfaces(after_state),
    }


def _classify(capture: dict[str, Any]) -> dict[str, Any]:
    before = dict(capture.get("before") or {})
    after = dict(capture.get("after") or {})
    diff_rows = _diff(before, after, depth=8, limit=220)
    product_rows = [row for row in diff_rows if row.get("product_truth") and not row.get("volatile")]
    volatile_rows = [row for row in diff_rows if row.get("volatile")]
    unknown_rows = [
        row
        for row in diff_rows
        if not row.get("volatile") and not row.get("product_truth")
    ]

    before_hashes = before.get("debug_bundle_hashes") or {}
    after_hashes = after.get("debug_bundle_hashes") or {}
    compared_hashes = {}
    for key in sorted(set(before_hashes) | set(after_hashes)):
        left_values = _hash_value_digests({"hashes": before_hashes}, key)
        right_values = _hash_value_digests({"hashes": after_hashes}, key)
        if left_values or right_values:
            compared_hashes[key] = {
                "before": left_values[:6],
                "after": right_values[:6],
                "matches": bool(set(left_values) & set(right_values)) if left_values and right_values else left_values == right_values,
            }

    if product_rows:
        diagnosis = "PRODUCT_TRUTH_FIELD_CHANGES"
        next_slice = "Trace the changing product field back to its controller request input before memoization."
    elif unknown_rows:
        diagnosis = "UNKNOWN_NON_VOLATILE_FIELD_CHANGES"
        next_slice = "Classify the remaining non-volatile changed fields as product truth or proof/debug before any bypass."
    else:
        diagnosis = "VOLATILE_PROOF_DEBUG_FIELDS_ONLY"
        next_slice = "Add proof that volatile proof/debug fields are excluded from authority hashes or memo request keys."

    return {
        "status": "PASS",
        "diagnosis": diagnosis,
        "changed_row_count": len(diff_rows),
        "volatile_row_count": len(volatile_rows),
        "product_truth_row_count": len(product_rows),
        "unknown_row_count": len(unknown_rows),
        "compared_hashes": compared_hashes,
        "changed_rows": diff_rows[:80],
        "recommended_next_slice": next_slice,
    }


def _markdown(payload: dict[str, Any]) -> str:
    cls = dict(payload.get("classification") or {})
    lines = [
        "# Design Guide Publication Hash Diff Snapshot",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnosis: `{cls.get('diagnosis')}`",
        f"- Product behaviour changed: `{payload.get('product_behaviour_changed')}`",
        f"- Changed rows: `{cls.get('changed_row_count')}`",
        f"- Volatile rows: `{cls.get('volatile_row_count')}`",
        f"- Product-truth rows: `{cls.get('product_truth_row_count')}`",
        f"- Unknown rows: `{cls.get('unknown_row_count')}`",
        "",
        "## Next Safe Slice",
        "",
        str(cls.get("recommended_next_slice") or ""),
        "",
        "## Changed Rows",
        "",
        "| Path | Kind | Volatile | Product truth |",
        "|---|---|---:|---:|",
    ]
    for row in cls.get("changed_rows") or []:
        lines.append(
            f"| {str(row.get('path')).replace('|', '\\|')} | {row.get('kind')} | "
            f"{row.get('volatile')} | {row.get('product_truth')} |"
        )
    return "\n".join(lines) + "\n"


def _write(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(payload["created_at"])
    json_path = ARTIFACT_DIR / f"design_guide_publication_hash_diff_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_publication_hash_diff_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8615)
    parser.add_argument("--base-url", default=os.environ.get("DESIGN_GUIDE_PUBLICATION_HASH_DIFF_URL"))
    parser.add_argument("--recipe", default=DEFAULT_RECIPE)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args(argv)

    process: subprocess.Popen | None = None
    base_url = str(args.base_url or f"http://localhost:{args.port}")
    created_at = _stamp()
    try:
        if not args.base_url:
            env_before = dict(os.environ)
            os.environ["CODEX_BROWSER_TEST_MODE"] = "1"
            try:
                process = _start_streamlit(args.port)
            finally:
                os.environ.clear()
                os.environ.update(env_before)
            _wait_for_http(base_url, timeout_s=70.0)
        capture = _capture(base_url, recipe=str(args.recipe), headed=bool(args.headed))
        classification = _classify(capture)
        payload = {
            "schema": "design_guide_publication_hash_diff_snapshot.v1",
            "created_at": created_at,
            "status": classification.get("status"),
            "product_behaviour_changed": False,
            "base_url": base_url,
            "classification": classification,
            "snapshot_hash": _stable_hash({"capture": capture, "classification": classification}),
            **capture,
        }
        json_path, md_path = _write(payload)
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "diagnosis": classification.get("diagnosis"),
                    "product_truth_row_count": classification.get("product_truth_row_count"),
                    "unknown_row_count": classification.get("unknown_row_count"),
                    "recommended_next_slice": classification.get("recommended_next_slice"),
                },
                indent=2,
            )
        )
        return 0 if payload["status"] == "PASS" else 1
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except Exception:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
