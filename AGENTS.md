# Repository Instructions

## Design Guide Fuzz Root-Cause Gate

If a Design Guide fuzz failure is not fixed after two narrow patch attempts, stop patching and create a root-cause classification report before making further changes.

Classify the failure as exactly one primary category:

- candidate_search_failure
- candidate_found_not_selected
- candidate_selected_not_published
- published_payload_stale
- click_apply_noop
- click_apply_but_ui_stale
- blocker_evidence_missing
- verifier_classification_bug
- stale_cache_or_state_source
- render_proof_mismatch

Patch only the identified owner layer after that. Do not keep adding fallback guards across render, proof, payload, cache, or coherence paths until the owner layer is named.
