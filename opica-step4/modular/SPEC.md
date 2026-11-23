# OPICA23 stock-kernel object composition gate — bounded counter reconciliation

**Version:** OPICA23_KERNEL_OBJECT_COMPOSITION_V1  
**State:** IMPLEMENTED; only a complete execution receipt can record a pass.  
**Date:** 21 November 2026, Europe/Stockholm.

This is a separately versioned acceptance method. It must not overwrite, relabel, or retrospectively pass the Round 19 mandatory 25-stage gate. That gate remains NOT_RUN/BLOCKED unless it is actually executed successfully.


## Historical execution and scope

Round20 head `56869094eafb17b534ca6a30cf2296959e4d4d20`, run `44920309725`, passed its first nineteen modular stages and timed out in `fresh_import_guard_compile` after 3601.084 seconds with an empty Lean log. Its final ten stages were NOT_RUN and the independent stage was SKIPPED. It remains INCOMPLETE. This successor changes object production and adds sampled RSS/swap, CPU, page-fault, I/O and pressure telemetry; it does not retrospectively pass that run. The target proposition, complete native/supplier proof identity, standard-three-axiom policy and independent complete-closure requirement remain fixed.

Round21 head `56b129cc2212eb28d0c32867d49078dbae6a34be`, run `44935463985`, passed nine modular stages and failed in `canonical_modules_compile` while reading `/proc/23617/io`. The first conditional receiver compile exited zero and retained its object, but the monitor recorded `MONITOR_OR_LAUNCH_ERROR` / `PermissionError`; that stage remains FAIL. The twenty later stages were NOT_RUN, and independent combined proof checking was SKIPPED. No Main import or closed C1 construction was reached. Round22 repaired only optional I/O telemetry and recorded this prior failure without reclassifying it. The exact kernel producer, logical sources, thirty-stage order and all proof/identity/axiom requirements remain unchanged.

Round22 head `70bfbd662f42aff97194c34ef3b6ee996f3cc1a1`, run `44941237531`, retained 9 PASS / 1 FAIL / 20 NOT_RUN. Its first two canonical monitored compilations passed. The third, `BoundaryFlatCharacterization`, exited zero, printed the expected standard-three-axiom reports and produced its original objects, but its monitor failed with incomplete mandatory memory counters for PID 18535. All ten recorded optional-I/O samples were available. The particular missing counter and the failing process-state recheck were not retained, so an exit-transition explanation remains a hypothesis. The actual Main import, closed construction and complete independent proof check did not run. That failure is preserved unchanged.

Round23 monitor schema `MONITORED_PROCESS_GROUP_RESOURCE_LIFECYCLE_V3` adds bounded re-observation of incomplete mandatory memory counters. One shared 0.25-second allowance per process-group sample, also bounded by the execution deadline, permits complete counters to be recovered or the original process identity to be confirmed no longer live. PID reuse, changed group, persistent live missing counters, malformed values and denied live status remain fatal. Confirmed retirement is recorded without invented measured-zero counters. Reconciliation details are retained. The original sampled memory cap, exit-zero, diagnostic, EOF, deadline, descendant-cleanup and final-evidence requirements remain in force. This changes no theorem, proof object, axiom policy, selected root or proof-stage obligation.

### Optional process I/O and mandatory validity gates

Round22 used monitor schema `MONITORED_PROCESS_GROUP_OPTIONAL_IO_V2`. Per-process `/proc/<pid>/io` counters are optional telemetry: a read or format failure records sticky INCOMPLETE I/O coverage and preserves the last available counters. The same member's RSS and VmSwap stay in the mandatory memory total; missing or invalid mandatory memory counters still fail. Exit zero, complete stdout/stderr EOF, compiler/proof diagnostics, finite wall time, sampled memory limits, output/telemetry limits, complete process-group cleanup and final evidence hashes remain mandatory. Incomplete optional I/O does not establish proof validity. The watchdog remains sampled, not a kernel/cgroup hard memory cap.

## 1. Mathematical acceptance argument

Let S be the complete proof dependency closure exported for the published original supplier targets. Let N be the native receiver and all its proof/definition dependencies, independently validated in the native-only common-pin environment. Let D be the freshly kernel-checked closed theorem objects and expanded consumers.

The desired composition is sound if:

1. S is exactly a previously kernel-accepted certificate under only the three permitted axioms.
2. The actual supplier proposition in the final environment is the same proposition in S and the intended canonical RH definition.
3. N is kernel-accepted under the same axioms, its actual definitions/proof constants in the final environment agree with the checked native environment, and common definitions agree on overlaps.
4. Every dependency used by D is covered by S, N, the shared checked core/packages, or an earlier validated declaration of D.
5. D's actual proof values are kernel-replayed against that coherent immutable environment, and the final theorem has the exact closed native C1 type.

Then the native RH-to-C1 proof applied to the authenticated closed RH proof establishes C1. Repeating the kernel computation on byte-identical S does not add a mathematical premise. Omitting any unvalidated dependency, however, would invalidate this modular argument.

A supplier fingerprint alone proves no theorem. The supplier's full proof closure must be bound to the accepted external certificate; the native proof closure and the actual new declaration values require their own checks.

## 2. Supplier endpoint must be the published root

Use:

    import Main
    theorem step4C1 :
      Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds :=
        Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis
          _root_.riemannHypothesis

Retain the exact OPICARound20 theorem names and mathematical specification. The failed Round20 run never produced these objects. The fresh output root, absence guard, new receipt schema and exact object hashes distinguish this execution from every earlier attempt.

The published Main theorem is an explicit export target. The old internal endpoint UpperTheory.FinalTheorems.riemannHypothesis is not an explicit published target and is not used directly by Main's RH wrapper. Its membership in the published proof closure cannot be assumed. The Main-root change closes that coverage uncertainty.

## 3. Exact supplier certificate binding

Supplier source checkpoint: bdb1810a06c78f246da285c9bcbe7db2cd992888.
Original supplier src tree: 24df20b62d9976ccd20da819bc20b16f808f0fdd.
Compiler: Lean 4.33.1, commit 819816b2e0a3bf405af45ae5c7af2491d8f5bee6.
Mathlib: 0df444a360eaa60ab8c11dca51a86af692955474.
Exporter: lean4export commit 15f6055e299ad5b89345e533cc2192f4cc00f659, built with that compiler.

Required uncompressed supplier export:

- SHA256: 5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e.
- Published byte count: 61,570,595,788; record the actual count independently.
- Published compressed SHA256: 61a8938ad5f5e57397c1c0e3b954916af546d9004ade01c3555744a681b05381.

The command must use all 38 original export targets in the original order, not just the five mathematical endpoints:

    Quot Quot.mk Quot.lift Quot.ind
    riemannHypothesis riemannZeta_eq_zero_re LFunction_ne_zero_of_half_lt_re LFunction_eq_zero_re LFunction_eq_zero_re_of_isPrimitive
    propext Quot.sound Classical.choice
    Nat.add Nat.sub Nat.mul Nat.pow Nat.gcd Nat.div Nat.mod Nat.beq Nat.ble Nat.land Nat.lor Nat.xor Nat.shiftLeft Nat.shiftRight String.ofList Char.ofNat List eagerReduce Nat String String.mk Char optParam autoParam semiOutParam outParam

The existing export-targets.txt bytes have SHA256 9eeb2e5e55be4a78f6e4983fc950dba915b45ad8aeb7a02a32341927a89e05e8.

**Final-environment binding is mandatory:** stream those exact targets using the actual final OPICAStep4.MainClosedBridge module as the importer. Exporting Main alone is useful as an early preflight, but by itself does not establish what constants the final environment resolves. The exporter metadata records compiler/export format, not the root module name. A final-environment export should match if the relevant declarations are identical; an unexpected mismatch is a failure to bind, even if benign ordering differences are suspected.

The complete export may be streamed through a bounded-memory SHA256 and byte-count sink. Retain exporter exit status, separate stderr, exact argv/environment/tool hashes and the digest/count. This avoids storing 61 GB without removing any certificate bytes from the identity check. The sink must reject partial/error exits. No normalization, dropped declarations or rewritten output is allowed before hashing. The full SHA256 is the required artifact identity. A differing prose byte count with the exact required digest is a metadata discrepancy to record and review, not evidence of changed certificate bytes. This distinction is concrete: the pilot challenge artifact hashes exactly to the published challenge digest but measures 350,862,311 bytes, while the MIT page states 350,862,970.

## 4. External validation evidence and trust boundary

Freeze the MIT verification page, SHA256SUMS, audit.log, con-leche-master.log, con-leche-compare.log and nanoda.log. Verify each available raw log against the publisher's SHA256SUMS. The source must still report successful complete checking and comparison for the exact solution.ndjson digest.

The current publisher's manifest gives:

| Evidence | SHA256 |
| --- | --- |
| audit.log | 0a1473fce6eed840011f4a76b1c51558fc6f03edd1e6bd1ee542e6c738d87a62 |
| con-leche-master.log | 23e27eacb9e8378569474cc185c0e98f6b995b4db0f8df88fd48a921084fed02 |
| con-leche-compare.log | 5a068bf55f24904eea9f05eda947c63d43bdee3c6ab0490e43943a3bd9af1f6e |
| nanoda.log | d4c5360b02d8dd885150c1cc28b616cb6fb5bf5b20d142558d79a7b15ae9d9df |

The external report and logs attest a completed independent proof check. The digest proves that our actual supplier export is the same artifact the publisher identifies. It does **not** cryptographically prove that the reported computation happened. Trust in the authenticated publisher's verification report remains an explicit evidence assumption, just as relying on a remote CI receipt requires trusting that service and its logs.

Accordingly, this design can establish the intended formal theorem under an explicitly disclosed externally verified supplier model. It cannot honestly be described as an independent local rerun of the supplier's kernels, or as satisfying a policy that requires those exact computations to be rerun here. No new logical RH axiom is introduced: the actual closed proof is loaded and its complete certificate is identified. The trust difference is in where that proof was checked.

The whole-proof Comparator/Lean-export jobs recorded as pending in the frozen evidence are not counted as passed. Completed con-leche/nanoda and comparison receipts are the supplier verification relied on by this version.

## 5. Native proof coverage

Rebuild the exact 572 native modules from unchanged source at native head 7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9, under the common compiler/Mathlib pins. Freshness, module closure, source hashes and actual object hashes must be verified as in Round 19.

Before loading supplier modules, fresh-replay the complete native-only ReceiverAudit environment through the stock kernel. Include the native C1-to-RH consumer if the new expanded audit invokes it. A named-module replay of ReceiverAudit alone only checks its new declarations relative to imports and is insufficient as a replacement for full native coverage in this successor's adversarial trust model.

Record all native theorem targets used by D, their exact types, actual proof bodies' dependency sets, and standard-only transitive axiom audits. Scan the governed native source closure for project axioms/placeholders as required by project policy. Native original-pin production CI remains separate and is not claimed by the common-pin run.

## 6. Coherence and collision protection

The Round24 execution bundle retains this gate and its verifier unchanged. Its
sole transport-layout change is a fixed 64 KiB SquashFS data block in place of
1 MiB, with zstd level 9, the current read-only mount, image/free-disk limits and
all execution deadlines unchanged. The original archive identity and every
expanded/mounted file hash remain mandatory. The new multi-block/tail/fragment
round-trip control establishes storage correctness, not a speed or capacity
guarantee. Round23's guarded-import timeout remains INCOMPLETE; neither that
attempt nor this unexecuted layout establishes a closed theorem.

Freeze the actual Lean core, Mathlib and package objects; require exact byte identity and resolution between native-only and final environments. Reject shadowed module paths, changed inventories, changed source trees and changed package revisions. Hash-mounted SquashFS inputs are legitimate if their expanded file bytes match; compression does not change proof semantics.

**Constant-level collision checking is mandatory too.** Lean can allow duplicate theorem names with matching signatures while ignoring proof-value differences during import finalization. Module path checks alone therefore do not close every substitution route.

Before adding native modules, inspect the supplier-only environment and reject a collision with any native-project declaration name or new OPICA20 declaration name. Shared core/Mathlib/package declarations are allowed only through the already byte-identical shared imports. The canonical native declaration inventory should be based on actual object/module ownership, not merely a Zeta23 name prefix: project extensions can live in other namespaces.

An alternative equally strict implementation is exact proof-export identity for every used native target between native-only and final environments. Such an alternative must cover values and their full dependencies, not only theorem types. Do not silently fall back from a collision failure to a type-only comparison.

## 7. New closed declarations

The exact Lean source files remain pinned as the mathematical specification. Their Main-importing elaborator compilation is **not run or claimed** by this version. Instead, a freshly built native producer uses the pinned stock Lean 4.33.1 APIs to create ordinary proof objects:

1. Import the original Main and canonical NativeValidated environment at trust level zero, private visibility, with `loadExts=false`. Process-lifetime `leakEnv=true` only avoids reference-count/freeing work; it changes no declaration.
2. Reject any preexisting intended closed name. Serialize an empty ordinary ImportGuard module with exactly the implicit Init imports and explicit Main, NativeValidated and Lean imports.
3. In a separate process, actually reimport that newly written guard. Add exactly the three intended ordinary theorem declarations using checked stock-kernel insertion, with the exact closed types and proof terms.
4. Use stock `mkModuleData`/`saveModuleData` with explicitly empty **new elaborator extension entries**. No logical constant, type, proof body or proof dependency is removed. No IR extra constants or unexpected module sidecars are allowed. This is not represented as a byte-identical elaborator output.
5. Read the actual objects through a separate raw inspector; require exact ordinary import headers/flags, zero guard declarations, three closed theorem declarations, exact types/proof dependencies, empty new extension entries and no hidden parameters.
6. Traverse actual loaded proof and type bodies for the four headline theorem axiom reports, failing on every unresolved constant. Empty extension metadata must never be interpreted as an empty axiom set. Only propext, Classical.choice and Quot.sound are accepted.
7. Replay both freshly written modules through the stock kernel, and retain every later native/supplier identity and independent proof-closure gate.

The loaded final environment must also contain every one of the exact fifty
independent-checker roots in its fixed order. Reject unsafe or partial roots;
require ordinary theorem kind for all five supplier headline roots, nine native
roots and three closed roots. The primitive roots retain their legitimate kinds.
The bound fifty-name inventory is checked again by the independent wrapper, so
the reader's ability to skip unsafe requested roots cannot weaken coverage.

The producer is not a trusted proof oracle. Its native executable, exact source files and build are recorded, and invalid-proof/existing-name controls must succeed. A printed success marker or an object file's existence cannot substitute for the raw inspection and actual kernel checks.

Require direct constant dependencies of every new proof value and type to belong to:

- the authenticated global riemannHypothesis supplier root;
- the checked native-only environment;
- the byte-identical shared checked dependencies;
- earlier freshly validated declarations of the same OPICA20 delta.

No additional external theorem outside the accepted supplier closure may be used. For the main C1 theorem the actual proof value should be the intended receiver application to the global supplier. Kernel-replay every new module against the frozen imports. Reject nonstandard transitive axioms, sorryAx, project axioms, compilation/replay failures, termination, warning-based failures and skipped stages.

## 8. Exact target meaning

Build native-only canonical fingerprint theorems for the independently expanded C1 formula, its registered native alias, and Mathlib RH. These are ordinary reflexivity theorems and must have no placeholders.

Export those fingerprint targets from the final combined environment as a separate small certificate. Compare all referenced definitions against the canonical export with no open definition targets. The comparison configuration must have an empty definition_names list.

Retain both positive and deliberate changed-proposition negative controls. The latter must fail at the changed definition, not for an unrelated resource or syntax reason.

Require the actual closed consumer to have the canonical literal C1 target. Fingerprint equality proves only statement identity; kernel replay of the closed consumer provides the proof.

## 9. Final integrity and receipts

Rehash every bound object/tool/source/product and recheck import inventories after all computations. Require unchanged exact final environment, source roots, supplier certificate digest and target definitions. Mounts must remain immutable throughout verification.

Use a new receipt schema recording each stage's command, source/object identity, byte counts, exit, diagnostics, timings and result. All required stages must finish successfully. Incomplete stages stay NOT_RUN/INCOMPLETE.

Required explicit scope fields:

- gate_version: OPICA23_KERNEL_OBJECT_COMPOSITION_V1
- supplier_certificate_identity: MATCHES_PUBLISHED_FULL_CERTIFICATE
- supplier_kernel_execution: EXTERNAL_PUBLISHED_RECEIPT; never LOCAL_PASS
- native_full_kernel_execution: LOCAL_PASS
- new_closed_declarations_kernel_execution: LOCAL_PASS
- full_combined_export_kernel_execution: NOT_RUN_BY_THIS_GATE
- prior_round19_25_stage_gate: NOT_RUN_OR_BLOCKED_UNCHANGED
- fresh_closed_object_production: STOCK_KERNEL_CHECKED_ACTUAL_THREE_THEOREMS
- closed_source_elaborator_compilation: NOT_RUN_BY_THIS_GATE
- prior_round20_modular_v1_gate: INCOMPLETE_IMPORT_GUARD_TIMEOUT_AT_56869094
- prior_round21_kernel_object_gate: FAIL_OPTIONAL_PROC_IO_AT_56b129cc
- source_to_object_provenance: separately stated; no self-authenticating manifest claim
- claim: exact C1 at the common integration pin, using the explicitly identified external supplier

A legitimate final claim would be: “The exact native C1 theorem was produced by checked stock-kernel insertion and passed modular kernel/definition/axiom checks at the recorded common pin, using a supplier certificate byte-identical to the independently verified published artifact.” This modular receipt alone must not claim a full combined proof rerun. The separate mandatory independent gate checks the complete combined 50-root proof/type closure directly from the objects; it does not replay a full augmented NDJSON file.

## 10. Adversarial failure cases

| Failure | Required rejection |
| --- | --- |
| Original five roots exported but internal unexported theorem used by bridge | Reject dependency coverage; use the global published root |
| Only five targets used instead of all 38 original ordered targets | Export digest fails |
| Isolated supplier matches, final environment substitutes a definition | Final-environment supplier export or native fingerprint comparison fails |
| Fake native theorem injected outside supplier export closure | Constant collision or native proof-export identity fails |
| Existing new theorem name makes delta replay skip its value | Preexisting-name rejection |
| Native source hashes match but dependency proof objects differ | Shared/object binding and native full replay fail |
| Successful fingerprint export with no closed theorem | Actual named theorem kind/type/value/replay requirements fail |
| Solver is valid only under a hidden RH parameter | Closed-type inspection fails |
| Cache has unchecked extra constants used by delta | Dependency coverage fails |
| Compiler output is truncated, killed, or masks errors | Exit/diagnostic/count/hash checks fail |
| External success is retracted or only a pending run remains | External receipt prerequisite fails |
| All checks succeed but old gate is reported as passed | Reporting/claim validation fails |

## 11. Resource implications

This successor retains full object imports, an entire original supplier export traversal, native fresh replay, axiom traversal, final-environment definition comparisons and new-module kernel checks. These must be measured; the successful SquashFS pilot does not prove they fit.

It avoids the full-Main elaborator-extension import that timed out in Round20 and the second elaborator process that was never reached. The stock kernel-checked constants are serialized as ordinary modules with explicit metadata limitations. The separate independent gate still checks the complete supplier/native/closed proof closure. No RH assumption is substituted for the supplier proof.

The original 25-stage gate would still require full augmented-export helper parsing, all configured export kernels and a fresh replay of the entire combined imported environment. Transparent compression saves disk but not their heap memory or runtime. It remains an independent, unexecuted alternative.

## Primary references

- https://math.mit.edu/~drew/grh/
- https://math.mit.edu/~drew/grh/SHA256SUMS
- https://math.mit.edu/~drew/grh/con-leche-compare.log
- https://github.com/leanprover/lean4/blob/819816b2e0a3bf405af45ae5c7af2491d8f5bee6/src/LeanChecker.lean
- https://github.com/leanprover/lean4/blob/819816b2e0a3bf405af45ae5c7af2491d8f5bee6/src/Lean/Environment.lean
- https://github.com/leanprover/lean4export/blob/15f6055e299ad5b89345e533cc2192f4cc00f659/Export.lean

