import OPICAStep4.ClosedBridge

/-!
Independently restated native C1 target. Both validation statements are named
theorems, so the kernel replay checks them as declarations. Source alone is not
a compilation or closure receipt.
-/
noncomputable section
open Zeta23.CCM Zeta23.OPICARound4.ArithmeticFrontier

namespace Zeta23.OPICARound19.Audit

/-- The statement expands the registered C1 alias, the quartic cutoff, the parity
disjunction and both native energy definitions. The physical carriers and norms
are the original ones, and no target hypothesis is introduced. -/
theorem literalC1 :
    ∀ n : ℕ, 1 ≤ n → ∃ L : ℝ, (n : ℝ) + 2 ≤ L ∧
      ((∀ u : poleNeutralEvenSubspace L (Nat.ceil (L ^ 4)),
        u ∈ evenMomentSlice L (Nat.ceil (L ^ 4)) →
          -(1 / (n : ℝ)) * ‖u‖ ^ 2 ≤
            (inner ℂ (poleNeutralEvenCompressedCanonical L (Nat.ceil (L ^ 4)) u) u).re) ∨
       (∀ v : poleNeutralOddSubspace L (Nat.ceil (L ^ 4)),
        v ∈ oddMomentSlice L (Nat.ceil (L ^ 4)) →
          -(1 / (n : ℝ)) * ‖v‖ ^ 2 ≤
            (inner ℂ (poleNeutralOddCompressedCanonical L (Nat.ceil (L ^ 4)) v) v).re)) :=
  Zeta23.OPICARound19.step4C1

/-- Exercise the existing native forward consumer using the new exact C1 proof.
The external producer itself has no dependency on the native project. -/
theorem nativeConsumerReachesMathlibRH : _root_.RiemannHypothesis :=
  riemannHypothesis_of_cofinal_moment_slice_bounds Zeta23.OPICARound19.step4C1

end Zeta23.OPICARound19.Audit

set_option pp.fullNames true
set_option pp.universes true

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound19.Audit.literalC1"
#check @Zeta23.OPICARound19.Audit.literalC1
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound19.Audit.literalC1"
#print axioms Zeta23.OPICARound19.Audit.literalC1

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound19.Audit.nativeConsumerReachesMathlibRH"
#check @Zeta23.OPICARound19.Audit.nativeConsumerReachesMathlibRH
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound19.Audit.nativeConsumerReachesMathlibRH"
#print axioms Zeta23.OPICARound19.Audit.nativeConsumerReachesMathlibRH
