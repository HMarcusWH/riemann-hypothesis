# Native bootstrap object custody — additive candidate v1

## Status and purpose

This candidate preserves exact compiled bytes that the existing full-gate evidence collector omits. It is a custody and reconstruction preparation tool. It does not compile Lean, run a kernel checker, decide a theorem, migrate native pins, change an acceptance profile, or create production acceptance.

The candidate adds this specification, `collect_native_capsule.py`, and its fixture tests. It leaves the original collector, all thirty modular stages, all seven independent stages, and the active diagnostic unchanged. The current native nineteen-path runtime/source-policy candidate is also unchanged.

**RH, Step 4, native production acceptance, and joint acceptance remain OPEN.** A successful custody operation means exact bytes were retained and read back successfully. It supplies no logical authority beyond the separately authenticated build/proof evidence.

## Exact scope

The frozen common-pin native build receipt identifies 576 modules and 1,155 produced files:

| Role | Modules | `.olean` | `.ilean` | Other sidecars | Total files |
|---|---:|---:|---:|---:|---:|
| Native `Zeta23` dependency closure | 572 | 572 | 572 | 3 | **1,147** |
| Authored bootstrap audit modules | 4 | 4 | 4 | 0 | **8** |
| Complete build-receipt custody | **576** | **576** | **576** | **3** | **1,155** |

The three additional sidecars are `.olean.private`, `.olean.server`, and `.ir` for `Zeta23.FromPNTPlus.EulerMaclaurin`. The four authored modules are `OPICAStep4.ReceiverAudit`, `OPICAStep4.ClaimFingerprint`, `OPICAStep4.BoundaryFlatCharacterization`, and `OPICAStep4.NativeBootstrapAudit`.

This profile fixes those names, the 572 native source identities, all four authored source identities, the common compiler identity, and the required sidecar sets. Every object/sidecar hash must come from the current fresh build receipt and match the actual file. An omission from the receipt cannot silently redefine completeness. Changed toolchains, source inventories, or sidecar conventions require a separately reviewed successor profile.

The original collector is **still required**. It covers the proof-run canonical modules, generated type/axiom audits, future guard and closed objects, proof/replay reports, and independent-checker evidence. `NativeValidated` and `NativeTypesAudit` are different modules from `NativeBootstrapAudit`; one is not a substitute for the other's bytes.

## Evidence that motivated the change

The Round23 and Round24 retained receipts independently agree on 572 native objects within each run. Comparing the two runs shows 147 different native `.olean` hashes, 425 unchanged hashes, no native source-hash changes, and no changes among the 575 native sidecars. The full input snapshots contain no other changed entries after normalizing the run-directory segment.

The old collector did not traverse `native/integration/.lake/build/lib/lean`, and it skipped `.ir` files. Its retained snapshots contain paths and SHA256 hashes, without native per-file sizes. None of the 1,147 native payloads was retained. Therefore the total native payload size is **unknown**, not zero and not a value recoverable from those hashes. The dependency-reference byte total and sampled RSS are not native output sizes.

Exact-hash matching also shows that six of the eight bootstrap-authored files were retained under the canonical verification roots. Both `NativeBootstrapAudit` files were absent. This candidate therefore retains all eight explicitly, avoiding dependence on incidental duplicate bytes in another artifact.

These observations are documented in the separate inventory audit and correction receipt accompanying this preparation. They justify retaining current objects; they do not establish why the 147 serializations differed or imply a logical difference between the proofs.

## Required inputs and immutable references

Collection requires the actual current work directory, the supplier checkout at an explicit full commit SHA, a fresh output directory, and explicit per-member and aggregate byte budgets. Absolute source/object paths in the fresh receipt must match that work directory exactly; historical receipts are not silently rebased onto newly rebuilt objects.

The collector authenticates these frozen metadata files by SHA256:

- `native_sources.json`: the exact 572-module source inventory at native commit `7597acdba0c7d0a81b8c3a5f229598e3f9b74ac9`, tree `9248b76d7aff60aab3bb775c4be9750dc6006003`.
- `runtime_files.json`: 26 stock runtime file identities plus the immutable Lean 4.33.1 archive identity.
- `lake-manifest.json`: the exact nine common dependency pins, including Mathlib `0df444a360eaa60ab8c11dca51a86af692955474`.
- `trusted_objects.json.gz`: the frozen dependency-object reference inventory.

The fresh native receipt must report the correct compiler and executable hashes, source identities, successful build status, unchanged source, and no preexisting native objects. Its metadata is retained verbatim. The collector does not reinterpret a synthetic or forged receipt as compiler evidence; the existing formal gates remain responsible for that acceptance.

The capsule embeds metadata references to the original supplier source tree `24df20b62d9976ccd20da819bc20b16f808f0fdd`, the immutable supplier dataset revision, and its archive/manifest hashes. It does **not** archive native `.lean` source copies, runtime binaries, common dependency payloads, the 30GB SquashFS image, or the original supplier object archive.

Where present, the collector also preserves the modular/independent and supplier-transport receipts, matches all 572 `NATIVE_VALIDATED_INPUTS.json` object identities to the build receipt, and hashes the existing `evidence.zip`. Missing gate context is recorded as missing. It cannot become evidence that a gate passed. Complete bootstrap-object custody can exist while every mathematical/production acceptance field remains OPEN.

## Byte, path, and completeness rules

Paths are derived from the frozen module inventory and fixed native library root. Receipt paths must match exactly. Descriptor-relative opens reject final symlinks and symlinks in parent directories; nonregular files are rejected. Duplicate JSON keys, duplicate/missing/extra module names, missing required sidecar records, substituted paths, and unrecognized receipt sidecar keys cannot qualify. The on-disk undeclared-sidecar check covers the four registered suffixes (`.ilean`, `.olean.private`, `.olean.server`, `.ir`); it is not a generic discovery scan for every other sibling filename or future compiler convention.

Preflight records actual sizes and hashes and compares them with the receipt. It reports native and authored bytes separately. Missing/unreadable size information is `null` at the relevant total, with a count of unknown-size files; it is never reported as measured zero. Oversized members are explicitly marked, and total-budget failure is reported even when every individual member is valid.

The collector refuses an existing output directory. It measures available disk before writing an uncompressed ZIP, streams each member with byte bounds, checks descriptor identities and hashes across each copy, and checks current identities again after copying. It then verifies the exact archive member set and reads every payload back, checking length and SHA256. Final archive publication uses an exclusive hard link, so a competing final filename cannot be overwritten.

Expected dispositions include:

| Condition | Outcome |
|---|---|
| All 1,155 products and metadata verified and archive readback passes | `COMPLETE_BUILD_RECEIPT_CUSTODY_ONLY`; exit 0 |
| Required file absent | File `MISSING`; overall incomplete; unknown size remains `null` |
| Member exceeds explicit limit | `OVERSIZE_MEMBER`; no complete archive |
| Sum exceeds explicit aggregate limit | `OVERSIZE_TOTAL`; no complete archive |
| Expected hash differs | `HASH_MISMATCH`; no complete archive |
| Required path traverses a symlink or cannot be read safely | `UNSAFE_OR_UNREADABLE`; no complete archive |
| Receipt omits a produced sidecar from the frozen four-suffix set | Explicit inventory error or `UNDECLARED_PRODUCED_SIDECAR` |
| Input changes while or after being copied | Explicit drift disposition; incomplete archive only |
| Archive readback, disk write, or exclusive publication fails | Overall incomplete; exit 2 |
| Output directory already exists | Refused before collection; existing contents preserved |

A failed collection never promotes `native-objects.partial.zip` to an accepted complete archive. Its external `CUSTODY_MANIFEST.json` records the failure and any partial archive identity. A complete archive still has `proof_acceptance=false`, `step4=OPEN`, and `rh=OPEN`.

## Proposed operational use — future reviewed execution only

1. Apply these three added files to a new, separately reviewed supplier branch. Do not apply them to the active diagnostic or amend a running head.
2. Retain the existing full-gate workflow, all original proof/checker commands, and the original `collect_evidence.py` invocation.
3. After the original collector, invoke this collector against the **same live work directory and exact head**, before its native files can expire. Keep it in a separate `if: always()` collection step so a mathematical timeout does not erase available custody evidence. Missing or failed bootstrap input must still report incomplete custody.
4. Supply explicit reviewed budgets. The native byte total is currently unknown. The collector measures it during preflight, and an inadequate budget produces an explicit incomplete report; a larger budget must not be inferred silently.
5. Upload the original `evidence.zip`, the separate `CUSTODY_MANIFEST.json`, and either the completed `native-objects.zip` or a clearly labelled partial ZIP. Preserve upload results and byte/hash identities. A custody-helper failure must not hide the original mathematical gate disposition.
6. A later consumer verifies both artifacts, their same-run/native-input bindings, all module hashes, and the separately required proof acceptance. Mapping archive member names to a new import root is a future explicitly validated reconstruction operation; it is not implemented as automatic import acceptance here.

Example invocation, with **illustrative explicit limits rather than measured requirements**:

```sh
python supplier/opica-step4/custody/collect_native_capsule.py \
  --work "$OPICA_WORK" --supplier "$GITHUB_WORKSPACE/supplier" \
  --head "$EXACT_CHECKED_HEAD" \
  --output "$OPICA_WORK/native-object-capsule" \
  --max-member-mib 512 --max-total-mib 4096
```

No workflow edit, push, dispatch, native pin application, source rebuild, or full proof rerun is part of this preparation.

## Review after the local control gate

**What became checked:** synthetic fixtures exercise complete 1,155-file custody, exact readback, omission, changed hashes, independent member/total limits, source-reference drift, missing authored audits, gate-input mismatch, substituted paths, symlink ancestors, output overwrite, mid-collection drift, and archive corruption. These are Python behavior checks, not Lean results.

**Workflow harvest:** no hosted custody collection or mathematical workflow was run for this candidate. The independently recorded Round24 modular incompleteness and skipped independent check retain their original dispositions.

**What changed:** the preparation now has a concrete path for preserving all fresh bootstrap outputs. It does not depend on recomputing identical object serialization from logically equivalent exports.

**Upstream and downstream implications:** immutable source/proof identity and serialization identity must remain distinct. Retained object bytes can remove an avoidable reproducibility blocker from a later accepted common-pin receiver, but cannot supply missing proof or production authority.

**Resurrected route and falsification:** reconstructing the exact checked import environment becomes a testable future route once the capsule is captured. The fastest falsification checks are a missing EulerMaclaurin sidecar, a mismatched native receipt hash, a changed canonical module, or an absent original proof artifact. Each remains a blocker until explicitly resolved.

**Highest-value next move:** obtain one real complete custody capsule during an otherwise authorized future exact-head proof run, verify its retrieval and reconstruction, and continue the mathematical/production gates separately. No new RH theorem or mathematical clue is claimed by these infrastructure checks.
