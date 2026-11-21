# Isolated native common-pin bootstrap

This prepares the native half of the actual external-RH/C1 composition. It
rebuilds exactly the 572 native modules imported by `ZeroFreeFloor`, then builds
the literal receiver, canonical statement fingerprints and the new full
boundary-flat characterization. It supplies no closed RH or C1 theorem.

## Fresh GitHub runner

Required system programs: Python 3.11+, Git, curl, GNU tar and zstd, on Linux
x86_64. No Python packages are required. Supply an already installed verified
toolchain, or let the script download the official SHA256-pinned Lean 4.33.1
archive. A new work directory is mandatory.

```bash
python3 native_bootstrap/bootstrap_native.py \
  --work-dir "$RUNNER_TEMP/opica-native" \
  --trusted-packages "$RUNNER_TEMP/opica-trusted-packages" \
  --external-project "$RUNNER_TEMP/riemann-hypothesis" \
  --toolchain-bin "$RUNNER_TEMP/lean-4.33.1-linux/bin" \
  --jobs 2 --aggregate-rss-mb 10000 --min-free-gb 3
```

Omit `--toolchain-bin` to install the exact archive. Add `--native-source PATH`
to use an existing immutable native checkout. Otherwise the script fetches the
exact native commit with a sparse checkout covering native Lean sources and
pin files. It does not download the repository's historical PDF/data blobs.

The native repository keeps its original `lean-toolchain` and Mathlib manifest.
The script creates a **separate** `integration/` Lake project at the common
Lean 4.33.1 / Mathlib `0df444a360eaa60ab8c11dca51a86af692955474` pin.
It does not run `lake update` or rebuild the entire native repository.

## One trusted dependency environment

The trusted packages directory must sit outside both proof projects. Missing
packages are fetched from their official repositories at full immutable commit
IDs. The script verifies every source checkout and runtime binary identity.
For a fresh environment it obtains the official complete Mathlib dependency
cache once. This is shared dependency preparation, not a full native-source
build. The complete Mathlib root is needed by the external endpoint and the
unchanged combined gate.

Fresh official Mathlib cache transfers default to at most 8 concurrent
transfers, with zero automatic retries. No request-start-rate bound is enforced
or claimed: curl's `--rate` option has no effect with `--parallel`. Use
`--cache-parallel` to select a lower concurrency bound when
appropriate. HTTP 429 remains a failure; it is never masked or retried. The
transport wrapper changes neither package sources nor object verification.

`integration/.lake/packages` is a symlink to this trusted directory. The outer
workflow may point the external checkout's `.lake/packages` to the **same**
directory. The script never mutates that external checkout. Neither project
may run a dependency update or mutate shared package sources during validation.

The frozen `trusted_objects.json.gz` inventory records 20,354 dependency object
files (3,737,450,792 bytes) from the independently prepared Round 19 native-only
common-pin environment. These reference bytes are verified before and after
the fresh native build. They bind the canonical comparison's dependencies;
they are not represented as a new source-to-object build attestation. Extra
official Mathlib modules can be present for the supplier's larger closure.

This avoids duplicating Mathlib and prevents an altered dependency copied from
the external proof from silently redefining both sides of the statement test.
The original combined gate's requirement that native canonical imports resolve
outside the external project remains unchanged.

## Execution and resource bounds

Native modules are compiled with direct Lean invocations in the isolated Lake
environment, in a dependency-respecting schedule. At most `--jobs` native Lean
processes run concurrently, each with `-j1`, a Lean allocation cap, and a hard
per-process virtual-address-space limit. The bootstrap records a sampled
aggregate process-group RSS high-water mark. A one-second watchdog aborts its
process groups on the configured RSS limit, disk reserve breach or global
timeout. The aggregate RSS check is a watchdog, not a cgroup hard-memory cap.
The outer GitHub job should retain its own timeout/resource constraints.

Historical native source linter warnings are recorded and permitted. Errors,
panics, `sorryAx` and sorry diagnostics fail the build. Newly authored receiver,
fingerprint, boundary-flat and complete-type audit modules use warnings as
errors. Their nine named theorem targets must report only the standard axioms.
The three authored proof modules also undergo named-module kernel replay.

Every module object must be absent before its compilation. Sources are hashed
before and after; outputs and sidecars are hashed; all commands, exit statuses,
logs and resource observations are preserved. A partial or interrupted build
produces a non-PASS receipt and cannot satisfy the combined gate.

## Outputs and unchanged gate compatibility

The main output is:

```text
WORK_DIR/integration/NATIVE_COMMON_PIN_BUILD.json
```

Its schema and module records match the original Round 19
`verify_combined.py::native_build_receipt` contract: `schema=1`, exact native
head/tree/common pin, compiler identity, all 572 modules, fresh objects, source
stability and matching source/object SHA256s. Added audit/resource fields do not
change that schema. The main closure gate still performs its own input checks.

The remaining paths are:

- `WORK_DIR/native-source/` when no local source is supplied.
- `WORK_DIR/integration/.lake/build/lib/lean/` for freshly compiled native and
  authored objects.
- `WORK_DIR/integration/OPICAStep4/` for authored sources and generated audit.
- `WORK_DIR/bootstrap-logs/` for commands and process receipts.

For an unchanged complete gate invocation, use `--integration
WORK_DIR/integration`, `--native WORK_DIR/native-source` (or the supplied local
checkout), and `--native-receipt
WORK_DIR/integration/NATIVE_COMMON_PIN_BUILD.json`.

The standalone `--plan-only` option verifies existing native source, runtime,
package revisions and all reference object hashes without building, downloading
or creating a PASS build receipt. It requires existing `--native-source` and
`--toolchain-bin` arguments.

## Local validation scope

This package was checked by a complete read-only validation against the actual
Round 19 pinned source/runtime/dependency environment. A fresh native leaf and
the actual nine-theorem type/axiom consumer were executed through the bootstrap
compiler/process machinery. Receipt compatibility and failure controls are
recorded under `validation/`. The entire 572-module bootstrap has **not** been
rerun locally; the fresh GitHub execution owns that result.

