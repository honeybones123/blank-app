"""Reusable Design Guide interaction assertions over verifier artifacts.

These assertions intentionally inspect saved browser verifier output. They are
shared by focused replay gates and can be reused by previous-fixed, golden, or
fuzz wrappers without changing product runtime behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_VISIBLE_OUTCOMES = {"PASS", "FAIL", "ACTION", "INFO"}
FORBIDDEN_DEBUG_TOKENS = (
    "candidate_evidence",
    "search_evidence",
    "current_state",
    "hidden browser-state",
    "_browser_state_probe",
    "guidance_compute_probe",
    "design_guide_probe",
    "exact_blockers_by_family",
    "post_click_exact_blockers_by_family",
    "candidate_search_evidence",
)


@dataclass
class AssertionResult:
    name: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


class DesignGuideAssertionError(AssertionError):
    """Raised when a Design Guide interaction contract is violated."""

    def __init__(self, result: AssertionResult):
        self.result = result
        super().__init__(f"{result.name}: {result.details}")


def _fail(name: str, **details: Any) -> AssertionResult:
    return AssertionResult(name=name, passed=False, details=details)


def _pass(name: str, **details: Any) -> AssertionResult:
    return AssertionResult(name=name, passed=True, details=details)


def _steps(run_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    case = run_summary.get("case")
    if isinstance(case, dict):
        rows.extend(step for step in list(case.get("timeline") or []) if isinstance(step, dict))
    for failure in list(run_summary.get("failures") or []):
        if isinstance(failure, dict):
            rows.extend(step for step in list(failure.get("timeline") or []) if isinstance(step, dict))
    for case in list(run_summary.get("cases") or []):
        if isinstance(case, dict):
            rows.extend(step for step in list(case.get("timeline") or []) if isinstance(step, dict))
    if not rows:
        for key in ("timeline", "steps"):
            rows.extend(step for step in list(run_summary.get(key) or []) if isinstance(step, dict))
    if not rows and isinstance(run_summary.get("visible_design_guide"), dict):
        rows.append(run_summary)
    return rows


def _latest_step(run_summary: dict[str, Any]) -> dict[str, Any]:
    steps = _steps(run_summary)
    return dict(steps[-1] if steps else {})


def _visible(step: dict[str, Any]) -> dict[str, Any]:
    return dict(step.get("visible_design_guide") or {})


def _summary(step: dict[str, Any]) -> dict[str, Any]:
    return dict(step.get("visible_summary") or {})


def _state(step: dict[str, Any]) -> dict[str, Any]:
    return dict(step.get("browser_state") or {})


def _guidance_probe(step: dict[str, Any]) -> dict[str, Any]:
    return dict(_state(step).get("guidance_compute_probe") or {})


def _proof_probe(step: dict[str, Any]) -> dict[str, Any]:
    return dict(_state(step).get("design_guide_probe") or {})


def _exact_blockers(step: dict[str, Any]) -> dict[str, Any]:
    card = _visible(step)
    guidance = _guidance_probe(step)
    proof = _proof_probe(step)
    return {
        **dict(card.get("exact_blockers_by_family") or {}),
        **dict(guidance.get("exact_blockers_by_family") or {}),
        **dict(guidance.get("post_click_exact_blockers_by_family") or {}),
        **dict(proof.get("exact_blockers_by_family") or {}),
        **dict(proof.get("post_click_exact_blockers_by_family") or {}),
    }


def _button_contract(step: dict[str, Any]) -> dict[str, Any]:
    card = _visible(step)
    guidance = _guidance_probe(step)
    return dict(card.get("button_contract") or guidance.get("button_contract") or guidance.get("primary_button_contract") or {})


def _family_selection(step: dict[str, Any]) -> dict[str, Any]:
    card = _visible(step)
    guidance = _guidance_probe(step)
    proof = _proof_probe(step)
    return {
        "selected_family_id": (
            card.get("selected_family_id")
            or guidance.get("selected_family_id")
            or proof.get("selected_family_id")
        ),
        "selected_family": (
            card.get("selected_family")
            or guidance.get("selected_family")
            or proof.get("selected_family")
        ),
        "selection_reason": (
            card.get("selection_reason")
            or guidance.get("selection_reason")
            or proof.get("selection_reason")
        ),
        "published_family_id": (
            card.get("published_family_id")
            or guidance.get("published_family_id")
            or proof.get("published_family_id")
        ),
        "cta_family_id": (
            card.get("cta_family_id")
            or guidance.get("cta_family_id")
            or proof.get("cta_family_id")
        ),
        "family_selection_contract": (
            card.get("family_selection_contract")
            or guidance.get("family_selection_contract")
            or proof.get("family_selection_contract")
        ),
        "family_chooser_contract": (
            card.get("family_chooser_contract")
            or guidance.get("family_chooser_contract")
            or proof.get("family_chooser_contract")
        ),
        "rejected_families": (
            card.get("rejected_families")
            or guidance.get("rejected_families")
            or proof.get("rejected_families")
        ),
        "family_match_passed": (
            card.get("family_match_passed")
            if card.get("family_match_passed") is not None
            else guidance.get("family_match_passed")
        ),
        "family_match_violation_reason": (
            card.get("family_match_violation_reason")
            or guidance.get("family_match_violation_reason")
            or proof.get("family_match_violation_reason")
        ),
        "family_match_reroute_approved": (
            card.get("family_match_reroute_approved")
            or guidance.get("family_match_reroute_approved")
            or proof.get("family_match_reroute_approved")
        ),
    }


def _cta_labels(step: dict[str, Any]) -> list[str]:
    card = _visible(step)
    labels: list[str] = []
    if card.get("cta_visible") and card.get("cta_label"):
        labels.append(str(card.get("cta_label")))
    for key in ("cta_texts", "visible_cta_texts", "button_texts"):
        for label in list(card.get(key) or []):
            if str(label or "").strip():
                labels.append(str(label).strip())
    raw = str(card.get("text") or "")
    if raw.count("Run one-click auto design") > 1:
        labels.extend(["Run one-click auto design"] * raw.count("Run one-click auto design"))
    return labels


def _active_fail_families(step: dict[str, Any]) -> set[str]:
    families = set(str(f or "").strip().lower() for f in list(step.get("active_failing_families") or []) if str(f or "").strip())
    support = dict(_summary(step).get("browser_overview_support") or {})
    statuses = dict(support.get("statuses") or {})
    utils = dict(support.get("utils") or {})
    for family in ("bending", "shear"):
        status = str(statuses.get(family) or dict(_summary(step).get(family) or {}).get("status") or "").upper()
        util = _float_or_none(utils.get(family) or dict(_summary(step).get(family) or {}).get("util"))
        if status == "FAIL" or (util is not None and util > 1.0):
            families.add(family)
    return families


def _low_util_families(step: dict[str, Any]) -> set[str]:
    families = set(str(f or "").strip().lower() for f in list(step.get("low_util_families") or []) if str(f or "").strip())
    support = dict(_summary(step).get("browser_overview_support") or {})
    utils = dict(support.get("utils") or {})
    statuses = dict(support.get("statuses") or {})
    for family in ("bending", "shear"):
        util = _float_or_none(utils.get(family) or dict(_summary(step).get(family) or {}).get("util"))
        status = str(statuses.get(family) or "").upper()
        if util is not None and 0.0 < util < 0.85 and status != "FAIL":
            families.add(family)
    return families


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except Exception:
        try:
            text = str(value or "").strip().split()[0]
            return float(text)
        except Exception:
            return None


def _has_actionable_cta(step: dict[str, Any]) -> bool:
    card = _visible(step)
    contract = _button_contract(step)
    return bool(
        card.get("cta_visible")
        and card.get("cta_enabled")
        and (contract.get("enabled") or contract.get("actionable"))
        and dict(contract.get("updates") or {})
    )


def _visible_text(step: dict[str, Any]) -> str:
    card = _visible(step)
    return " ".join(
        str(value or "")
        for value in (
            card.get("title"),
            card.get("headline"),
            card.get("text"),
            card.get("status_label"),
            card.get("intent"),
            card.get("cta_label"),
        )
    ).strip().lower()


def _contract_family(step: dict[str, Any]) -> str:
    contract = _button_contract(step)
    card = _visible(step)
    return str(
        contract.get("family")
        or card.get("family")
        or card.get("check_key")
        or ""
    ).strip().lower()


def _visible_forbidden_underdesign_outcome(step: dict[str, Any]) -> str | None:
    text = _visible_text(step)
    if "cleanup" in text:
        return "cleanup_optimisation_visible"
    if "design is efficient" in text:
        return "design_is_efficient_visible"
    if "exact stop" in text or "exact-stop" in text or "no further safe cleanup" in text:
        return "exact_stop_or_cleanup_stop_visible"
    if "blocked cleanup" in text or "cleanup blocked" in text:
        return "blocked_cleanup_visible"
    status = str(_visible(step).get("status_label") or "").strip().upper()
    if status == "PASS" and "fail" not in text:
        return "pass_terminal_visible"
    return None


def _has_repair_action_for_active_failure(step: dict[str, Any], active: set[str]) -> bool:
    if not _has_actionable_cta(step):
        return False
    family = _contract_family(step)
    text = _visible_text(step)
    if _visible_forbidden_underdesign_outcome(step):
        return False
    if family in active:
        return True
    if family == "combined" and active & {"bending", "shear"}:
        return True
    return any(
        token in text
        for token in (
            "repair",
            "required fix",
            "capacity is low",
            "strength",
            "increase",
            "tighten",
        )
    )


def _has_exact_proof(step: dict[str, Any], family: str | None = None) -> bool:
    blockers = _exact_blockers(step)
    if family:
        blockers = {family: dict(blockers.get(family) or {})} if blockers.get(family) else {}
    for blocker in blockers.values():
        if not isinstance(blocker, dict):
            continue
        if not bool(blocker.get("exact_blocker")):
            continue
        required = ("attempted_candidate_count", "failed_candidate_id", "failed_check_name", "reason")
        if all(blocker.get(key) not in (None, "", [], {}) for key in required):
            return True
    return False


def assert_design_guide_resolved(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    card = _visible(step)
    if int(card.get("visible_card_count") or 0) < 1:
        return _fail("assert_design_guide_resolved", reason="no_visible_card", artifact=run_summary.get("artifact_dir"))
    if int(card.get("proof_pending_visible_count") or 0) > 0 or bool(card.get("preparing_visible")):
        return _fail("assert_design_guide_resolved", reason="pending_shell_visible", card=card)
    return _pass("assert_design_guide_resolved", visible_card_count=card.get("visible_card_count"))


def assert_single_visible_outcome(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    card = _visible(step)
    count = int(card.get("visible_card_count") or 0)
    status = str(card.get("status_label") or "").strip().upper()
    classes = str(card.get("classes") or "").lower()
    if count != 1:
        return _fail("assert_single_visible_outcome", visible_card_count=count)
    if status == "BLOCKED":
        return _fail("assert_single_visible_outcome", reason="blocked_terminal_visible", title=card.get("title"))
    if status and status not in ALLOWED_VISIBLE_OUTCOMES:
        return _fail("assert_single_visible_outcome", status=status)
    if "blocked" in classes and status not in {"FAIL", "INFO"}:
        return _fail("assert_single_visible_outcome", reason="blocked_class_without_allowed_status", classes=classes, status=status)
    return _pass("assert_single_visible_outcome", status=status or "UNKNOWN")


def assert_single_primary_cta(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    labels = _cta_labels(step)
    visible_labels = [label for label in labels if label]
    if len(visible_labels) > 1:
        return _fail("assert_single_primary_cta", cta_labels=visible_labels)
    contract = _button_contract(step)
    actionable = bool(contract.get("enabled") or contract.get("actionable"))
    card = _visible(step)
    if actionable and not bool(card.get("cta_visible") and card.get("cta_enabled")):
        return _fail("assert_single_primary_cta", reason="actionable_contract_without_visible_enabled_cta", contract=contract)
    if not actionable and bool(card.get("cta_enabled")):
        return _fail("assert_single_primary_cta", reason="enabled_cta_without_actionable_contract", contract=contract)
    return _pass("assert_single_primary_cta", cta_labels=visible_labels)


def assert_no_duplicate_cta_labels(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    labels = _cta_labels(step)
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        return _fail("assert_no_duplicate_cta_labels", duplicates=duplicates, labels=labels)
    return _pass("assert_no_duplicate_cta_labels", labels=labels)


def assert_no_stale_outcomes(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    final_state = dict(step.get("post_click_final_state") or {})
    failure = str(final_state.get("failure_classification") or run_summary.get("failure_classification") or "")
    if any(token in failure for token in ("stale", "card_not_recomputed", "same_candidate_still_visible")):
        return _fail("assert_no_stale_outcomes", failure_classification=failure, final_state=final_state)
    return _pass("assert_no_stale_outcomes")


def assert_no_debug_output(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    text = " ".join(
        str(value or "")
        for value in (
            _visible(step).get("text"),
            _summary(step).get("raw_visible_text"),
        )
    ).lower()
    found = [token for token in FORBIDDEN_DEBUG_TOKENS if token.lower() in text]
    details_count = 0
    cards = list(_visible(step).get("cards") or [])
    if cards:
        details_count = int(dict(cards[0].get("test_hook_counts") or {}).get("design-guide-details") or 0)
    if details_count or found:
        return _fail("assert_no_debug_output", details_count=details_count, tokens=found)
    return _pass("assert_no_debug_output", details_count=details_count)


def assert_no_frozen_state(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    card = _visible(step)
    if int(card.get("proof_pending_visible_count") or 0) > 0 or bool(card.get("preparing_visible")):
        return _fail("assert_no_frozen_state", card=card)
    return _pass("assert_no_frozen_state")


def assert_no_blank_shell(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    card = _visible(step)
    if int(card.get("visible_card_count") or 0) < 1 or not str(card.get("title") or card.get("text") or "").strip():
        return _fail("assert_no_blank_shell", card=card)
    return _pass("assert_no_blank_shell")


def assert_underdesign_has_repair_or_explicit_no_repair(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    active = _active_fail_families(step)
    if not active:
        return _pass("assert_underdesign_has_repair_or_explicit_no_repair", active_failures=[])
    if _has_repair_action_for_active_failure(step, active):
        return _pass("assert_underdesign_has_repair_or_explicit_no_repair", active_failures=sorted(active), resolution="repair_action")
    missing = [family for family in active if not _has_exact_proof(step, family)]
    if missing:
        return _fail("assert_underdesign_has_repair_or_explicit_no_repair", missing_no_repair_proof=missing, card=_visible(step))
    return _pass("assert_underdesign_has_repair_or_explicit_no_repair", active_failures=sorted(active), resolution="exact_no_repair")


def assert_underdesign_unlocked_requires_repair(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    active = _active_fail_families(step)
    if not active:
        return _pass("assert_underdesign_unlocked_requires_repair", active_failures=[])
    forbidden = _visible_forbidden_underdesign_outcome(step)
    if forbidden:
        return _fail(
            "assert_underdesign_unlocked_requires_repair",
            reason=forbidden,
            active_failures=sorted(active),
            card=_visible(step),
            contract=_button_contract(step),
        )
    if _has_repair_action_for_active_failure(step, active):
        return _pass(
            "assert_underdesign_unlocked_requires_repair",
            active_failures=sorted(active),
            resolution="repair_action",
            family=_contract_family(step),
        )
    missing = [family for family in active if not _has_exact_proof(step, family)]
    if missing:
        return _fail(
            "assert_underdesign_unlocked_requires_repair",
            reason="missing_repair_action_or_legal_no_repair_proof",
            active_failures=sorted(active),
            missing_no_repair_proof=missing,
            card=_visible(step),
            contract=_button_contract(step),
        )
    return _pass(
        "assert_underdesign_unlocked_requires_repair",
        active_failures=sorted(active),
        resolution="legal_no_repair_proof",
    )


def assert_family_selection_matches_publication(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    family = _family_selection(step)
    selected = str(family.get("selected_family_id") or "").strip()
    published = str(family.get("published_family_id") or "").strip()
    cta = str(family.get("cta_family_id") or "").strip()
    reroute_approved = bool(family.get("family_match_reroute_approved"))
    if not selected and not published and not cta:
        return _pass("assert_family_selection_matches_publication", reason="family_ids_not_exposed_for_legacy_artifact")
    chooser = str(family.get("family_chooser_contract") or "").strip()
    if selected and chooser and chooser != "family_chooser_contract":
        return _fail(
            "assert_family_selection_matches_publication",
            reason="unexpected_family_chooser_contract",
            family_chooser_contract=chooser,
            family_selection=family,
        )
    if selected and str(family.get("selected_family") or selected).strip() != selected:
        return _fail(
            "assert_family_selection_matches_publication",
            reason="selected_family_does_not_match_selected_family_id",
            selected_family=family.get("selected_family"),
            selected_family_id=selected,
            family_selection=family,
        )
    if selected and published and selected != published and not reroute_approved:
        return _fail(
            "assert_family_selection_matches_publication",
            reason="selected_family_id_does_not_match_published_family_id",
            selected_family_id=selected,
            published_family_id=published,
            cta_family_id=cta,
            family_selection=family,
        )
    if selected and cta and selected != cta and not reroute_approved:
        return _fail(
            "assert_family_selection_matches_publication",
            reason="selected_family_id_does_not_match_cta_family_id",
            selected_family_id=selected,
            published_family_id=published,
            cta_family_id=cta,
            family_selection=family,
        )
    passed = family.get("family_match_passed")
    if str(passed).strip().lower() in {"false", "0", "no"} and not reroute_approved:
        return _fail(
            "assert_family_selection_matches_publication",
            reason=family.get("family_match_violation_reason") or "family_match_passed_false",
            family_selection=family,
        )
    return _pass(
        "assert_family_selection_matches_publication",
        selected_family_id=selected,
        published_family_id=published,
        cta_family_id=cta,
    )


def assert_overdesign_has_cleanup_or_exact_stop_proof(run_summary: dict[str, Any]) -> AssertionResult:
    step = _latest_step(run_summary)
    low = _low_util_families(step)
    if not low:
        return _pass("assert_overdesign_has_cleanup_or_exact_stop_proof", low_util_families=[])
    if _has_actionable_cta(step):
        return _pass("assert_overdesign_has_cleanup_or_exact_stop_proof", low_util_families=sorted(low), resolution="cleanup_action")
    missing = [family for family in low if not _has_exact_proof(step, family)]
    card = _visible(step)
    title = str(card.get("title") or "")
    if missing:
        return _fail(
            "assert_overdesign_has_cleanup_or_exact_stop_proof",
            missing_exact_stop=missing,
            title=title,
            card=card,
        )
    return _pass("assert_overdesign_has_cleanup_or_exact_stop_proof", low_util_families=sorted(low), resolution="exact_stop")


def assert_click_does_not_collapse_page(run_summary: dict[str, Any]) -> AssertionResult:
    for step in _steps(run_summary):
        card = _visible(step)
        if int(card.get("visible_card_count") or 0) < 1 and str(step.get("step_type") or "").lower().endswith("click"):
            return _fail("assert_click_does_not_collapse_page", step_type=step.get("step_type"), card=card)
    return _pass("assert_click_does_not_collapse_page")


def assert_click_does_not_jump_to_top(run_summary: dict[str, Any]) -> AssertionResult:
    for step in _steps(run_summary):
        layout = dict(step.get("scroll_layout_probe") or step.get("layout_probe") or {})
        before = _float_or_none(layout.get("scroll_before") or layout.get("stMain_scroll_before"))
        after = _float_or_none(layout.get("scroll_after") or layout.get("stMain_scroll_after"))
        if before is not None and after is not None and before > 300 and after < 50:
            return _fail("assert_click_does_not_jump_to_top", before=before, after=after, step_type=step.get("step_type"))
    return _pass("assert_click_does_not_jump_to_top")


def assert_reo_refreshes_after_geometry_edit(run_summary: dict[str, Any]) -> AssertionResult:
    for step in _steps(run_summary):
        sync = dict(step.get("diagram_state_sync") or step.get("geometry_reo_refresh") or {})
        if sync.get("geometry_changed") and sync.get("reo_stale"):
            return _fail("assert_reo_refreshes_after_geometry_edit", sync=sync)
    failure_text = str(run_summary.get("failure_classification") or "")
    if "reo" in failure_text.lower() and "stale" in failure_text.lower():
        return _fail("assert_reo_refreshes_after_geometry_edit", failure_classification=failure_text)
    return _pass("assert_reo_refreshes_after_geometry_edit")


CORE_ASSERTIONS = (
    assert_design_guide_resolved,
    assert_single_visible_outcome,
    assert_single_primary_cta,
    assert_no_duplicate_cta_labels,
    assert_no_stale_outcomes,
    assert_no_debug_output,
    assert_no_frozen_state,
    assert_no_blank_shell,
    assert_underdesign_unlocked_requires_repair,
    assert_underdesign_has_repair_or_explicit_no_repair,
    assert_family_selection_matches_publication,
    assert_overdesign_has_cleanup_or_exact_stop_proof,
    assert_click_does_not_collapse_page,
    assert_click_does_not_jump_to_top,
    assert_reo_refreshes_after_geometry_edit,
)


def run_core_design_guide_assertions(run_summary: dict[str, Any]) -> list[AssertionResult]:
    return [assertion(run_summary) for assertion in CORE_ASSERTIONS]


def assert_core_design_guide_contract(run_summary: dict[str, Any]) -> list[AssertionResult]:
    results = run_core_design_guide_assertions(run_summary)
    failures = [result for result in results if not result.passed]
    if failures:
        raise DesignGuideAssertionError(failures[0])
    return results
