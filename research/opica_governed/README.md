# Proper OPICA reuse: governed native compiler search, not keyword matching

**Execution branch:** synchronized Lean 4.36.0 proof supplier at source tree
`69b331ce0e429c7632dac6aa642e5875a50b1218`; independently qualified
native OPICA source in `HMarcusWH/zeta-23-lean` at
`bb7c8184a135b2823c6296917c5ac893bebf2a71`. The two incompatible
compiler worlds remain separate.

This package invokes the **unchanged native OPICA engine** from a second
pinned checkout rather than reimplementing its bounded theorem proposer.

## Research target A: three real native typed composition contracts

`run_frozen_native_retrieval.py` invokes original
`service._target`, `service._search_contract`,
`proposals.enumerate_candidates`, `composition_search.retrieve`,
`TargetSpec`, `GrammarProfile` and `SearchBudget` on the existing
compiler-exported `SEARCH_CONTRACTS.json`. Its three targets are
`INTEGRATION_CLOSURE`, `INTEGRATION_SOURCE`,
`INTEGRATION_INDEX`. It independently checks every reviewed native source
file against its frozen Git blob, uses only the two approved source declarations
per goal, preserves actual term plans and candidate fingerprints and reports
resource exhaustion without asserting mathematical unprovability.

This is a **source-bound PREVIEW**, not a full production snapshot or kernel
acceptance. Its synthetic preview generation is deliberately distinct from
real native source generations and its unused compiler-export field is a
zero sentinel. Fresh native proof validation is a separate lane.

## Research target B: independent arithmetic C1, no RH premise

`run_native_c1_search.py` executes under original OPICA's
`native_context` worker and a fresh compiler-bound native source snapshot.
It uses the trusted native `atlas_driver` and
`Zeta23.RHRC.OpicaComposition.Export` to export **actual Lean expression
DAGs**, full theorem type/axiom/source contracts, and the exact transparent
C1 proposition value. The approved proof menu contains exactly:

- `cofinal_moment_slice_bounds_of_even`
- `cofinal_moment_slice_bounds_of_odd`
- `cofinal_moment_slice_bounds_of_tendsto`

These are conditional mathematical reductions, *not unconditional positive
source estimates*. The file explicitly excludes `riemannHypothesis`,
`cofinal_moment_slice_bounds_of_riemannHypothesis` and the RH↔C1 equivalence.

The original `proposals.enumerate_candidates` and restricted
`composition_search.retrieve` then generate compiler-typed candidate plans
within a finite budget. Each retrieved plan must be checked by the unchanged
native `execute_attempt` worker, and any accepted candidate independently
replayed by `verify_application`.

An empty search means **NO MATCH IN THIS APPROVED GRAMMAR**, not proof of
impossibility or proof of C1. A candidate is not a theorem until genuine
kernel/axiom/independent consumer evidence is available; even one accepted
native conditional candidate is not automatically Step4/RH acceptance.

## Native compiler validation

The kernel lane also executes the original
`tests.test_integration_search_native` suite, which itself freshly exports
the three typed targets, reconstructs two-link plans, builds Lean theorem
objects and independently verifies them. **This is real OPICA use**, not
the source search from PR #4. It does not replace the original 11-lane
release qualification or complete external supplier certificate audit.

## Claim and cost controls

The native OPICA compiler/environment uses its frozen 4.33.x source and
Mathlib; the shortened community supplier uses Lean 4.36.0. No
`.olean` from one is loaded into the other. Source comparison and typed
native searches do not establish a new cross-toolchain theorem bridge.

All workflows preserve exact Git identities and failure artifacts. The old
30+7 original supplier proof verification and the separate Round19 gate retain
their historical status. **RH and independent Step4 remain OPEN.**
