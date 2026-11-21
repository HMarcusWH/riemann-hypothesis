# Stock kernel construction: exact scope and interface

## Purpose and boundary

This producer is a versioned alternative to the two timed-out/unevaluated source-elaboration stages. It does not make the original round20 elaborator gate pass. The original Lean files remain the mathematical specification; their three closed types and proof expressions are constructed explicitly and submitted to the pinned stock Lean kernel.

Build with the pinned Lean 4.33.1 `lake build kernel_bridge`. The accompanying `lakefile.toml` has no package dependencies and enables `warningAsError=true` and `relaxedAutoImplicit=false`. No package or toolchain update is needed. Production must bind the exact source/config/compiler/kernel/writer/runtime and built executable, then rehash them after use.

CLI:

```
kernel_bridge guard OUTPUT.olean
kernel_bridge closed OUTPUT.olean
kernel_bridge controls
```

The caller supplies a complete, unambiguous `LEAN_PATH`, fresh output paths with existing parent directories, the pinned stock runtime on `PATH`, and an external whole-process resource/timeout monitor. The tool emits flushed `OPICA21_PHASE` records around imports, checked additions, serialization and transitive axiom collection. `controls` uses only stock Init imports and temporary files; it never loads the actual supplier.

## Exact ordinary headers

All imports below have `importAll=false` and `isExported=true`. `isMeta=false` except for the second `Init` entry. Both output modules have `isModule=false`. These are the exact ordinary-source import arrays, including the two implicit imports inserted by Lean 4.33.1 `Lean.Elab.HeaderSyntax.imports`.

| Output | Imports, in order |
|---|---|
| `OPICAStep4.ImportGuard` | `Init`, meta `Init`, `Main`, `OPICAStep4.NativeValidated`, `Lean` |
| `OPICAStep4.MainClosedBridge` | `Init`, meta `Init`, `OPICAStep4.ImportGuard` |

The guard command imports that real environment and rejects any preexisting closed target name before writing the zero-declaration object. The closed command reads and validates the serialized guard, **actually imports it**, repeats the absence check, and adds exactly the three frozen theorem declarations in order. Imports use `trustLevel=0`, `loadExts=false`, `leakEnv=true`, `level=.private`. Each command runs in a separate process; imported regions are never manually freed. `leakEnv=true` is the documented process-lifetime optimization, not a validation bypass.

The checked insertion API is `Lean.Environment.addDeclCore ... (doCheck := true)`, with the stock kernel's result required to succeed. No `addDeclWithoutChecking`, `debug.skipKernelTC`, `sorry`, new project axiom or fake environment constructor is used.

## Actual object contents and metadata difference

The writer calls stock `Lean.mkModuleData` at the private level with explicit `extEntries? := some (.uniform #[])`, then stock `Lean.saveModuleData`. It requires exactly zero or three fresh stage2 constants. Imported constants remain imported dependencies. The three new constants are plain safe theorem records with exact types, level parameters, full proof ASTs and mutual-group fields; they introduce no inductive or quotient scaffolding. Existing scaffolding comes from the actual imported kernel environment and remains covered by the downstream validation gates.

Each object is reread with stock `readModuleData`. The full header, count, name table, duplicate freedom, exact complete `TheoremVal` records, zero extension entries and zero `extraConstNames` are checked. Existing outputs and any authored `.olean.server`, `.olean.private`, `.ir` or `.ir.sig` sidecars are rejected.

Empty **new extension entries** are intentional. They do not mean empty logical dependencies or empty axiom sets. This avoids `computeExtEntries` callbacks, notably the exported-axiom extension's additional large proof walk when imported extensions have not been initialized. This is not a byte-identical elaborator object and is not represented as such.

## Exact public type and axiom audit

After successful serialization/readback, the tool inspects the actual kernel constants for `riemannHypothesis` and the three closed roots. It requires safe theorem kind, no universe parameters or free/metavariables, and exact constant types. It prints the original `OPICA19_TYPE_BEGIN`/`OPICA19_TYPE_END` records and standard parse-compatible `'name' depends on axioms: [...]` lines.

A shared monotone worklist propagates a reachability bit per public root. This computes separate actual axiom sets while sharing the large supplier dependency traversal. It follows every type and available body using `ConstantInfo.value? (allowOpaque := true)`, as well as projection names, mutual inductive/constructor metadata and recursor rules. Missing constants, unsafe/partial logical dependencies and axioms outside `propext`, `Classical.choice`, `Quot.sound` fail closed. The initial/serialized axiom extension is never consulted. Cycles are handled by monotone propagation until a fixed point; no partial recursion cache can erase a dependency.

The stock kernel checks the new proof expressions in the imported environment. Importing at trust level zero alone does **not** replay every imported proof. Therefore the retained independent raw-object inspector, actual type/axiom audit, both named stock kernel replays, complete native proof identity, complete supplier export identity, exact canonical definition comparison, complete independent selected proof/type closure and final input rehash are necessary parts of acceptance. This producer alone supplies no C1/RH claim authority.

## Exact requested-root eligibility inventory

The v4 producer additionally looks up the exact **50 requested independent-checker roots** in the already-loaded actual closed environment, in the same order as the modular and independent runners: 38 supplier roots, 9 native roots, and 3 newly closed roots. `SELECTED_ROOT_INVENTORY.json` records the exact lists and their derivation by AST evaluation of the modular runner's literal constants. The producer checks cardinalities 50 and 17, duplicate freedom, presence, and absence of unsafe/partial flags. The 5 supplier headline theorems, 9 native mathematical roots and 3 closed roots must specifically have ordinary `thmInfo` kind. Primitive, quotient, inductive, constructor and axiom roots keep their legitimate kinds.

After each successful check the producer emits exactly one `OPICA21_SAFE_SELECTED_ROOT <name>` line, in the frozen order. Production acceptance requires that complete ordered inventory in addition to successful process completion. This prevents a requested unsafe/partial root from silently disappearing when a downstream checker skips ineligible declarations. It is a cheap kind/presence guard, not an additional transitive proof or axiom walk; the retained complete independent selected closure remains necessary. Local controls exercise the guard on core fixtures, not the actual 50-root supplier environment.

## Local evidence and remaining resource uncertainty

The native controls passed on the actual pinned runtime. They wrote a zero-declaration core guard, reimported it, wrote three harmless safe theorem/alias/Iff.mp objects with exact readback, and replayed the result using the pinned stock `leanchecker`. They also rejected an invalid proof, a reused name, a theorem reaching a forbidden axiom through an opaque body, and an unresolved logical dependency; an unrelated axiom did not contaminate the safe root.

The preserved v3 native control run took 2.37262 seconds under a 60-second and 4-GiB whole-process limit, with sampled RSS+swap 1,318,457,344 bytes. Its exact receipt is `native_controls_v3/native_writer_and_adversarial_controls.process.json`, with source/config/binary identity in `native_controls_v3/CONTROL_BINDING.json`; its source/config/spec remain under `frozen_v3/`. Both stock-checker child streams are forwarded into the monitored parent log before checking exit status; exactly one expected verbose module replay line is required. Stock verbose mode does not expose individual declaration names, so those names and complete values are checked by the actual object reread instead.

For v4, fresh strict stock C generation and native linking passed in 3.092777 and 3.165882 seconds, respectively. The final native controls passed in 2.02187 seconds with sampled RSS+swap 1,318,641,664 bytes under the same 60-second and 4-GiB bound. In addition to all previous writer/reimport/replay and dependency controls, these controls reject missing, duplicate, wrong-kind, unsafe and partial selected roots, and accept legitimate core theorem/inductive/quotient kinds. All eleven required success markers occur exactly once; fixtures emit no production selected-root inventory claims. Exact process receipts/logs/telemetry and source/config/runtime/generated-C/executable before/after bindings are in `native_controls_v4/`, driven by `run_v4_controls.py`. The exact CI Lake build remains separately assigned to the parent. These are mechanism controls, not an actual `Main` import, execution of the actual 50-root inventory, or a closed C1 proof.

An earlier interpreter-hosted native-only conditional probe exceeded its 4-GiB watchdog after 17.826 seconds, without a Lean diagnostic or kernel rejection. That incomplete attempt is preserved separately. `loadExts=false` still loads the module graph, private constant maps and IR/imported entry data; only expensive extension initialization is skipped. The original one-hour timeout had no subphase or RSS evidence, so no full-supplier runtime or memory guarantee follows from these small controls.

## Post-green disposition

The formal theorem inventory and mathematical assumptions are unchanged by v4. What became tested is the mechanism that prevents requested roots from being skipped on safety/kind grounds; the three production proof expressions are unchanged. The fresh compiler/native-link controls are implementation validity checks, the ordinary-object replay is a stock kernel mechanism regression, and the negative controls are fail-closed regressions. None is a new RH-relevant mathematical theorem. The previous elaborator timeout remains incomplete, and the original gate is not retrospectively marked passed.

The next decisive check is the full versioned production run with actual inputs, exact ordered-root markers, proof/type identity, complete independent closure and final rehash. It must either produce all required evidence or localize the remaining resource/semantic failure. No further optional local theorem or broad-import work is required before that check. C1 and RH remain OPEN here.
