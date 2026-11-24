import hashlib, io, json, pathlib, tempfile, unittest
from export_graph import Index
def feed(ix,rows):
    raw=b"".join((json.dumps(r)+"\n").encode() for r in rows)
    ix.consume(io.BytesIO(raw),len(raw),hashlib.sha256(raw).hexdigest())
def fixture():
    return [{"meta":{"format":{"version":"3.1.0"}}},
            {"in":1,"str":{"pre":0,"str":"riemannHypothesis"}},
            {"in":2,"str":{"pre":0,"str":"sorryAx"}},
            {"ie":0,"sort":0},{"ie":1,"const":{"name":2,"us":[]}},
            {"axiom":{"name":2,"type":0,"levelParams":[],"isUnsafe":False}},
            {"thm":{"name":1,"type":0,"value":1,"all":[1],"levelParams":[]}}]
def root(ix,limit=1000):
    return next(x for x in ix.report("fixture",limit,30)["roots"] if x["name"]=="riemannHypothesis")
class TestGraph(unittest.TestCase):
    def test_transitive_axiom(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20);feed(ix,fixture());x=root(ix)
            self.assertEqual(x["closure"]["axioms"],["sorryAx"])
            self.assertEqual(x["closure"]["declarations"],2)
            self.assertEqual(x["value_dependencies"]["constants"],["sorryAx"])
    def test_unknown_record(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20)
            with self.assertRaises(RuntimeError):feed(ix,fixture()+[{"unknown":{}}])
    def test_wrong_hash(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20);raw=b"".join((json.dumps(r)+"\n").encode() for r in fixture())
            with self.assertRaises(RuntimeError):ix.consume(io.BytesIO(raw),len(raw),"0"*64)
    def test_forward_reference(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20);rows=fixture();rows[3]={"ie":0,"app":{"fn":1,"arg":0}}
            with self.assertRaises(RuntimeError):feed(ix,rows)
    def test_inductive_structure(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20)
            rows=fixture()[:4]+[{"ie":1,"const":{"name":2,"us":[]}},
                {"inductive":{"types":[{"name":1,"type":0,"all":[1],"ctors":[2]}],"ctors":[{"name":2,"type":1,"induct":1}],"recs":[]}}]
            feed(ix,rows);self.assertEqual(root(ix)["closure"]["declarations"],2)
    def test_bounded_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20);feed(ix,fixture())
            self.assertEqual(root(ix,1)["closure"]["status"],"BUDGET_EXHAUSTED")
    def test_actual_type_conversion(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20);feed(ix,fixture());x=root(ix)
            self.assertEqual(x["type_expression"],{"format":"LEAN_EXPR_DAG_V1","root":"0","nodes":[["sort",["zero"]]]})
            self.assertEqual(x["closure"]["membership"]["count"],2)
    def test_projection_and_let(self):
        with tempfile.TemporaryDirectory() as d:
            ix=Index(pathlib.Path(d),2**20)
            rows=fixture()[:-1]+[{"ie":2,"proj":{"typeName":2,"idx":0,"struct":1}},{"ie":3,"letE":{"name":0,"type":0,"value":1,"body":2,"nondep":False}},{"thm":{"name":1,"type":0,"value":3,"all":[1]}}]
            feed(ix,rows);self.assertEqual(root(ix)["value_dependencies"]["constants"],["sorryAx"])
if __name__=="__main__":unittest.main()
