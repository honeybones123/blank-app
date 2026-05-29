# Bug Fix Regression Checklist

A confirmed product bug is not fixed until all are complete:

- [ ] focused replay created
- [ ] replay fails before product patch
- [ ] global invariant added
- [ ] named failure classification added
- [ ] replay added to permanent regression suite
- [ ] never-regress rule written
- [ ] meta-verifier passes
- [ ] product patch applied only after verifier catches bug
- [ ] focused replay passes after patch
- [ ] previous-fixed/regression suite passes

Required report after every fix:

- Files changed
- Exact failure fixed
- Original artifact path
- Exact replay command run
- Result: passed / progressed past original failure / failed same way
- Replay or gate that now protects the failure
- Verifier invariant that now protects it
- New failure classification, if any
- Whether broader gates are still required
