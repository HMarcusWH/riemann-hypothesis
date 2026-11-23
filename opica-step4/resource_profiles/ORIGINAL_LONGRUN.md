# Original supplier, dedicated long-run execution profile

This is an operational alternative to the repeated hosted stage-20 timeout. It does not change native or supplier mathematics, the source pins, the image, proof roots, the original 30 modular stages or seven independent stages, or the allowed axioms. The selected long-run profile changes the workflow deadline from six to twenty hours and the compile/import limit from 1,800 to 14,400 seconds. Other proof process budgets and memory ceilings are unchanged.

Push runs check the source bundle and existing resource controls only. No expensive proof run starts without a manual profile selection and an exact reviewed head. The historical hosted profile remains available under manual dispatch with its original 1,800-second compile limit.

The maintainer must provision a disposable Linux X64 runner labeled opica-original-433-longrun and named opica-original-433-*, with at least eight CPUs, 120,000 MiB RAM, 250 GiB free disk, 400,000 free inodes, vm.max_map_count >= 1048576, the original dependencies, venv support and passwordless sudo for the selected read-only loop/mount operations. Root must install a mode 0644 or stricter /etc/opica/original-433-longrun.json whose exact JSON is {"schema":"OPICA_ORIGINAL_433_EPHEMERAL_V1","runner_name":"<actual runner name>","ephemeral":true}. Do not use a shared persistent host. No host is provisioned by this PR. The preflight neither deletes installed SDKs nor changes the host's swap or sysctl configuration.

Publish the reviewed workflow on the default branch if needed for GitHub's workflow_dispatch visibility, then dispatch the original archive proof branch at the exact reviewed head with LONGRUN_ORIGINAL. Full proof and independent receipts remain mandatory. If execution stops, retain the observed partial result; never reuse the prior run's PASS stages as a current-head acceptance.

Current disposition: RH OPEN, C1 OPEN, Step4 OPEN; source/profile code is not evidence of a completed proof.
