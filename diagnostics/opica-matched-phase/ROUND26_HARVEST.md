# Round26 matched-prefix diagnostic — final evidence harvest

**Frozen event:** 2026-11-22; head `3ce05c7f351ecd811eea1a15ae35d826c13dad89`; run [45043676060](https://github.com/HMarcusWH/riemann-hypothesis/actions/runs/45043676060), job `137273438606`. This is **EXPERIMENTAL DIAGNOSTIC EVIDENCE ONLY**. RH/C1/Step 4 remain OPEN.

The workflow finished **FAILURE**; prep, source identity, 19-stage prefix, object custody and final resource observation completed. The nonaccepting 1,800-second stock import probe was incomplete. The exact 517-byte original `matched_stock_import_split.log`, SHA256 `0ee6413ccb845c6532fe8efac97fff8cf7138df7e93a0bedec9109de8385f190`, contains `CORE_BEGIN` at monotonic 5,830,318 ms, `CORE_END` at 6,630,460 ms (800.142 s completed core), and `FINALIZE_BEGIN` at the same 6,630,460 ms. **No FINALIZE_END** exists. Finalization ran for some portion of the remaining budget; its total duration cannot be inferred.

The process receipt records 1,800.261451 s, peak sampled RSS-plus-swap 11,082,997,760 bytes, 1,609,988 observed major faults, and 83,942,926,336 observed read bytes. These are process observations, not a controlled comparison proving that disk is the bottleneck. The frozen Round25 recorded-input comparison reported zero mismatched fields; post-integrity and unchanged resource identities passed.

The original parser additionally rejected the actual Lean `#[public import Init, public meta import Init, public import Main, public import OPICAStep4.NativeValidated, public import Lean]` marker as a rendering mismatch. The separately checked fix `4fbabb316f9b...` corrects only parsing. `reparse_saved_log.py` can produce a separate corrected-observation receipt from the original log without changing its FAILED outcome.

**Artifacts:** diagnostic `14766573175` (outer ZIP SHA256 `68efa88b50acf5a5f53f58345d2218f7a7fcd014ab27beed01526e9ef177791b`); resource `14767337569`. No guard theorem object, C1 theorem, or independent proof receipt was produced by this diagnostic. The original full production attempt remains 19 PASS / 1 INCOMPLETE / 10 NOT_RUN.
