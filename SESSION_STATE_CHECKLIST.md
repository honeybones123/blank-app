# Session State Checklist (must-pass)

## A) Boot / Init
- [ ] A1 init_shared_session_state() is called exactly once per run before any page widgets.
- [ ] A2 Defaults are seeded using key existence only:
  - ✅ if key not in st.session_state: st.session_state[key] = default
  - ❌ never if not st.session_state.get(key)
- [ ] A3 Snapshot restore sets:
  - [ ] _restored_from_snapshot = True
  - [ ] _restore_guard_active = True
- [ ] A4 After restore:
  - [ ] recalc_derived_values()
  - [ ] persist_state_snapshot()

## B) Hydration (shared → widget keys)
- [ ] B1 BEFORE any widgets render for the active page, hydrate widget keys from shared:
  - ✅ if widget_key not in st.session_state: st.session_state[widget_key] = st.session_state[shared_key]
  - ❌ never write shared keys during hydration
- [ ] B2 Hydration MUST include spacing keys (e.g. s_bar_bot, s_lig) so stale widget zeros don't clobber shared.

## C) Widget creation
- [ ] C1 For mapped widgets, do not pass value= after the key exists:
  - ✅ pre-seed st.session_state[widget_key] if missing
  - ✅ call widget with key=widget_key and no value=
- [ ] C2 Widget keys are stable forever (no renames without migration).
- [ ] C3 **ABSOLUTE RULE**: Never assign `st.session_state[<widget_key>] = ...` inside page render
  - ✅ **ONLY** allowed form is:
    ```python
    if widget_key not in st.session_state:
        st.session_state[widget_key] = initial_value
    ```
  - ❌ **NEVER** do unconditional assignments like:
    ```python
    st.session_state[widget_key] = value  # This overwrites user edits!
    ```
  - Use `seed_widget_from_shared()` helper or conditional seeding only.

## D) Sync callbacks (widget → shared)
- [ ] D1 Callback must exit if:
  - [ ] sync lock active
  - [ ] restore guard active
  - [ ] widget not rendered this run (render registry)
- [ ] D2 "Missing" means key absent OR value is None. 0 is valid.
- [ ] D3 Never overwrite meaningful shared values with default widget 0 for nonzero-required keys.

## E) Restore guard teardown (must happen)
- [ ] E1 After the active page render_fn finishes, set:
  - [ ] _restore_guard_active = False

## F) Derived/results discipline
- [ ] F1 Derived values only written in recalc_derived_values()
- [ ] F2 Results only written in update_results()

## G) Must-pass tests
- [ ] G1 All-zeros test: set every reo input to 0, navigate all pages → no defaults reseeded unless reset pressed.
- [ ] G2 Restore test: set non-default values, reload/navigate → restored shared values never overwritten by widget defaults.
