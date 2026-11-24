# Community supplier v4.37 sync candidate — 2026-11-24

The mathematical source is unchanged from upstream 73958da58a8a4d1f61b789745c5444baf6247cae, src tree 6e972745429bd501b15e5daa9db46c8a9feb85db. Previous fork main 52c7dcc17b9c29b41e186741fe8296b1a52a3e4b remains on archive/pre-v437-community-sync-20261124. Existing verification and research branches remain untouched.

This merge candidate preserves the old fork CI directory and its upstream-only builder/publisher containment, except for the safe hosted dual challenge rehearsal and additive source identity workflow. Three fork identity scripts/notes are preserved over the upstream scripts tree. The upstream workflow changes remain accessible in the pinned upstream parent, not active on the fork.

Lean 4.37.0-rc1 and Mathlib 31ce06eaadf4a200c0e1407c5f10953cf606b8f8 form a new source epoch. No proof receipts or compiled objects transfer automatically.

First qualify exact source identity and both challenge exports/checksums and placeholder rejection; then separately qualify a disposable runner to run both actual sandboxed Comparators against freshly built Main using Mathlib-only cache. An accepted placeholder rehearsal is not supplier proof verification. Fresh supplier qualification and a reviewed 4.37 port of the independent 38/50-root bridge are separate requirements. The original 30+7 and v4.36 procedures remain unchanged.

No proof acceptance claimed. Native C1 and independent Step 4 remain OPEN.
