module
public import Main

/-!
Exact current community Lean4.36 supplier endpoint, not a new arithmetic proof.
This module changes no original theorem, imported definition or trusted source.
-/

@[expose] public section

namespace OPICACommunityV436

/-- Pure certified-type ingress, CONDITIONAL on the imported supplier theorem.
The proof body is the public root, never a new arithmetical estimate. -/
theorem suppliedRH : RiemannHypothesis := _root_.riemannHypothesis

end OPICACommunityV436

#check (_root_.riemannHypothesis : RiemannHypothesis)
#check (OPICACommunityV436.suppliedRH : RiemannHypothesis)
#print axioms OPICACommunityV436.suppliedRH
