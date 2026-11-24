import copy, unittest
from source import accepted, axiom_report, roots, Refused, PUBLIC, ALLOWED, KERNELS
class Controls(unittest.TestCase):
    def setUp(self):
        self.cfg={"challenge_module":"Challenge","solution_module":"Main","theorem_names":PUBLIC,"permitted_axioms":["propext","Quot.sound","Classical.choice"],"external_kernels":{"Lean paranoid":["leanchecker-paranoid","--silent","--from-export"],"nanoda":["nanoda_bin"]}}
        self.d={"sandboxed":True,"judgement":"accepted","report":{"compare_statements":{"judgement":"success"},"check_axioms":{"judgement":"success"},"kernel_reports":{n:{"judgement":"success"} for n in KERNELS},"config":copy.deepcopy(self.cfg)}}
    def test_smoke_import(self):
        import smoke
        self.assertTrue(callable(smoke.run))
    def test_executor_import(self):
        import verify
        self.assertTrue(callable(verify.Campaign.execute))
    def test_roots(self):
        a,b,c=roots(); self.assertEqual((len(a),len(b),len(c)),(50,17,35))
    def test_accept(self): self.assertTrue(accepted(self.d,self.cfg))
    def test_unsandboxed(self):
        self.d["sandboxed"]=False
        with self.assertRaises(Refused): accepted(self.d,self.cfg)
    def test_skipped_statement(self):
        self.d["report"]["compare_statements"]["judgement"]="skipped"
        with self.assertRaises(Refused): accepted(self.d,self.cfg)
    def test_missing_kernel(self):
        self.d["report"]["kernel_reports"].pop("nanoda")
        with self.assertRaises(Refused): accepted(self.d,self.cfg)
    def test_extra_axiom(self):
        self.d["report"]["config"]["permitted_axioms"].append("sorryAx")
        with self.assertRaises(Refused): accepted(self.d,self.cfg)
    def test_definition_hole(self):
        self.d["report"]["config"]["definition_names"]=["RiemannHypothesis"]
        with self.assertRaises(Refused): accepted(self.d,self.cfg)
    def test_named_axioms(self):
        self.assertEqual(axiom_report("'foo' depends on axioms: [propext,\n Classical.choice]\n",["foo"])["foo"],["propext","Classical.choice"])
    def test_missing_axiom_record(self):
        with self.assertRaises(Refused): axiom_report("",["foo"])
    def test_sorry(self):
        with self.assertRaises(Refused): axiom_report("'foo' depends on axioms: [sorryAx]\n",["foo"])
    def test_custom_axiom(self):
        with self.assertRaises(Refused): axiom_report("'foo' depends on axioms: [other]\n",["foo"])
if __name__=="__main__": unittest.main()
