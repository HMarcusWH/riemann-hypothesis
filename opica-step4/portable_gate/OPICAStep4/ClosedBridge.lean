import Development.AutomorphicArithmetic.CharacterBoxes.MainConclusion
import Zeta23.OPICARound4.ArithmeticFrontier.ZeroFreeFloor

/-!
Round 19 closed bridge candidate. The source is not a validation receipt.
The strict portable gate must freshly compile and replay it and its named
consumer before any closure claim. No arithmetic estimate or RH is a premise.
-/

namespace Zeta23.OPICARound19

open OPICARound4.ArithmeticFrontier

/-- The registered native Step 4 contract, supplied by the external closed theorem. -/
theorem step4C1 : CofinalMomentSliceVanishingErrorBounds :=
  cofinal_moment_slice_bounds_of_riemannHypothesis
    UpperTheory.FinalTheorems.riemannHypothesis

/-- The same input gives zero error for both parities, every positive aperture
and every cutoff. It is stronger than the cofinal tolerance requested by C1. -/
theorem allMomentSlicesZero {L : ℝ} (hL : 0 < L) (K : ℕ) :
    EvenMomentSliceLowerBound L K 0 ∧ OddMomentSliceLowerBound L K 0 :=
  momentSliceLowerBounds_zero_of_riemannHypothesis
    UpperTheory.FinalTheorems.riemannHypothesis hL K

end Zeta23.OPICARound19

set_option pp.fullNames true
set_option pp.universes true

#eval IO.println "OPICA19_TYPE_BEGIN UpperTheory.FinalTheorems.riemannHypothesis"
#check @UpperTheory.FinalTheorems.riemannHypothesis
#eval IO.println "OPICA19_TYPE_END UpperTheory.FinalTheorems.riemannHypothesis"
#print axioms UpperTheory.FinalTheorems.riemannHypothesis

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound19.step4C1"
#check @Zeta23.OPICARound19.step4C1
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound19.step4C1"
#print axioms Zeta23.OPICARound19.step4C1

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound19.allMomentSlicesZero"
#check @Zeta23.OPICARound19.allMomentSlicesZero
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound19.allMomentSlicesZero"
#print axioms Zeta23.OPICARound19.allMomentSlicesZero
