# OPICA Step 4 — canonical statement and closed proof gate

This package supplies an executable verification path for the exact native Step 4 contract. It consumes a complete original proof build, a separately rebuilt native receiver at the common Lean 4.33.1 pin, and trusted verification tools. It does not replace the external proof with a premise.

**The complete combined gate has not passed locally.** The available external checkout has the full source but lacks the complete compiled endpoint and its enormous dependency closure. The local preflight must remain BLOCKED. Successful native receiver builds, statement fingerprints and comparison controls are separately recorded supporting results.

The intended closed theorem is:

~~~lean
Zeta23.OPICARound19.step4C1 :
  Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds
~~~

Its short proof applies the existing native RH-to-C1 theorem to the external closed theorem `UpperTheory.FinalTheorems.riemannHypothesis`. `IndependentConsumer.lean` independently writes the complete C1 quantifiers, physical vector domains, norms, compressed energies, parity disjunction and cutoff `Nat.ceil (L ^ 4)`. It also exercises the existing native C1-to-Mathlib-RH implication.

`ClaimComparison.lean` adds the actual closed theorem `provedRequiredC1 : ClaimFingerprint.requiredC1`. That proof is distinct from the statement fingerprints described below.

## Why there are two separately exported environments

A valid proof can still target an unintended proposition if an imported definition has been substituted. Checking a Git commit, printing a theorem name and replaying loaded objects does not by itself establish that their definitions represent the intended statement.

The runner therefore first compiles and exports `ClaimFingerprint.lean` using only the prepared native environment and its common dependencies. It does this before loading the external solution modules. This canonical module has no placeholders and contains three ordinary theorems:

- `requiredC1_reflexive` mentions the independently written literal C1 proposition.
- `requiredC1_is_native` identifies that proposition with the registered native C1 alias by definitional reflexivity.
- `requiredRH_reflexive` mentions Mathlib's actual `RiemannHypothesis` separately, because C1's target need not itself mention zeta.

These theorems prove statement identities. **They prove neither C1 nor RH.**

Comparator compares ordinary theorem types and recursively compares every definition used by those types, including definition bodies. Its `definition_names` mechanism deliberately treats listed definitions as holes, so this package fixes `definition_names` to the empty list. The proposition-valued `requiredC1` is reached through an ordinary theorem's type; it is never listed as a definition hole.

The combined environment must export the same fingerprints **and all six actual closed proof declarations**, including the external RH supplier and `provedRequiredC1`. The runner checks closed theorem types and transitive axioms directly in that same augmented export. Official Comparator then compares canonical definitions and runs its configured kernels on that exact complete solution export. A fingerprint-only export cannot satisfy the runner's closed proof audit.

## Inputs and tool versions

Use Python 3.11 or later. The Python runner has no third-party dependencies.

| Input | Required identity or location |
| --- | --- |
| Complete original proof checkout/build | Actual `Development.AutomorphicArithmetic.CharacterBoxes.MainConclusion.olean` and complete imported objects; default root `.lake/build/lib/lean` |
| Original native source | Commit `7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9`, tree `9248b76d7aff60aab3bb775c4be9750dc6006003` |
| Native original toolchain | Its existing `leanprover/lean4:v4.33.0-rc2` pin remains unchanged |
| Common integration environment | Lean `4.33.1`; native objects at `integration/.lake/build/lib/lean` |
| Common Mathlib | Commit `0df444a360eaa60ab8c11dca51a86af692955474` in both environments |
| Native rebuild receipt | `integration/NATIVE_COMMON_PIN_BUILD.json`, successful schema 1 receipt covering exactly 572 native modules |
| Exporter | `leanprover/lean4export` tag `v4.33.0`, commit `15f6055e299ad5b89345e533cc2192f4cc00f659`, built with Lean `4.33.1` |
| Official judging toolchain | Lean `4.36.0`, with bundled `lake comparator`, `leanchecker-paranoid` and `nanoda_bin`; its normal platform and sandbox prerequisites apply |
| Statement comparison helper | Build the supplied `comparison_control` project with Lean `4.33.1` |

The native source directory is inferred from the `Zeta23` library's `srcDir` in the integration `lakefile.toml`; `--native` can specify it explicitly. The prepared canonical environment and verification tools are trusted inputs. Object hashes record their actual bytes and later stability; they are not self-authenticating build provenance.

The helper vendors the unchanged upstream comparison algorithm at commit `865edc14486c3388e9225daa971da8e157488c3e` and the matching export parser. `UPSTREAM_IDENTITY.json` and `SOURCE_FREEZE.json` record these sources. The helper is a comparison and axiom-audit tool. It does not implement a kernel.

## Run

First build the small helper with the Lean 4.33.1 Lake binary:

~~~sh
cd /absolute/path/to/portable_gate/comparison_control
/absolute/path/to/lean-4.33.1-linux/bin/lake build compare_exports
~~~

Then run the gate:

~~~sh
python /absolute/path/to/portable_gate/verify_combined.py \
  --external /absolute/path/to/full-original-proof \
  --integration /absolute/path/to/common-pin-integration \
  --lake /absolute/path/to/lean-4.33.1-linux/bin/lake \
  --exporter /absolute/path/to/lean4export/.lake/build/bin/lean4export \
  --comparator-lake /absolute/path/to/lean-4.36.0-linux/bin/lake \
  --output /absolute/path/to/fresh-evidence-directory
~~~

The comparison helper defaults to the binary built inside this package. `--comparison-helper` can give another trusted build's path. The output directory must be fresh, empty and outside both governed source checkouts. Its default is a uniquely named directory under the integration workspace's parent.

The runner does not update either repository, change original pins, rebuild dependency repositories or overwrite their objects. It compiles the four portable source modules into fresh output directories. The canonical fingerprint is compiled independently a second time in the combined environment.

Do not change the prepared inputs during a run. The gate compares every shared package and core object against the canonical environment, rejects import-root shadowing, records all objects present in the searched dependency roots, and rechecks inventories and hashes at the end. Hashing large original proof objects and exporting/replaying the complete certificate can require substantial storage, memory and time.

## Exact source identity

The recognized external checkpoints are:

| Commit | Role |
| --- | --- |
| `bdb1810a06c78f246da285c9bcbe7db2cd992888` | User fork source checkpoint |
| `9266b88245feaf2906ebba592613dd8098b0e8f6` | Upstream infrastructure checkpoint |
| `40e56bab026552e089d7afcfeff08d2defb9c005` | Original mirror checkpoint |

An explicit full `--external-head` is checked exactly and still must pass the canonical source inventory check. All accepted inventories have the same original source after omitting exactly `src/Challenge.lean`. That upstream comparison challenge is outside the imported proof endpoint; its exclusion never permits a placeholder in an imported proof.

The accepted inventory contains 175,187 entries with SHA256:

~~~text
16f09dc78678562246fd2d80dd2244a20d9d590576467a290f7f8ccbfb4426bc
~~~

Its bytes are the sorted, NUL-separated recursive `git ls-tree` records under `src`, with only `src/Challenge.lean` omitted and one trailing NUL. Working-tree changes to protected proof sources or pins are rejected. The portable proof sources, comparison configuration and helper/control sources are separately hash-bound by `GATE_SPEC.json`.

**Source identity and certificate validity are separate records.** This runner does not certify that every supplied external object was built from the corresponding source file. It reports external source-to-object provenance as unestablished by the object snapshots. An independently compared canonical target and a completely checked proof certificate can establish the target without inventing a provenance receipt. No user-created manifest plus its own hash is promoted to authenticated build evidence.

## Native rebuild receipt

The existing native builder's schema 1 receipt must have `status: PASS`, `exit_code: 0`, the exact native head/tree above, the common Mathlib revision, and the exact `lean --version` string. Its `modules` array must cover precisely all 572 native source dependencies of `ZeroFreeFloor`, with no duplicate, missing or additional module.

Each row supplies `module`, `source_path`, `source_sha256`, `object_path`, `object_sha256`, `preexisting_object: false`, and `source_unchanged: true`. The gate independently reconstructs the native source import closure, checks actual source/object hashes and checks resolution against the prepared native root. Recorded absolute paths can be relocated; their module-relative suffixes and actual digests must still match. Unknown metadata fields are tolerated.

This records the prepared conditional receiver build. It is not itself the closed C1 claim. A RUNNING receipt, a failed build, a missing exit code or reused preexisting native objects cannot pass.

## Required validation sequence

The complete sequence is implemented in `verify_combined.py` and recorded stage by stage:

1. Verify protected source identities and pins and require the real external endpoint object.
2. Establish the native-only canonical environment, the trusted tool paths and the completed native rebuild receipt.
3. Snapshot canonical dependencies, freshly compile the canonical fingerprint and export its complete statement dependencies, including the standard kernel primitives and permitted axioms.
4. Establish the combined environment. Require exact shared package and core object identity, reject shadowed native/package/core modules and snapshot the searched dependency objects.
5. Run positive and changed-definition controls for both the small comparison helper and official Comparator. A changed proposition body must be rejected at that definition.
6. Freshly compile the combined fingerprint, `ClosedBridge`, `IndependentConsumer` and `ClaimComparison`.
7. Audit complete printed types and transitive axioms for all six closed declarations. Universe annotations on the three standard axioms are normalized; other axiom names are rejected.
8. Explicitly export all six closed declarations, the fingerprints, primitives and axioms to one augmented solution export.
9. Run the helper on that exact export with `--closed`. Check the exact closed C1/RH theorem types and transitive axioms in the export itself.
10. Run official Lean 4.36.0 `lake comparator` with `--challenge-from-export` and `--solution-from-export`, so it consumes the bound exports without rebuilding or exporting only the configured fingerprint roots. Lean's default kernel, the paranoid kernel and nanoda judge that same augmented solution export.
11. Replay the bridge, named independent consumer and comparison consumer with Lean 4.33.1 `leanchecker`; then run mandatory `--fresh` on `ClaimComparison`, which includes the entire `IndependentConsumer` and external proof import closure.
12. Recheck protected sources, package pins, object inventories, all bound input hashes and all fresh products.

There is no skip-fresh or force-pass option. Nonzero exits, signals, timeouts, missing success markers and error/warning/placeholder diagnostics cannot become a proof pass. The intentionally failing semantic controls are identified as expected rejections; proof stages never use that exception.

The default budgets are two hours per module compilation, four hours per ordinary module replay, and twenty-four hours each for full export, comparison and fresh replay. Options can increase budgets without weakening checks.

## Receipts and claim boundaries

Every stage writes a JSON receipt. Each process writes a raw log, command, exit code and hashes. Exports have separate stdout artifacts and stderr logs, so diagnostic output cannot silently contaminate a proof export. Unrun stages remain `NOT_RUN`.

The aggregate is `COMBINED_GATE_RECEIPT.json`:

| Exit | Status | Meaning |
| --- | --- | --- |
| `0` | `PASS` | All canonical-definition, exact closed-type, axiom, kernel and integrity gates passed for the recorded certificate. |
| `1` | `FAIL` | A validation or process check failed. |
| `2` | `BLOCKED` or `INCOMPLETE` | A required input, tool, completed receipt or resource budget was unavailable. |
| `130` | `INTERRUPTED` | The operator interrupted the run. |

Only complete success yields `EXACT_CANONICAL_NATIVE_C1_PROVED_AT_RECORDED_INTEGRATION_PIN`. Even then the aggregate keeps the following distinctions:

- Native original-pin compilation and Round4 eleven-lane production acceptance remain `NOT_RUN_NOT_CLAIMED` by this isolated gate.
- External source-to-object provenance is not certified by a hash snapshot.
- A fingerprint theorem or comparison control proves neither C1 nor RH.
- Historical masked/survivor Möbius-cell estimates, strict positivity and coercivity are not silently included in the C1 statement.

## Reproducible controls and current limits

The Python machinery tests run with and without optimization:

~~~sh
python -m unittest -v test_verify_combined.py
python -O -m unittest -v test_verify_combined.py
~~~

They challenge missing/duplicate/truncated theorem types, missing/extra/forbidden axiom reports, polymorphic standard axioms, zero-exit error/warning diagnostics, timeouts, missing closed export roots, altered shared objects, import shadowing and retargeted input symlinks.

The actual semantic comparison control is:

~~~sh
python comparison_control/test_statement_definitions.py \
  --lean /absolute/path/to/lean-4.33.1-linux/bin/lean \
  --exporter /absolute/path/to/lean4export \
  --comparison-helper /absolute/path/to/compare_exports \
  --output /absolute/path/to/fresh-control-directory
~~~

It independently compiles and exports identical `True` definitions and a substituted `False` definition under the same name and the same reflexivity-theorem type. Its success requires acceptance of matching definitions and rejection specifically at the changed proposition body. This control has passed locally with the frozen helper. The real canonical C1/RH fingerprint has also been compiled, exported and compared to itself. These results validate statement preparation and the comparison mechanism; they do not validate the missing combined closed proof.

The official existing-export command was checked against Lean v4.36.0's own `comparator-from-export` regression test and `Lake/CLI/Check.lean`. Copies are included under `comparison_control/upstream-v4.36.0` for review. The full official Comparator/kernel path on the closed external solution has not run locally.
