"""Design Guide executor-contract item sanitization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


_EXECUTOR_CONTRACT_SANITIZER_DEPENDENCIES: tuple[str, ...] = (
    "_evaluate_auto_design_candidate",
    "_guidance_executor_actionability_contract",
    "_guidance_item_as_advisory",
    "_guidance_state_snapshot",
    "_post_click_accepted_green_audit",
    "_resolve_recommendation_updates",
    "_try_promote_efficiency_item_to_executor_backed_candidate",
)


@dataclass(frozen=True)
class ExecutorContractSanitizerRuntime:
    evaluate_auto_design_candidate: Callable[..., Any]
    guidance_executor_actionability_contract: Callable[..., Any]
    guidance_item_as_advisory: Callable[..., Any]
    guidance_state_snapshot: Callable[..., Any]
    post_click_accepted_green_audit: Callable[..., Any]
    resolve_recommendation_updates: Callable[..., Any]
    try_promote_efficiency_item: Callable[..., Any]


def bind_executor_contract_sanitizer_dependencies(namespace: dict[str, Any]) -> None:
    globals().update(
        {
            name: namespace[name]
            for name in _EXECUTOR_CONTRACT_SANITIZER_DEPENDENCIES
            if name in namespace
        }
    )


def _sanitize_guidance_items_for_executor_contract(
    guidance_items: list[dict] | None,
    *,
    state: dict,
    debug_sink: dict | None = None,
    runtime: ExecutorContractSanitizerRuntime | None = None,
) -> list[dict]:
    if runtime is not None:
        _evaluate_auto_design_candidate = (
            runtime.evaluate_auto_design_candidate
        )
        _guidance_executor_actionability_contract = (
            runtime.guidance_executor_actionability_contract
        )
        _guidance_item_as_advisory = runtime.guidance_item_as_advisory
        _guidance_state_snapshot = runtime.guidance_state_snapshot
        _post_click_accepted_green_audit = (
            runtime.post_click_accepted_green_audit
        )
        _resolve_recommendation_updates = (
            runtime.resolve_recommendation_updates
        )
        _try_promote_efficiency_item_to_executor_backed_candidate = (
            runtime.try_promote_efficiency_item
        )
    else:
        namespace = globals()
        _evaluate_auto_design_candidate = namespace[
            "_evaluate_auto_design_candidate"
        ]
        _guidance_executor_actionability_contract = namespace[
            "_guidance_executor_actionability_contract"
        ]
        _guidance_item_as_advisory = namespace[
            "_guidance_item_as_advisory"
        ]
        _guidance_state_snapshot = namespace["_guidance_state_snapshot"]
        _post_click_accepted_green_audit = namespace[
            "_post_click_accepted_green_audit"
        ]
        _resolve_recommendation_updates = namespace[
            "_resolve_recommendation_updates"
        ]
        _try_promote_efficiency_item_to_executor_backed_candidate = (
            namespace[
                "_try_promote_efficiency_item_to_executor_backed_candidate"
            ]
        )
    out: list[dict] = []
    blocked_primary_reason: str | None = None
    promotion_debug: list[dict] = []
    for idx, item in enumerate(list(guidance_items or [])):
        if not isinstance(item, dict):
            continue
        action_type = str(item.get("action_type") or "").strip()
        if not action_type:
            out.append(item)
            continue
        allowed, reason = _guidance_executor_actionability_contract(item, state=state)
        if allowed:
            try:
                final_updates = dict(_resolve_recommendation_updates(item, state=state) or {})
            except Exception:
                final_updates = {}
            if final_updates:
                try:
                    final_candidate = _evaluate_auto_design_candidate(
                        _guidance_state_snapshot(state or {}),
                        updates=final_updates,
                        source="design_guide_sanitize_final_acceptance_probe",
                        label=str(item.get("title_main") or "Design Guide candidate"),
                        action_type=str(item.get("action_type") or "apply_resolved_candidate"),
                    )
                except Exception:
                    final_candidate = None
                if isinstance(final_candidate, dict):
                    final_state = dict(_guidance_state_snapshot(state or {}))
                    final_state.update(final_updates)
                    final_audit = _post_click_accepted_green_audit(
                        dict(final_candidate.get("overview") or {}),
                        blocker_source=dict(final_candidate),
                        state=final_state,
                    )
                    unresolved_final = list(final_audit.get("post_click_unresolved_low_util_families") or [])
                    final_overview = dict(final_candidate.get("overview") or {})
                    safe_pass_action = bool(
                        item.get("family_safe_pass_fallback")
                        and str(item.get("guidance_intent") or "").strip().lower()
                        in {
                            "required_fix",
                            "optional_cleanup",
                            "efficiency_tightening",
                        }
                        and final_overview.get("all_key_pass")
                        and not final_overview.get("any_fail")
                    )
                    if unresolved_final and not safe_pass_action:
                        promotion_debug.append(
                            {
                                "index": idx,
                                "blocked_reason": str(
                                    final_audit.get("post_click_accepted_green_invalid_reason")
                                    or "candidate_final_accepted_state_unresolved_low_util"
                                ),
                                "final_unresolved_low_util_families": list(unresolved_final),
                            }
                        )
                        out.append(
                            _guidance_item_as_advisory(
                                item,
                                blocked_reason=str(
                                    final_audit.get("post_click_accepted_green_invalid_reason")
                                    or "candidate_final_accepted_state_unresolved_low_util"
                                ),
                            )
                        )
                        continue
                    if unresolved_final and safe_pass_action:
                        item = {
                            **dict(item),
                            "post_repair_cleanup_required": True,
                            "post_repair_unresolved_low_util_families": list(
                                unresolved_final
                            ),
                        }
            out.append(item)
            continue
        promoted_item, promoted_meta = _try_promote_efficiency_item_to_executor_backed_candidate(
            item,
            state=state,
            blocked_reason=str(reason or ""),
        )
        if promoted_meta.get("attempted") or promoted_meta.get("promoted"):
            promotion_debug.append(
                {
                    **dict(promoted_meta),
                    "index": idx,
                    "title": item.get("title_main"),
                },
            )
        if isinstance(promoted_item, dict) and promoted_meta.get("promoted"):
            out.append(promoted_item)
            continue
        sanitized = _guidance_item_as_advisory(item, blocked_reason=str(reason or "candidate_not_commit_eligible"))
        out.append(sanitized if isinstance(sanitized, dict) else item)
        if idx == 0 and blocked_primary_reason is None:
            blocked_primary_reason = str(reason or "candidate_not_commit_eligible")
    if isinstance(debug_sink, dict):
        debug_sink["design_guide_executor_contract_primary_blocked_reason"] = blocked_primary_reason
        debug_sink["design_guide_executor_contract_primary_blocked"] = bool(blocked_primary_reason)
        debug_sink["design_guide_executor_backed_promotion_debug"] = list(promotion_debug)
        debug_sink["design_guide_executor_backed_promotion_applied"] = any(
            bool(row.get("promoted")) for row in promotion_debug
        )
    return out
