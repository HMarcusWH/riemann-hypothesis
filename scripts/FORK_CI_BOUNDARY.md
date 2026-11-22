# Fork PR CI containment, 2026-11-23

The inherited upstream Build PR workflow was built for
leanprover-community/riemann-hypothesis. It used pull_request_target and
a cache service, runner groups, native proof seeds and an API resolver fixed to
that upstream repository. It is NOT authorized to build fork PRs.

On this fork, the inherited build workflow:
* has NO automatic pull_request_target trigger;
* has a fixed upstream-only guard on ALL four jobs;
* is not an acceptance check for OPICA or any RH claim.

The fork instead runs the unprivileged source-policy workflow to check:
* exact event repository/head/base identity (not a matching PR number upstream),
* no privileged execution of untrusted PR source, and
* refusal of stale parents, missing fork identity and changed source policy.

This is a containment repair, NOT an upstream proof build replacement. A new
fork-owned heavy runner/cache/merge-candidate build must be independently
qualified before large supplier-build CI can be re-enabled. Our separate OPICA
workflows preserve their original pinned source, kernel and claim boundaries.
Historical failing PR #4/5 upstream-misdirected builds remain FAIL, not PASS.

No byte changes to src or its Lean/Mathlib compilation inputs are authorized here.
