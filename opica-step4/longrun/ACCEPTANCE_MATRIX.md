# Long-run Step 4 claim matrix

This file defines expected release states; it is not a successful verification report.

| Gate | Full requirement | Partial or red disposition |
|---|---|---|
| Exact source | Supplier source/tree, original native pin, common Lean/Mathlib, runtime hashes, complete supplier-object inventory | BLOCKED; no theorem claim |
| Native preparation | Fresh 572 source modules; complete native source/target object binding and replay | INCOMPLETE or FAIL |
| Modular 1–19 | All 19 original ordered methods PASS | Later stages NOT_RUN |
| Modular Stage 20 | Actual guarded stock import and separate raw object audit PASS | INCOMPLETE; no guard/closed proof claimed |
| Modular 21–30 | All ten original methods PASS, all 30 ordered receipts PASS | NOT_RUN or INCOMPLETE |
| Independent | All seven methods PASS, all 50 ordered roots and full proof/type dependency closure accepted | Independent NOT_RUN/FAIL; no Step4 closure |
| Final | Byte-identical original inputs, proof objects, no forbidden axiom, exact definitions, worktree, all final integrity | No acceptance |
| Post-green | Proof reading, workflow harvest, explicit published claim/remaining assumptions | Do not upgrade external-certificate trust or old gate |

A **successful pilot** runs only original methods 1–20. It must never produce `MODULAR_GATE_RECEIPT.status=PASS`, must keep stages 21–30 NOT_RUN, and must not run the independent checker.

A full successful receipt *can* establish checked native C1 under the existing externally authenticated supplier certificate model if the exact original modular and complete independent kernel gates pass. It is not an independently discovered CCM arithmetic proof of RH, and is not a pass of the old separate Round19 25-stage procedure or native original-pin build.

`LONGRUN_WORKFLOW_DISPOSITION.json` is an additional fail-closed summary of raw required receipts. It never changes proof authority or emits `proof_acceptance: true` by itself.
