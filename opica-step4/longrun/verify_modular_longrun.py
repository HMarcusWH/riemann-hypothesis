#!/usr/bin/env python3
"""Versioned long-run budget adapter for the UNCHANGED original modular proof gate.

Only the stage-specific execution deadline is overridden. The actual stage methods,
stock Lean kernel producer, proof objects, imports, axiom policy and source checks
remain those of the frozen original verifier.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from policy import PolicyError, profile, source_identity, sha256, git, require, EXPECTED_BASE, EXPECTED_PROFILE

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "modular" / "verify_modular.py"
PROFILE = HERE / "PROFILE.json"
LONGRUN_STAGES = frozenset(("guarded_kernel_import", "fresh_closed_kernel_construction"))
MODULAR_COUNT = 30
INDEPENDENT_COUNT = 7

def _load_original():
    require(git("rev-parse", "HEAD:opica-step4/modular/verify_modular.py") ==
            git("rev-parse", EXPECTED_BASE + ":opica-step4/modular/verify_modular.py"),
            "Original modular mathematical gate changed")
    require(git("rev-parse", "HEAD:opica-step4/modular/kernel_producer/KernelBridge.lean") ==
            git("rev-parse", EXPECTED_BASE + ":opica-step4/modular/kernel_producer/KernelBridge.lean"),
            "Original stock kernel producer changed")
    require(git("rev-parse", "HEAD:opica-step4/independent/verify_independent.py") ==
            git("rev-parse", EXPECTED_BASE + ":opica-step4/independent/verify_independent.py"),
            "Original independent checker changed")
    require(sha256(ORIGINAL) == sha256_bytes_from_git("opica-step4/modular/verify_modular.py"),
            "Original modular verifier worktree differs from checked commit")
    spec = importlib.util.spec_from_file_location("opica_longrun_frozen_modular", ORIGINAL)
    require(spec is not None and spec.loader is not None, "Original modular verifier not importable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(len(module.STAGES) == MODULAR_COUNT and
            module.STAGES[19] == "guarded_kernel_import" and
            module.STAGES[20] == "fresh_closed_kernel_construction",
            "Original 30-stage order or guard location changed")
    return module


def sha256_bytes_from_git(path: str) -> str:
    import subprocess
    body = subprocess.check_output(["git", "-C", str(HERE.parents[1]), "show", "HEAD:" + path], timeout=60)
    return hashlib.sha256(body).hexdigest()


def controller_receipt(path: Path, *, mode: str, head: str, p: dict, result: int, gate,
                       stage_budgets: list) -> dict:
    modular = gate.receipt
    rows = modular.get("stages", [])
    require(len(rows) == MODULAR_COUNT, "Original modular receipt stage count differs")
    statuses = [row.get("status") for row in rows]
    if mode == "full":
        valid = (result == 0 and modular.get("status") == "PASS"
                 and statuses == ["PASS"] * MODULAR_COUNT)
        disposition = "MODULAR_30_PASS_REQUIRES_INDEPENDENT" if valid else "MODULAR_NOT_ESTABLISHED"
    else:
        valid = (result == 0 and modular.get("status") == "PILOT_STAGE20_COMPLETE"
                 and statuses[:20] == ["PASS"] * 20 and statuses[20:] == ["NOT_RUN"] * 10)
        disposition = "PILOT_STAGE20_COMPLETE_NOT_MODULAR_PASS" if valid else "PILOT_INCOMPLETE"
    r = {
        "schema": "OPICA_LONGRUN_CONTROLLER_RECEIPT_V1",
        "execution_mode": mode, "status": disposition,
        "checked_head": head, "checked_tree": git("rev-parse", "HEAD^{tree}"),
        "longrun_profile_id": p["id"], "longrun_profile_sha256": sha256(PROFILE),
        "adapter_sha256": sha256(Path(__file__)),
        "original_modular_source_sha256": sha256(ORIGINAL),
        "original_independent_source_sha256": sha256(HERE.parent / "independent" / "verify_independent.py"),
        "original_kernel_producer_sha256": sha256(HERE.parent / "modular" / "kernel_producer" / "KernelBridge.lean"),
        "stage_budget_overrides": stage_budgets,
        "modular_receipt_sha256": sha256(gate.output / "MODULAR_GATE_RECEIPT.json"),
        "original_modular_status": modular.get("status"),
        "original_stage_statuses": statuses,
        "exit_code": result,
        "pilot_completed": valid if mode == "pilot_stage20" else False,
        "modular_pass": valid if mode == "full" else False,
        "independent_pass": False,
        "proof_acceptance": False,
        "prior_round19_25_stage_gate": "NOT_RUN_OR_BLOCKED_UNCHANGED",
        "rh_status": "OPEN",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Versioned execution policy over unchanged mathematical gate; independent proof remains separately required",
    }
    require(not path.exists(), "Controller receipt must not be overwritten")
    with path.open("x", encoding="utf-8") as stream:
        json.dump(r, stream, indent=2)
        stream.write("\n")
    return r


def make_gate_class(mod, p):
    class LongrunGate(mod.ModularGate):
        def __init__(self, args, mode):
            self.longrun_mode = mode
            self.longrun_budgets = []
            super().__init__(args)

        def kernel_construct(self, module, mode, stage_name):
            if stage_name not in LONGRUN_STAGES:
                return super().kernel_construct(module, mode, stage_name)
            # Only override the deadline while executing the EXACT original method.
            replacement = p["limits_seconds"][stage_name]
            before = self.args.compile_timeout
            require(before == p["limits_seconds"]["canonical_compile"],
                    "Original compile-timeout was changed")
            self.longrun_budgets.append({"stage": stage_name,
                                          "original_seconds": before,
                                          "selected_seconds": replacement})
            self.args.compile_timeout = replacement
            try:
                return super().kernel_construct(module, mode, stage_name)
            finally:
                self.args.compile_timeout = before

        def execute(self):
            if self.longrun_mode == "full":
                return super().execute()
            # Diagnostic-only pilot runs the original first twenty stage methods.
            # It cannot produce MODULAR PASS or run the independent checker.
            actions = {name: getattr(self, name) for name in mod.STAGES if hasattr(self, name)}
            code = 2
            try:
                for name in mod.STAGES[:20]:
                    self.stage(name, actions[name])
                require(all(row["status"] == "PASS" for row in self.receipt["stages"][:20]),
                        "Pilot prefix did not complete every stage")
                require(all(row["status"] == "NOT_RUN" for row in self.receipt["stages"][20:]),
                        "Pilot illegally executed a downstream stage")
                self.receipt.update(status="PILOT_STAGE20_COMPLETE",
                                    closure_claim="NOT_ESTABLISHED",
                                    claim="Actual guarded kernel import and its audit completed; no full modular or independent proof authority")
                code = 0
            except (mod.GateBlocked, mod.GateIncomplete) as err:
                self.receipt.update(status="INCOMPLETE", failure=str(err))
            except KeyboardInterrupt:
                self.receipt.update(status="INTERRUPTED", failure="Operator interrupt")
                code = 130
            except Exception as err:
                self.receipt.update(status="FAIL", failure=str(err), exception_type=type(err).__name__)
            finally:
                self.receipt.update(ended_utc=mod.old.utc_now(), exit_code=code)
                self.save()
                print("PILOT: " + self.receipt["status"], flush=True)
            return code
    return LongrunGate


def main(argv=None) -> int:
    option = argparse.ArgumentParser(add_help=False)
    option.add_argument("--longrun-mode", choices=("pilot_stage20", "full"), required=True)
    option.add_argument("--longrun-selection", required=True)
    option.add_argument("--longrun-checked-head", required=True)
    own, remaining = option.parse_known_args(argv)
    try:
        p = profile()
        require(own.longrun_selection == p["id"], "Longrun profile not selected")
        source_identity(own.longrun_checked_head)
        mod = _load_original()
        args = mod.arguments(remaining)
        require(args.compile_timeout == p["limits_seconds"]["canonical_compile"] and
                args.fresh_timeout == p["limits_seconds"]["fresh_replay"] and
                args.replay_timeout == p["limits_seconds"]["replay"] and
                args.export_timeout == p["limits_seconds"]["export"] and
                args.comparison_timeout == p["limits_seconds"]["comparison"],
                "Original stage budgets differ from selected policy")
        require(args.external_head == own.longrun_checked_head, "Explicit supplier head differs")
        Gate = make_gate_class(mod, p)
        gate = Gate(args, own.longrun_mode)
        result = gate.execute()
        final = controller_receipt(gate.output / "LONGRUN_CONTROLLER_RECEIPT.json",
                                   mode=own.longrun_mode, head=own.longrun_checked_head,
                                   p=p, result=result, gate=gate,
                                   stage_budgets=gate.longrun_budgets)
        print(json.dumps({"status": final["status"], "modular_pass": final["modular_pass"],
                          "proof_acceptance": False, "rh_status": "OPEN"}), flush=True)
        return result
    except Exception as err:
        print("LONGRUN_EXECUTION_REJECTED: " + type(err).__name__ + ": " + str(err), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
