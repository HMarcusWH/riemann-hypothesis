"""Exact finite falsification of complete-cost optimality (not a Lean receipt)."""
from r2_common import need,CLAIMS

def run():
    count=0;violations=0;max_slack=0
    for e in range(13):
        for o in range(13):
            H=e+o;s=e-o
            for re in range(e+1):
                for ro in range(o+1):
                    t=s-(re-ro);R=2*H*abs(re-ro)
                    for center2 in range(25):
                        U=(2*H-center2)**2
                        for p in (1,-1):
                            a=max(4*max(p*s,0)**2-U,0)
                            b=max(4*max(p*t,0)**2-U,0)
                            slack=b+4*R-a
                            violations+=int(slack<0)
                            max_slack=max(max_slack,slack)
                            count+=1
    need(count==414050 and violations==0,"Finite complete-cost control failed")
    return {"status":"FINITE_COMPLETE_COST_CONTROL_ONLY","signed_cell_cases":count,"violations":violations,"max_scaled_slack":max_slack,"scope":"UNRESTRICTED_REMOVAL_ABSTRACT_FINITE_CELLS","not_native_asymptotic_proof":True,**CLAIMS}
if __name__=="__main__":
    import json
    print(json.dumps(run(),sort_keys=True))
