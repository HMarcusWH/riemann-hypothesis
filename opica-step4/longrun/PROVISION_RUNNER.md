# OPICA dedicated ephemeral host provisioning — operator-owned

This is a runbook, **not** a claim of an existing runner or proof completion.

## External prerequisites

1. Provision a disposable isolated Linux x86-64 runner, preferably Ubuntu 24.04 with `ext4` or `xfs` on an adequately sized local NVMe volume. The initial policy requires at least 120,000 MiB physical RAM, eight available CPUs, 250 GiB free disk, and 400,000 free inodes at the chosen runner work root. These are admission thresholds, not scientifically proven capacity requirements.
2. Install the official GitHub Actions self-hosted runner, register it **only** in the trusted repository or appropriately isolated runner group, and label it `opica-longrun`. Use a name beginning with `opica-longrun-`; only one clean dedicated runner should be eligible for a run. Prefer the official ephemeral `--ephemeral` runner mode; do not reuse a long-run proof VM for unrelated untrusted jobs.
3. Keep the runner unprivileged. The existing original transport requires controlled root operations for loopback and read-only SquashFS mounts. Arrange a reviewed, narrowly scoped sudo capability rather than blanket persistent secrets. The runner is disposable, so no third-party PR workflow may execute on it.
4. Preinstall Python 3 with venv, `git`, `sudo`, `zstd`, `squashfs-tools`, `losetup`, `mount`, and the original dependencies. The workflow rebuilds its pinned Lean toolchain/native packages, exporter and checker. Allow network only for explicitly authenticated dependency downloads; preserve the original source hashes and full SHA256 check over 350,374 supplier objects.
5. Create root-owned `/etc/opica/ephemeral-runner.json`, mode 0644 or stronger, **outside** the repository, with fields:
```json
{
  "schema": "OPICA_EPHEMERAL_RUNNER_V1",
  "ephemeral": true,
  "runner_name": "opica-longrun-YOUR-EXACT-RUNNER-NAME",
  "profile_id": "OPICA_LONGRUN_20H_DIO64K_V1"
}
```
   The `runner_name` value must equal GitHub's actual `RUNNER_NAME`. The runner marker is operational admission evidence, not a cryptographic attestation of GitHub's control plane or a mathematical certificate. Keep its parent directory not writable by the runner.
6. Run the reviewed commit with `workflow_dispatch` only. Enter `verify_head` exactly equal to the selected workflow ref SHA. Start with `pilot_stage20`. The runner preflight rejects mismatches, resource shortages, missing marker and changed original source files.
7. Collect and preserve all receipts, including failure outcomes. A pilot only checks the original first twenty modular stages and cannot establish Step4. Follow with a separate full 30+7 run only after reviewing the pilot.

## GitHub workflow publication dependency

GitHub's `workflow_dispatch` requires the workflow to be present on the repository's default branch before it can be dispatched normally. This branch supplies the implementation for review, but the workflow will not automatically execute while it exists only on this draft/stacked PR. Publication requires an explicit reviewed merge path. Do **not** add `pull_request_target` or an untrusted public-fork trigger to work around that restriction.

## Why finite watchdogs remain

Long-running Lean kernel work can legitimately exceed 1,800 seconds. The new stage-specific budget is 14,400 seconds for each of the two potentially expensive imports. If it still expires, that attempt remains `INCOMPLETE`; select and version a larger budget based on evidence. Memory/resource sampling, stdout/stderr caps, exit-zero, kernel proof checking, process-group cleanup and all original 30+7 gates remain mandatory.

## Remaining external tasks

No compute machine has been registered/provisioned through this PR. No external artifact archive, read-only proof-store mount or full independent kernel check has been executed by merely creating workflow files.
