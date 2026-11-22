# Round24 execution handover — 22 November 2026

## Exact source and pending execution

The reviewed storage-experiment source is commit
`9e3d30f25cb7ba442e4707f88fb67a513721093f`, tree
`4fe5cf7211a4609cd85e57f1c37e1a4ded3436c1`. At the 10:09 UTC recheck, PR #1
still had that head and all 20 returned Actions runs were terminal; none was a
Round24 execution. The workflow has now been enabled. The next run must record
its actual checked commit, tree, attempt and job IDs before any result is
attributed to it.

This dated handover records completed local controls and corrects the earlier
resource interpretation. Its accompanying source-manifest entry changes only
documentation and inventory. The supplier `src` tree remains
`24df20b62d9976ccd20da819bc20b16f808f0fdd`; all 25 Step4 Lean files, executable
gate sources, toolchain pins, ordered roots and workflow bytes are unchanged.
The workflow passes its actual `${{ github.sha }}` as the explicit external
head, so execution evidence belongs to the new documentation descendant.

## Completed local controls

All 97 published Python controls passed locally on the reviewed commit from
02:02:11 to 02:02:20 UTC on 22 November 2026, with exit zero and no skipped
tests:

| Published suites | Tests | Result |
|---|---:|---|
| `test_verified_squashfs_store`, `test_export_stream_store` | 24 | PASS |
| `test_verify_modular`, `test_monitored_process` | 60 | PASS |
| `test_independent` | 13 | PASS |

All 79 checked workflow/Step4 source files were hashed before and after those
commands and were unchanged. The replay used Python 3.12,
`zstandard==0.25.0`, and separately built official squashfs-tools 4.6.1 at
`d8cb82d9840330f9344ec37b992595b5d7b44184`, with zstd support enabled.
The receipts retain the binary hashes and build options.

Evidence identities:

- `LOCAL_CONTROL_RECEIPT.json`: SHA256
  `52500d7c5cbbf7805a3f337e4011d326610b8ed6df88dddfa454e35de0ce6f67`.
- `CHECKED_SOURCE_FILES.json`: SHA256
  `00f36c13edb4c159b656ff8d2e9bf372f8867f3d74a1d18eb371c4419233578a`.
- `Round24_Local_Control_Review_2026-11-22.zip`: 140,975 bytes, SHA256
  `1ad89ffd92e1f3245127fbcdbfab2298d19f1f1ee29271ff0e0bad83353c1156`.

The archive contains the control logs, source manifest, monitor fixtures and
resource correction. These are local mechanism/regression results. They do
not establish a production supplier import, a modular PASS, an independent
combined-proof PASS or a new Lean theorem. The fresh Actions execution still
runs its complete control and proof sequence.

## Corrected Round23 resource evidence

[Round23 run 44954415707, job 136999254211](https://github.com/HMarcusWH/riemann-hypothesis/actions/runs/44954415707/job/136999254211)
recorded successful runner preparation. Its initial 3 GiB swap snapshot was
taken before the additional 40 GiB swap file was activated:

| Resource | Before preparation | After preparation |
|---|---:|---:|
| `MemTotal` | 16,366,512 kB | 16,366,512 kB |
| `SwapTotal` | 3,145,724 kB | 45,088,760 kB |

The proof attempt therefore had approximately 15.6 GiB physical RAM and 43 GiB
swap after preparation. The 50,000 MiB watchdog threshold measures sampled
process RSS plus swap; it is not physical RAM or a kernel-enforced allocation.
Neither the corrected capacity nor the timeout establishes OOM, deadlock or a
semantic proof failure.

Round23 remains 19 PASS / 1 INCOMPLETE / 10 NOT_RUN. Its guarded original
supplier import ended after 1,800.828 seconds with only `IMPORT_BEGIN`, exit
-15 and confirmed cleanup. No guard or closed object was produced, and the
independent gate was skipped.

## Run and acceptance contract

Round24 retains the original supplier bytes and changes the SquashFS data
block to 64 KiB. Storage/read amplification remains a HYPOTHESIS until the
full run supplies measurements. The 40 GiB image cap, disk preflights and
1,800-second import deadline remain in force. Passing the small transport
fixtures does not predict full-image capacity or import time.

The complete acceptance sequence is:

1. Fresh resource preparation, all 97 controls, the 572-module native build,
   all 350,374 original mounted-file checks, and pinned verification tools.
2. All 30 modular stages passing in order, including actual guarded import,
   the three fresh closed theorem objects, exact type/axiom audits, stock
   kernel replays, complete native and supplier proof identities, canonical
   definition comparison and final input integrity.
3. All seven independent stages passing, including all 50 ordered roots,
   the 17 safe ordinary mathematical theorem roots, complete statement/proof
   dependency closure, consistent accepted-record counts of at least
   1,468,421, zero synthesized prelude and successful cleanup.
4. Artifact and manifest verification, harvest of every workflow/job result,
   and the project claim review plus Post-Green Research Pass on the exact
   successful proof and surrounding definitions.

The outer job deadline remains 360 minutes. Individual stage budgets do not
guarantee that the whole sequence fits; an incomplete stage stays incomplete.
The authoritative receipts are `MODULAR_GATE_RECEIPT.json` and
`INDEPENDENT_RECEIPT.json`, bound to the actual execution head and inputs.
The original Round19 procedure and original native-pin rebuild retain their
separate status. C1 and RH remain OPEN pending the complete required proof
and claim-validation evidence.

## First hosted execution and control correction — 10:17 UTC

The enabled workflow ran as [45011433999, attempt 1](https://github.com/HMarcusWH/riemann-hypothesis/actions/runs/45011433999)
at exact documentation head `c7a44302dd4a616c3b26208222732e751b5c216d`, tree
`14c8e5ee6a857a8275c47e29126ebcdb4b87f978`, job `137174408329`.
Runner preparation passed. The transport suite passed 24 controls. The
60-control modular/monitor suite then ended with one error: the terminated
child's `/proc/<pid>/stat` disappeared between `exists()` and `read_text()` in
`test_timeout_kills_descendant_after_producer_leader_exits`. The independent
control suite and every native, supplier and proof stage were skipped. This
run supplies no modular or independent proof receipt and no theorem result.

The failure artifact `14749943087` is 2,305 bytes, SHA256
`a264ae7d9ee0f9d258b7efe1ae79a34686f1b68558f339b9bae031f99981a596`.
It preserves runner resources; the terminal job log preserves the traceback.

The next descendant corrects only the two test-side `/proc` observation races:
read the state directly, accept only `FileNotFoundError` as an already reaped
child, and otherwise retain the `Z`/`X` requirement. A readable live child
still fails. Other read errors and malformed states remain errors. The test's
required `GateIncomplete` result, polling budget, production cleanup code,
proof verifiers, Lean sources, workflow, source pins and all stage deadlines
are unchanged. The source manifest records the changed test and this handover.

The corrected source passed all 97 published controls locally, plus six
focused cases: disappearance between reads, an already reaped child, `X`
state, rejection of a live child, propagation of a permission error and
propagation of a malformed-state error. These controls are mechanism evidence,
not a Step4 or RH proof. Local review receipt SHA256:
`6b40bc1de7b714761383c928f680b1cf1b4b2e32aa74542d0daf499adf3bece7`.

The successor Actions run must record its own exact commit/tree/run identity
and execute the full acceptance sequence above. The failed run is retained as
a distinct attempt; it is not relabelled as passed.
