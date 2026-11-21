# INDEPENDENT_COMBINED_PROOF_V1

This is an additional independent checker execution after
`OPICA20_MODULAR_CERTIFICATE_COMPOSITION_V1` passes all 30 stages. It neither
modifies nor reports PASS for the original Round19 25-stage gate. It does not
claim a full combined NDJSON kernel run or a fresh compilation of con-leche's
separate soundness metatheory. Final exact common-pin claim review requires
both the modular 30-stage PASS and this complete independent-closure PASS, plus
the actual theorem/type/axiom/source evidence. This checker receipt alone does
not register a project RH claim or original-pin production acceptance. The
original 25-stage gate retains its unexecuted status and cannot be reported PASS.

## Exact object and checker

The selected module is the actual newly compiled
`OPICAStep4.MainClosedBridge`. The ordered root list is exactly the frozen
modular runner's 38 `SUPPLIER_TARGETS`, nine `AUDIT_NAMES`, and three
`CLOSED_TYPES` keys, in that order: 50 distinct roots. The complete statement
and proof dependency closure of those roots is checked from the original
`.olean` bytes. The checker is unchanged con-leche commit
`cd2eceab2e9b10404c663b468639c8aa99d0d1f2`, freshly built under its own stock
Lean 4.36.0 runtime. Original proof objects and the claim/type/axiom audits
remain at the pinned stock Lean 4.33.1 integration environment.

The official runtime archive is exactly 607,649,028 bytes with SHA256
`2b7ab1ed8b92d2e6abfaf41344823b510064dbc9c0260cac73eb496ab2dea6eb`.
Every extracted runtime file, including dynamic libraries and symlink targets,
is inventoried before and after build and before and after verification.
All tracked checker source files and the actual resulting executables are
bound. The bootstrap uses the pinned `zstandard==0.25.0` dependency already
installed for transport; its C backend's window-size argument uses bytes, and
the frame header has an additional explicit 1 GiB window limit.

## Inherited mathematical and byte identity

The wrapper requires a completed modular PASS at the explicit full external
HEAD, the exact frozen runner/spec hashes, all 30 stages once in order, and each
stage's matching on-disk receipt. It verifies the exact modular source/head/tree
and package/runtime identities, bound-file and complete object inventories,
raw three-theorem object audit, exact closed types, and the separate standard
three-axiom policy. It checks that the final native proof export matches its
canonical export and that the final supplier export matches the published
complete supplier certificate. It rehashes all inherited inputs before and
after independent checking and rejects new/missing shadow objects.

Every import root is exposed through a read-only bind mount of the exact
original inodes. If the native library contains earlier `OPICAStep4` copies,
a narrowly filtered view hides that already masked namespace. The canonical
and final first roots retain their bound fresh authored objects; the four
promoted canonical modules must have identical hashes. No dependency bytes
are substituted. The actual supplier SquashFS mount, each bind mount and the
filtered symlink map must remain unchanged through the last lazy proof read.

Read-only bind views prevent writes through those views; they are not separate
snapshots of inodes still reachable by an administrator through original
writable paths. The private sequential CI job permits no concurrent writer.
The host administrator, operating-system/filesystem implementation, system
libraries and hardware remain trusted. Pre/post hashes and mount identities
provide the recorded integrity checks under that explicit execution model.

## Fresh compatibility and fail-closed controls

The same freshly built checker must pass these controls on the actual current
Lean 4.33.1 environment before it sees the combined proof:

1. A safe unrelated theorem is accepted from an isolated fixture also containing
   an unused custom axiom (exactly two file records, plus validated prelude).
2. A selected theorem whose proof reaches that custom axiom returns exactly
   exit 2 and names the non-standard axiom; generic nonzero exits do not count.
3. A missing requested root returns exactly exit 3 and its missing-name message.
4. All 42 native roots and their proof dependencies are accepted: 65,507 records.
5. The stock canonical fingerprint export and direct-object reader agree on
   51,634 complete declaration records, including proof/value fields, with
   zero differences and zero duplicate keys. The upstream comparator only
   normalizes declaration ordering and inductive recursor ordering.

The negative fixture is created outside the governed proof-source trees and
never imported into the combined proof. It is an adversarial control only.

The combined command uses `--verified --olean` and all 50 explicit roots.
A successful process must exit zero with one exact verified acceptance line,
select exactly 50 roots, finish checking every emitted record, and report
consistent parse/check/accept counts. The accepted count must be at least the
1,468,418 original supplier records plus the three actual new closed theorems.
All explicit primitive roots must be present without synthesized prelude
records. Absent roots are rejected by the pinned reader. Unsafe/partial roots
can be skipped by that reader, so the inherited exact safe-theorem/root-kind
and type audits for the three actual new theorem declarations remain mandatory.

## Resource limits and CLI

The default combined worker count is the minimum of four and the available CPU
affinity, recorded in the receipt. The default combined time budget is 9,000
seconds; the default process-group memory budget is 50,000 MiB RSS plus swap.
The native/reader controls use one checker worker, a 900-second time budget,
and 7,000 MiB RSS-plus-swap budget. The upstream comparison utility's own
loader worker count is unchanged. Process groups are terminated on failure,
timeout, memory/diagnostic limit, and after an exited leader so descendants
cannot survive. The log cap is checked again after cleanup. No timeout or
unsupported result is treated as acceptance.

```sh
python independent/bootstrap_checker.py \
  --work "$OPICA_WORK/independent-checker" \
  --timeout 2400 --memory-mib 10000 --min-free-gib 6

python independent/verify_independent.py \
  --modular-output "$OPICA_WORK/verification" \
  --checker-work "$OPICA_WORK/independent-checker" \
  --external-head "$EXACT_GITHUB_SHA" \
  --output "$OPICA_WORK/independent-verification" \
  --timeout 9000 --memory-mib 50000
```

Bootstrap outputs `BOOTSTRAP_RECEIPT.json`, `RUNTIME_FILES.json`,
`CHECKER_SOURCE_FILES.json`, and process logs/receipts at its work root.
Verification outputs `INDEPENDENT_RECEIPT.json`, stage/process receipts,
read-only view identity records and the final bound-file inventory. It writes
no full proof NDJSON. A PASS is permitted only after all seven stages, including
the final complete integrity check; cleanup failures also fail the wrapper.
