import unittest
from candidate_validate import fingerprint
from cross_search import Builder,conditional,head,peel
from candidate_port import DENIED
class FinalControls(unittest.TestCase):
    def test_fingerprint_preserves_constant_identity(self):
        a={"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["const",["str",["anonymous"],"A"],[]]]}
        b={"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["const",["str",["anonymous"],"B"],[]]]}
        self.assertNotEqual(fingerprint(a),fingerprint(b))
    def test_metadata_normalization(self):
        a={"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["sort",["zero"]]]}
        b={"format":"LEAN_EXPR_DAG_V1","root":"1","nodes":a["nodes"]+[["mdata",[],"0"]]}
        self.assertEqual(fingerprint(a),fingerprint(b))
    def test_binder_names_only(self):
        a={"format":"LEAN_EXPR_DAG_V1","root":"1","nodes":[["sort",["zero"]],["forall",["str",["anonymous"],"x"],"default","0","0"]]}
        b={"format":"LEAN_EXPR_DAG_V1","root":"1","nodes":[a["nodes"][0],["forall",["str",["anonymous"],"y"],"default","0","0"]]}
        self.assertEqual(fingerprint(a),fingerprint(b))
        b["nodes"][1][2]="implicit"
        self.assertNotEqual(fingerprint(a),fingerprint(b))
    def test_universe_preserved(self):
        a={"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["sort",["zero"]]]}
        b={"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["sort",["succ",["zero"]]]]}
        self.assertNotEqual(fingerprint(a),fingerprint(b))
    def test_no_endpoint_import(self):
        self.assertIn("Main",DENIED)
        self.assertIn("Development.AutomorphicArithmetic.CharacterBoxes.MainConclusion",DENIED)
if __name__=="__main__":unittest.main()
