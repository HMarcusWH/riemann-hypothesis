# Stock Lean import phase diagnostic

**This workflow measures resource use and import phases. It does not accept a proof or construct a Step 4 theorem. Step 4, C1 and RH remain OPEN.**

## Reason for this run

The full Step 4 run at commit `2d54e707ab9ac8a50c2ed3cb2fd72b4171cb21bf`, tree `0d60ad18d4e0e95d9296ba745b355b003449a3b3`, ended with 19 modular stages PASS, `guarded_kernel_import` INCOMPLETE and ten stages NOT_RUN. The separate independent gate was skipped. [Run 45011966301](https://github.com/HMarcusWH/riemann-hypothesis/actions/runs/45011966301) recorded only `IMPORT_BEGIN` before its unchanged 1,800-second deadline. Its process exit code is literally null, and its cleanup passed.

Round23's 1 MiB SquashFS blocks and Round24's 64 KiB blocks both reached this boundary. The later run still recorded 205,465,633,792 read bytes and 4,438,270 major faults. Those sampled counters show sustained mapped-file access; they do not identify the internal import phase or establish a throughput improvement. Neither a theorem rejection, an OOM kill nor a deadlock was established.

## Exact diagnostic contract

The diagnostic starts from the unchanged Round24 source and rebuilds the same pinned native dependencies. It recreates the original supplier store with the existing 64 KiB helper and verifies all 350,374 mounted original files. The mount remains read-only and uses the existing default decompressor setting. No proof body, import, source declaration, runtime binary or supplier object is rewritten or omitted to make the probe complete.

The executable uses stock Lean 4.33.1, compiler `819816b2e0a3bf405af45ae5c7af2491d8f5bee6`, and the exact failed guard import array:

```text
Init
Init (meta)
Main
OPICAStep4.NativeValidated
Lean
```

Its split mode follows the public implementation of `Lean.importModules`: it calls `importModulesCore`, emits a flushed boundary marker, then calls `finalizeImport`. Both execute inside `withImporting`. Options, plugins and artifact overrides remain empty; the settings remain `trustLevel = 0`, `level = private`, `loadExts = false`, `leakEnv = true`.

The first probe is bounded by the unchanged process-group monitor at **600 seconds** and **50,000 MiB sampled RSS plus swap**, with the existing cleanup and telemetry behavior. The hosted diagnostic job has a 120-minute outer limit including preparation. It does not alter any original full-gate deadline or source file. The existing 97 controls and the diagnostic's own input controls must pass before expensive preparation.

The four canonical native audit modules are freshly compiled. Their source/runtime/import identities are checked, their object identities are recorded, and any difference from Round24's four object hashes is reported. A fresh build must not be called an exact reproduction of historical artifact bytes unless those identities actually match.

## Interpretation

| Last marker | What was observed | Next question |
|---|---|---|
| `CORE_BEGIN` only | Original module loading has not returned within the probe budget | Which file mappings or storage operations dominate? |
| `CORE_END`, then `FINALIZE_BEGIN` | Module loading returned; environment finalization has not returned | Is the cost in constant-map construction, extension-entry setup or persistence marking? |
| `FINALIZE_END` and `HEADER_MATCH` | The stock split import returned with the expected header | Does the unchanged full producer complete under the actual proof gate? |
| Any explicit error | The recorded operation failed | Diagnose that error before another run |

An import returning successfully is still not a kernel replay, axiom audit, definition comparison, independent proof check or closed-theorem construction. Every diagnostic receipt has `proof_acceptance = false`. The ordinary 30-stage modular gate and seven-stage independent gate are **NOT_RUN by this workflow**.

The diagnostic omits the full gate's earlier export/replay/snapshot prefix and uses its own executable. Cache warm-up, process address layout and fresh native object serialization can therefore differ from the failed run. The phase boundary is the intended evidence; timing differences are not a controlled production speedup measurement. The complete supplier bytes and source/runtime pins remain fixed, while the actual fresh native object identities are recorded separately.

The `lean-control` selection is a small local control that imports Lean only. It must never be reported as a successful supplier or guard import. The `stock` mode is available for a later explicitly selected comparison; this initial workflow requests only `exact-guard split`.

## Evidence and continuation

The artifact retains process logs, phase markers, resource observations, actual runtime/source/object identities, the fresh native build receipt and the original-store verification receipts. The original store, native dependency objects and compiled diagnostic executable are not included in the small evidence archive. Their identities and these omissions remain explicit.

A justified successor must be chosen from actual phase and resource evidence. Changing decompressor concurrency, memory, physical storage or a deadline is a separate hypothesis to test; none is assumed to solve the problem. Even if a diagnostic becomes green, the complete unchanged proof and claim obligations remain outstanding.

The original proof PR remains [PR 1](https://github.com/HMarcusWH/riemann-hypothesis/pull/1). This diagnostic branch neither merges it nor changes native production pins.
