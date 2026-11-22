# OPICA long-running Step 4 verification — versioned execution protocol

**Status:** implementation source; not an acceptance receipt. **Terminal claim:** `C1_OPEN / RH_OPEN` until the complete exact checks pass.

This is a **new execution profile** over the frozen `OPICA23_KERNEL_OBJECT_COMPOSITION_V1` mathematical gate. The original `.github/workflows/opica-combined-modular.yml`, `opica-step4/modular/` source, proof objects, independent checker, old Round19 gate, proof target and 50 selected roots remain unmodified. Historical failed/incomplete jobs are immutable evidence.

## Authority and why this exists

The frozen Round24 run 45029482502 (head `51a2aab2566ed9736f6c4fcddbcfeea74d90e09d`) passed modular stages 1–19, reached its 1,800-second Stage 20 guarded import deadline and never constructed the guard or three closed theorem objects. The independently instrumented Round26 matched-prefix run 45043676060 (head `3ce05c7f351ecd811eea1a15ae35d826c13dad89`) measured an 800.142-second completed import core, entered `finalizeImport` and exhausted 1,800 seconds with **no finalization-complete marker**. It reported no kernel rejection. This is an incomplete computation, not evidence of a valid proof.

The new workflow is **manual only** on a dedicated disposable `opica-longrun` self-hosted machine. It must not run untrusted fork code. The operator must supply an exact audited Git commit, use the exact pinned supplier/native objects, and install a root-controlled host identity marker as specified in `PROFILE.json`. Host resource minima are proposals, not proved requirements. The workflow intentionally has no automatic `push` or `pull_request_target` trigger.

## Mathematical firewall

Full acceptance still requires 30 original modular stage functions **and** all seven original independent stages in order. The original supplier proof export SHA256, all 38 supplier roots, the nine native roots, the three exact new roots, native proof-body and type equality, complete import/object inventories, stock kernel checks, canonical definitions and allowed axioms (`propext`, `Classical.choice`, `Quot.sound`) remain mandatory. In particular, source compilation with five intentional Challenge `sorry` placeholders is not RH acceptance.

The long-run adapter inherits the original `ModularGate`. Only the per-process deadline for `guarded_kernel_import` and `fresh_closed_kernel_construction` is overridden under the frozen, audited profile. It never changes proof code, imports, `trustLevel`, `loadExts`, root selection, axiom policy, or the independent checker. The original modular receipt continues to bind the old runner/source hash, while the separate long-run controller receipt binds the adapter and profile. A changed timeout has no proof authority.

## Execution and claim states

- `pilot_stage20`: run the exact original first 20 modular methods, **stop after the actual guard import and raw guard-object audit**, and preserve the other ten as `NOT_RUN`. Never output a modular `PASS` or trigger independent checking.
- `full`: run the original all-30 modular process with two stage-specific timeout overrides; only on full original modular `PASS` execute the unchanged seven-stage independent checker, on the same immutable prepared input environment.
- The outer job is up to 1,200 minutes (20 hours) on a self-hosted runner; per-stage limits are still finite, logs/IO/EOF/RSS+swap/cleanup remain bounded. A timeout stays `INCOMPLETE`.
- Save all raw process receipts and stage artifacts with source/host identity. A summary uploaded by GitHub is evidence, not a substitute for source-object/kernel checks.
- For longer-than-job execution, `checkpoint.py` seals **completed** boundary outputs for audit; `resume.py` refuses to skip previously checked stages. Actual trust-preserving cross-job resumption requires a separately validated implementation and is not silently enabled.

## Runbook

1. Provision a clean disposable self-hosted runner labeled `opica-longrun`, at least the minimum RAM/SSD/CPU in `PROFILE.json`, and root-owned `/etc/opica/ephemeral-runner.json` with matching runner identity. Do not put secrets into the working tree.
2. On a reviewed commit descended from the frozen parent, manually dispatch `opica-longrun-verify.yml` with exact Git SHA, profile ID and `pilot_stage20` for the first run.
3. Inspect the exact pilot `LONGRUN_CONTROLLER_RECEIPT.json` and source/host/operation logs. A successful pilot only proves actual guard execution and inspection, not Step4 closure.
4. When the pilot is completed and harvested, dispatch `full`. Require both `MODULAR_GATE_RECEIPT.json` and `INDEPENDENT_RECEIPT.json` to contain actual complete PASS (30 + 7), with complete final source/object integrity. Do not reinterpret previously incomplete gates.
5. Perform the Post-Green Research Pass: inspect every workflow job; read checked declarations and proof dependencies; compare earlier routes and falsifiers; identify the next independent arithmetic theorem question.

**No host is provisioned and no long-run proof job has been executed by adding these files.**
