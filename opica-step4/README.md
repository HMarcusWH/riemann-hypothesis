# Exact OPICA Step 4: combined verification

This branch supplies a reproducible verification job for the exact native C1
contract. Its mathematical input is the unchanged supplier `src` tree
`24df20b62d9976ccd20da819bc20b16f808f0fdd`, together with the native project at
`7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9`. The isolated integration uses stock
Lean 4.33.1 and Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`.

The actual proposed closed declaration is
`Zeta23.OPICARound20.Closed.step4C1` in
`portable_gate/OPICAStep4/MainClosedBridge.lean`. It applies the existing native
RH-to-C1 theorem to the global `riemannHypothesis` declaration exported by
`Main`. A separate named theorem checks the fully expanded original C1
statement, including both parity domains, the physical norms, and the original
cutoff. Another named theorem derives positivity on the full boundary-flat
space. No mathematical source or original project pin is changed.

## Acceptance and exact scope

The authoritative results of this job are `MODULAR_GATE_RECEIPT.json` and
`INDEPENDENT_RECEIPT.json` in its uploaded evidence artifact. Both must finish
with PASS. The existence of this branch, a successful resource pilot, a cache
download, or a successful native bootstrap does not establish the closed
theorem. Every required stage must complete.

`OPICA22_KERNEL_OBJECT_COMPOSITION_V1` is a separately specified modular
verification method. It combines:

1. A fresh native source build and complete fresh kernel replay of the native
   imported environment.
2. Checked stock-kernel construction, raw theorem-object inspection, exact closed type and
   transitive axiom audits, and kernel replay of the new named declarations.
3. Exact equality of the complete native proof export before and after the
   supplier imports, including proof values and transitive definitions.
4. Definition-sensitive comparison of the literal C1 and canonical RH targets,
   with matching and deliberately substituted-definition controls.
5. A complete export of all 38 original supplier targets from the actual final
   combined environment, byte-for-byte bound by SHA256 to the published
   certificate `5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e`.

That modular stage relies on the explicitly recorded external con-leche/nanoda
verification receipts published at <https://math.mit.edu/~drew/grh/>. This job
does not claim those external kernel computations were executed locally.
The certificate hash identifies the exact externally attested object; the
publisher's execution report is an explicit trust premise.

After the modular gate passes, `INDEPENDENT_KERNEL_OBJECT_COMBINED_PROOF_V1` checks the complete
combined proof dependency closure directly from the original compiled files.
It rebuilds unchanged con-leche commit
`cd2eceab2e9b10404c663b468639c8aa99d0d1f2` with its separately pinned official
Lean 4.36.0 runtime. The proof objects remain the original Lean 4.33.1 objects.
The checker recursively follows both statement and proof dependencies for all
50 selected roots: the 38 original supplier roots, nine native roots, and three
new closed theorem roots. It checks every emitted declaration and requires
actual acceptance with exit zero. It uses read-only views and verifies the
bound original bytes before and after the lazy proof reader runs.

The independent run retains the existing closed safe-theorem, exact-type,
canonical-definition, and three-axiom requirements. It also repeats the real
native proof-closure replay, a field-by-field comparison of the original object
reader with the stock exporter, and controls for missing roots and transitive
custom axioms. A complete independent PASS supplies local verification evidence
for the actual combined proof. Its executable-build receipt does not claim a
fresh build of every checker correctness metatheorem.

The original Round 19 mandatory 25-stage gate is preserved unchanged in
`portable_gate/`. This new workflow does not execute or retrospectively pass
that procedure, and does not rerun a kernel over a full augmented NDJSON export.
The independent checker operates directly on the complete selected object
closure. The two receipts record these distinct methods and scopes. A modular
PASS supports its external-certificate model; the independent PASS additionally
requires the complete actual combined proof check here. Neither establishes an
original-pin production rebuild or erases the old procedure's outstanding
status. See `modular/SPEC.md` for the modular acceptance argument.

## Preserved earlier results and the optional-I/O repair

Round21 head `56b129cc2212eb28d0c32867d49078dbae6a34be`, run `44935463985`, passed nine modular stages and failed in `canonical_modules_compile` while reading `/proc/23617/io`. The first conditional receiver compile exited zero and retained its object, but the monitor recorded `MONITOR_OR_LAUNCH_ERROR` / `PermissionError`; that stage remains FAIL. The twenty later stages were NOT_RUN, and independent combined proof checking was SKIPPED. No Main import or closed C1 construction was reached. The Round22 successor repairs only optional I/O telemetry and records this prior failure without reclassifying it. The exact kernel producer, logical sources, thirty-stage order and all proof/identity/axiom requirements remain unchanged.

The monitor schema is `MONITORED_PROCESS_GROUP_OPTIONAL_IO_V2`. Per-process `/proc/<pid>/io` counters are optional telemetry: a read or format failure records sticky INCOMPLETE I/O coverage and preserves the last available counters. The same member's RSS and VmSwap stay in the mandatory memory total; missing or invalid mandatory memory counters still fail. Exit zero, complete stdout/stderr EOF, compiler/proof diagnostics, finite wall time, sampled memory limits, output/telemetry limits, complete process-group cleanup and final evidence hashes remain mandatory. Incomplete optional I/O does not establish proof validity. The watchdog remains sampled, not a kernel/cgroup hard memory cap.

Round20 head `56869094eafb17b534ca6a30cf2296959e4d4d20` passed its first nineteen modular stages, then its full-Main elaborator import timed out after one hour. The remaining ten stages and complete independent proof check did not run. That attempt remains INCOMPLETE.

This version uses the pinned stock kernel to check the exact three theorem declarations and stock module-data APIs to write ordinary proof objects. It imports the original proof constants with `loadExts=false`, preserving their full types, bodies and dependencies while avoiding elaborator-extension initialization. The new modules explicitly have empty elaborator extension entries. The raw inspector validates exact ordinary imports, zero/three declarations, types, values and metadata; the later stock and independent kernels still check the actual proof. The original Lean bridge text is a pinned mathematical specification, and its full-Main elaborator compilation is not claimed. Execution-only telemetry records sampled RSS, swap, CPU, page faults and I/O, with bounded time and sampled memory enforcement.

## Reproducible execution

`.github/workflows/opica-combined-modular.yml` runs on the standard public
Ubuntu 24.04 GitHub runner. The resource pilot has already checked that this
runner can mount a stock read-only SquashFS image and read identical bytes
through memory mapping. The full workflow still has to demonstrate that the
actual imports, exports, and proof checks fit its time and resource limits.

`transport/verified_squashfs_store.py` streams the pinned supplier archive into
a stock SquashFS filesystem. It checks the compressed artifact hash, every
expanded original file hash, member counts, paths, sizes, and terminal archive
state before accepting the image. After mounting, the workflow reads and hashes
every original mounted file again. It does not manufacture or edit proof
objects. The native dependencies are fetched and checked separately by
`native_bootstrap/bootstrap_native.py`.

The workflow records source, toolchain, runtime-library, object, and theorem
identities; raw process exits and diagnostics; and the result of each gate.
It preserves small evidence artifacts even on failure. Missing, interrupted,
warning-masked, mismatched, or skipped checks cannot produce a terminal PASS.
An updated execution head supersedes a running older head; cancelled work keeps
its incomplete disposition and cannot contribute a missing PASS.

## Post-green mathematical result

The independent native theorem
`Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative` characterizes C1 as
nonnegativity of the canonical quadratic form on every boundary-flat vector,
for every positive aperture and every cutoff. It also yields an exact
equivalence with the native RH proposition and a finite negative-witness
refutation theorem. These are equivalences and implications, not an independent
closed proof of C1. Their Lean source is included and is freshly checked by
the workflow.
