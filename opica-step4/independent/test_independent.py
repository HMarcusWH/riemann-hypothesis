"""Concrete fail-closed controls for the new independent wrapper only."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import common as c
import verify_independent as v


def passing_modular_shape():
    return {"schema":v.mod.GATE_VERSION,"gate_version":v.mod.GATE_VERSION,"status":"PASS","exit_code":0,
        "runner_sha256":c.MODULAR_RUNNER_SHA,"frozen_runner_sha256":v.mod.FROZEN_RUNNER_SHA,
        "frozen_spec_sha256":v.mod.FROZEN_SPEC_SHA,
        "stages":[{"name":name,"status":"PASS","details":{}} for name in v.mod.STAGES],
        "supplier_certificate_identity":"MATCHES_PUBLISHED_FULL_CERTIFICATE",
        "supplier_kernel_execution":"EXTERNAL_PUBLISHED_RECEIPT","native_full_kernel_execution":"LOCAL_PASS",
        "new_closed_declarations_kernel_execution":"LOCAL_PASS","full_combined_export_kernel_execution":"NOT_RUN_BY_THIS_GATE",
        "prior_round19_25_stage_gate":"NOT_RUN_OR_BLOCKED_UNCHANGED",
        "fresh_closed_object_production":"STOCK_KERNEL_CHECKED_ACTUAL_THREE_THEOREMS",
        "closed_source_elaborator_compilation":"NOT_RUN_BY_THIS_GATE",
        "closure_claim":"EXACT_NATIVE_C1_AT_COMMON_PIN_UNDER_EXPLICIT_EXTERNAL_SUPPLIER_CERTIFICATE_MODEL"}


def accepted_log(roots=50,count=1500000):
    return (f"con-leche: read: emitting records from {roots} constants t=1.0s\n"
        f"con-leche: parse done: {count} fold records — the file's {count}, 0 built-in prelude records synthesised t=2.0s\n"
        f"con-leche: check done: {count} declarations t=3.0s\n"
        f"con-leche: accepted {count} declarations (--verified)\n")


class ReceiptTests(unittest.TestCase):
    def test_exact_modular_shape_accepted(self):
        self.assertEqual(len(v.assert_modular_claim(passing_modular_shape())),30)

    def test_changed_stage_head_or_scope_rejected(self):
        for field,value in (("status","RUNNING"),("exit_code",1),("runner_sha256","0"*64),
                            ("prior_round19_25_stage_gate","PASS"),("native_full_kernel_execution","NOT_RUN"),
                            ("schema","OPICA20_MODULAR_CERTIFICATE_COMPOSITION_V1"),
                            ("fresh_closed_object_production","NOT_RUN"),
                            ("closed_source_elaborator_compilation","PASS")):
            data=passing_modular_shape();data[field]=value
            with self.subTest(field=field),self.assertRaises(c.Failure):v.assert_modular_claim(data)
        for mutation in (lambda x:x.pop(),lambda x:x.reverse(),lambda x:x.append(x[0]),lambda x:x[3].update(status="RUNNING")):
            data=passing_modular_shape();mutation(data["stages"])
            with self.assertRaises(c.Failure):v.assert_modular_claim(data)

    def test_exact_roots_and_nonempty_full_acceptance(self):
        self.assertEqual(len(v.ROOTS),50)
        self.assertEqual(v.ROOTS[:38],v.mod.SUPPLIER_TARGETS)
        self.assertEqual(v.ROOTS[38:47],v.mod.AUDIT_NAMES)
        self.assertEqual(v.ROOTS[47:],tuple(v.mod.CLOSED_TYPES))
        self.assertEqual(v.acceptance(accepted_log(),50,minimum=1468421,complete_prelude=True),1500000)
        for log in (accepted_log(49),accepted_log(count=0),accepted_log().replace("--verified","--trusted"),
                    accepted_log()+accepted_log(),accepted_log().replace("check done: 1500000","check done: 1499999")):
            with self.assertRaises(c.Failure):v.acceptance(log,50,minimum=1468421,complete_prelude=True)

    def test_actual_safe_root_inventory_cannot_skip_duplicate_or_reorder(self):
        lines = ["OPICA21_SAFE_SELECTED_ROOT " + name for name in v.ROOTS]
        self.assertEqual(v.mod.parse_selected_root_audit("\n".join(lines) + "\n"), list(v.ROOTS))
        for changed in (lines[:-1], lines + lines[:1], list(reversed(lines)),
                        lines[:-1] + ["OPICA21_SAFE_SELECTED_ROOT Forged.root"]):
            with self.assertRaises(v.mod.GateFailure):
                v.mod.parse_selected_root_audit("\n".join(changed) + "\n")

    def test_missing_gate_fails_with_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=argparse.Namespace(modular_output=root/"missing",checker_work=root/"tools",output=root/"out",
                external_head="a"*40,jobs=1,timeout=10,memory_mib=512,control_timeout=10,control_memory_mib=512)
            gate=v.Independent(args)
            self.assertEqual(gate.execute(),1)
            data=c.read_json(root/"out/INDEPENDENT_RECEIPT.json")
            self.assertEqual(data["status"],"FAIL")
            self.assertEqual(data["stages"][0]["status"],"FAIL")
            self.assertEqual(data["stages"][1]["status"],"NOT_RUN")
            self.assertEqual(data["prior_round19_25_stage_gate"],"NOT_RUN_OR_BLOCKED_UNCHANGED")

    def test_bound_object_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/"Proof.olean";file.write_bytes(b"original")
            obj=v.Independent.__new__(v.Independent)
            obj.object_inventories={str(root):{"Proof.olean":c.sha(file)}}
            obj.input_files={str(file):c.sha(file)};obj.bound={}
            obj.rehash_inputs()
            file.write_bytes(b"modified")
            with self.assertRaises(c.Failure):obj.rehash_inputs()

    def test_new_shadow_object_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            obj=v.Independent.__new__(v.Independent);obj.object_inventories={str(root):{}}
            obj.check_object_sets()
            (root/"Shadow.olean").write_bytes(b"new")
            with self.assertRaises(c.Failure):obj.check_object_sets()

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"receipt.json";p.write_text('{"status":"FAIL","status":"PASS"}')
            with self.assertRaises(c.Failure):c.read_json(p)

    def test_runtime_library_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lib=root/"libleanshared.so";lib.write_bytes(b"pinned runtime")
            inventory=c.file_inventory(root)
            c.verify_file_inventory(root,inventory)
            lib.write_bytes(b"different runtime")
            with self.assertRaises(c.Failure):c.verify_file_inventory(root,inventory)


class ProcessTests(unittest.TestCase):
    def invoke(self,root,name,source,**kwargs):
        return c.run(name,[sys.executable,"-c",source],cwd=root,env=c.clean_env(),output=root,
                     timeout=kwargs.pop("timeout",3),memory_mib=kwargs.pop("memory_mib",256),**kwargs)

    def test_timeout_is_failure_and_process_group_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(c.Failure,"timeout"):
                self.invoke(root,"timeout","import time; time.sleep(10)",timeout=0.05)
            row=c.read_json(root/"timeout.json")
            self.assertEqual(row["status"],"FAIL")
            self.assertNotEqual(row["exit_code"],0)

    def test_nonzero_and_final_log_burst_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(c.Failure):self.invoke(root,"nonzero","raise SystemExit(3)")
            with self.assertRaises(c.Failure):self.invoke(root,"burst","print('x'*100000)",log_limit=1000)

    def test_memory_budget_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(c.Failure,"memory budget"):
                self.invoke(root,"memory","import time; x=bytearray(32*1024*1024); time.sleep(5)",memory_mib=1)

    def test_exited_leader_descendant_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=("import os,time,pathlib\np=os.fork()\n"
                "if p: pathlib.Path('child.pid').write_text(str(p))\n"
                "else: time.sleep(20)\n")
            row,_=self.invoke(root,"descendant",source)
            self.assertEqual(row["exit_code"],0)
            pid=int((root/"child.pid").read_text())
            for _ in range(20):
                stat=Path(f"/proc/{pid}/stat")
                if not stat.exists() or stat.read_text().rsplit(")",1)[1].split()[0]=="Z":break
                time.sleep(0.05)
            else:self.fail("Descendant survived process-group cleanup")

if __name__ == "__main__":unittest.main()
