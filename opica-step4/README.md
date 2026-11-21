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

The authoritative result of this job is `MODULAR_GATE_RECEIPT.json` in its
uploaded evidence artifact. The existence of this branch, a successful resource
pilot, a cache download, or a successful native bootstrap does not establish
the closed theorem. Every required stage must finish with PASS.

`OPICA20_MODULAR_CERTIFICATE_COMPOSITION_V1` is a separately specified modular
verification method. It combines:

1. A fresh native source build and complete fresh kernel replay of the native
   imported environment.
2. Actual compilation, raw theorem-object inspection, exact closed type and
   transitive axiom audits, and kernel replay of the new named declarations.
3. Exact equality of the complete native proof export before and after the
   supplier imports, including proof values and transitive definitions.
4. Definition-sensitive comparison of the literal C1 and canonical RH targets,
   with matching and deliberately substituted-definition controls.
5. A complete export of all 38 original supplier targets from the actual final
   combined environment, byte-for-byte bound by SHA256 to the published
   certificate `5ea74b912147c5c93cc2b6d70cc727cf908df2f62ac6a20480a3fa02f6be244e`.

The final item relies on the explicitly recorded external con-leche/nanoda
verification receipts published at <https://math.mit.edu/~drew/grh/>. This job
does not claim those external kernel computations were executed locally.
The certificate hash identifies the exact externally attested object; the
publisher's execution report is an explicit trust premise.

The original Round 19 mandatory 25-stage gate is preserved unchanged in
`portable_gate/`. This new workflow does not execute or retrospectively pass
that procedure, and does not rerun a kernel over the full augmented export.
The receipt records both limitations. A PASS supports the exact common-pin
C1 theorem under the specified modular external-certificate model; it does
not establish an original-pin production rebuild or erase the old gate's
outstanding status. See `modular/SPEC.md` for the full acceptance argument.

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

## Post-green mathematical result

The independent native theorem
`Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative` characterizes C1 as
nonnegativity of the canonical quadratic form on every boundary-flat vector,
for every positive aperture and every cutoff. It also yields an exact
equivalence with the native RH proposition and a finite negative-witness
refutation theorem. These are equivalences and implications, not an independent
closed proof of C1. Their Lean source is included and is freshly checked by
the workflow.
