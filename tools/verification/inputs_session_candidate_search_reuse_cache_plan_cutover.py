from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_page_modules.session import (
    build_inputs_candidate_search_reuse_key_hash,
    build_inputs_candidate_search_reuse_lookup_result,
    build_inputs_candidate_search_reuse_store_plan,
)


def _old_key(value):
    try:
        raw = json.dumps(value, sort_keys=True, default=str)
    except Exception:
        raw = repr(value)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _old_lookup(cache, key_hash):
    row = dict(dict(cache or {}).get(key_hash) or {})
    payload = row.get("payload")
    if not isinstance(payload, dict):
        return None
    out = copy.deepcopy(payload)
    debug_trace = dict(out.get("debug_trace") or {})
    debug_trace["candidate_search_reuse_decision"] = {
        "decision": "REUSE_HIT",
        "reason": "stable_no_input_reuse_key_unchanged",
        "key_hash": key_hash,
        "source": "design_guide_candidate_search_reuse_cache",
    }
    debug_trace["candidate_search_reuse_cache_hit"] = True
    out["debug_trace"] = debug_trace
    return out


def _old_store(cache, key_hash, payload, recorded_at, limit):
    cache_out = dict(cache or {})
    store_payload = copy.deepcopy(payload)
    debug_trace = dict(store_payload.get("debug_trace") or {})
    debug_trace["candidate_search_reuse_recorded"] = True
    debug_trace["candidate_search_reuse_key_hash"] = key_hash
    debug_trace["candidate_search_reuse_policy"] = "stable_no_input_same_key_only"
    store_payload["debug_trace"] = debug_trace
    cache_out[key_hash] = {
        "payload": store_payload,
        "recorded_at": recorded_at,
        "policy": "stable_no_input_same_key_only",
    }
    if len(cache_out) > limit:
        ordered = sorted(cache_out.items(), key=lambda item: float(dict(item[1] or {}).get("recorded_at") or 0.0))
        cache_out = dict(ordered[-limit:])
    return cache_out


def main() -> int:
    inputs = (ROOT / "inputs_page.py").read_text(encoding="utf-8")
    builders = (ROOT / "inputs_page_modules" / "session" / "builders.py").read_text(encoding="utf-8")
    init_text = (ROOT / "inputs_page_modules" / "session" / "__init__.py").read_text(encoding="utf-8")
    failures = []
    scenarios = []

    for name, value in (("dict", {"b": 2, "a": 1}), ("tuple", ("x", 3)), ("none", None)):
        new_hash = build_inputs_candidate_search_reuse_key_hash(value)
        scenarios.append({"name": f"key:{name}", "match": new_hash == _old_key(value)})

    key_hash = build_inputs_candidate_search_reuse_key_hash({"state": 1})
    cached_payload = {"items": [{"id": "a"}], "debug_trace": {"existing": True}}
    cache = {key_hash: {"payload": cached_payload, "recorded_at": 1.0}}
    lookup = build_inputs_candidate_search_reuse_lookup_result(cache=cache, key_hash=key_hash)
    scenarios.append(
        {
            "name": "lookup_hit",
            "match": lookup.cache_hit and lookup.payload == _old_lookup(cache, key_hash),
        }
    )
    miss = build_inputs_candidate_search_reuse_lookup_result(cache=cache, key_hash="missing")
    scenarios.append({"name": "lookup_miss", "match": not miss.cache_hit and miss.payload is None})

    old_cache = {
        f"k{i}": {"payload": {"i": i}, "recorded_at": float(i), "policy": "stable_no_input_same_key_only"}
        for i in range(6)
    }
    payload = {"items": [{"id": "new"}], "debug_trace": {"before": 1}}
    plan = build_inputs_candidate_search_reuse_store_plan(
        cache=old_cache,
        key_hash="new",
        payload=payload,
        recorded_at=10.0,
        cache_limit=6,
    )
    scenarios.append(
        {
            "name": "store_and_bound",
            "match": plan.stored and plan.cache == _old_store(old_cache, "new", payload, 10.0, 6),
        }
    )
    if not all(row["match"] for row in scenarios):
        failures.append("cache plan parity failed")

    key_start = inputs.index("def _design_guide_candidate_search_reuse_key_hash")
    stale_start = inputs.index("def _design_guide_candidate_search_reuse_stale_apply_reason", key_start)
    get_start = inputs.index("def _design_guide_candidate_search_reuse_get", stale_start)
    store_start = inputs.index("def _design_guide_candidate_search_reuse_store", get_start)
    finalize_start = inputs.index("def _finalize_compute_design_guidance_items_output", store_start)
    key_body = inputs[key_start:stale_start]
    get_body = inputs[get_start:store_start]
    store_body = inputs[store_start:finalize_start]
    if "build_inputs_candidate_search_reuse_key_hash(" not in key_body:
        failures.append("page key helper does not delegate")
    if "build_inputs_candidate_search_reuse_lookup_result(" not in get_body:
        failures.append("page lookup helper does not delegate")
    if "build_inputs_candidate_search_reuse_store_plan(" not in store_body:
        failures.append("page store helper does not delegate")
    for snippet in ("copy.deepcopy(payload)", "cache[key_hash] =", "ordered = sorted("):
        if snippet in get_body or snippet in store_body:
            failures.append(f"old page-owned cache materialization remains: {snippet}")
    if "st.session_state" in builders or "import streamlit" in builders or "import inputs_page" in builders:
        failures.append("session builder imports or reads forbidden page/UI state")
    for name in (
        "build_inputs_candidate_search_reuse_key_hash",
        "build_inputs_candidate_search_reuse_lookup_result",
        "build_inputs_candidate_search_reuse_store_plan",
    ):
        if name not in init_text:
            failures.append(f"session builder is not exported: {name}")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    decision = "INPUTS_SESSION_CANDIDATE_SEARCH_REUSE_CACHE_PLAN_LOCKED" if not failures else "FAIL"
    result = {
        "audit": "inputs_session_candidate_search_reuse_cache_plan_cutover",
        "timestamp": timestamp,
        "decision": decision,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "session_read_write_ownership_moved": False,
        "scenarios": scenarios,
        "failures": failures,
    }
    verification_dir = ROOT / "artifacts" / "verification"
    audit_dir = ROOT / "artifacts" / "audits"
    verification_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = verification_dir / f"inputs_session_candidate_search_reuse_cache_plan_{timestamp}.json"
    report_path = audit_dir / f"inputs_session_candidate_search_reuse_cache_plan_{timestamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Session Candidate Search Reuse Cache Plan Cutover",
                "",
                f"Decision: `{decision}`",
                "",
                f"Scenarios checked: `{len(scenarios)}`",
                f"Failures: `{len(failures)}`",
                "",
                "The session module owns key hashing, lookup projection, hit stamping, and bounded store planning.",
                "`inputs_page.py` still owns session cache reads/writes, timestamps, diagnostics, and exception handling.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(decision)
    print(json_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
