import array, base64, hashlib, json, unittest, zlib
from cross_search import Builder,conditional,head,peel,root,subdag,membership,union_report
def const(n):
    name=["anonymous"]
    for x in n.split("."):name=["str",name,x]
    return ["const",name,[]]
def mk(a,b):
    return {"format":"LEAN_EXPR_DAG_V1","root":"2","nodes":[const(a),const(b),["forall",["anonymous"],"default","0","1"]]}
def mem(ids):
    import struct
    b=struct.pack("<"+"I"*len(ids),*ids)
    return {"encoding":"LE_U32_SORTED_ZLIB_BASE64_V1","count":len(ids),"sha256":hashlib.sha256(b).hexdigest(),"data":base64.b64encode(zlib.compress(b)).decode()}
class Controls(unittest.TestCase):
    def test_splice(self):
        a=mk("TopG","RampWindows");b=mk("RampWindows","NativeEnergySubpower");bs,_=peel(a);_,end=peel(b)
        q=conditional(bs,b,end);ds,last=peel(q)
        self.assertEqual(len(ds),1);self.assertEqual(head(q,last),"NativeEnergySubpower")
        self.assertEqual(head(subdag(q,int(q["nodes"][root(q)][3]))),"TopG")
    def test_union(self):
        a={"world":"ORIGINAL_EXPORT","declaration":"a","membership":mem([1,2,3])}
        b={"world":"ORIGINAL_EXPORT","declaration":"b","membership":mem([2,3,4])}
        r=union_report([a,b],{1,2,3,4,5});self.assertEqual(r["original_export_union_declarations"],4);self.assertEqual(r["original_export_overlap_saved"],2)
    def test_union_no_cross_epoch(self):
        a={"world":"ORIGINAL_EXPORT","declaration":"a","membership":mem([1,2])}
        b={"world":"NATIVE_COMPILER","declaration":"b","closure_count":10}
        r=union_report([a,b],None);self.assertEqual(r["original_export_union_declarations"],2);self.assertEqual(r["separate_native_consumers"],["b"])
    def test_membership_tamper(self):
        a=mem([1,2,3]);a["sha256"]="0"*64
        with self.assertRaises(RuntimeError):membership(a)
    def test_order_refusal(self):
        with self.assertRaises(RuntimeError):membership(mem([1,3,2]))
if __name__=="__main__":unittest.main()
