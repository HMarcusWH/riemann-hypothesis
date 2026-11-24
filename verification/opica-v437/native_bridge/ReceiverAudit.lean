import Zeta23.OPICARound4.ArithmeticFrontier.ZeroFreeFloor

/-!
Common-version audit of the existing native receiving theorem.
This file is deliberately conditional on RH and is not the closed Step 4 proof.
The separately named ClosedBridge module must supply the actual external theorem.
-/

noncomputable section
open Zeta23.CCM Zeta23.OPICARound4.ArithmeticFrontier

namespace Zeta23.OPICARound19.ReceiverAudit

theorem exactReceiver :
    _root_.RiemannHypothesis →
    ∀ n : ℕ, 1 ≤ n → ∃ L : ℝ, (n : ℝ) + 2 ≤ L ∧
      ((∀ u : poleNeutralEvenSubspace L (Nat.ceil (L ^ 4)),
        u ∈ evenMomentSlice L (Nat.ceil (L ^ 4)) →
          -(1 / (n : ℝ)) * ‖u‖ ^ 2 ≤
            (inner ℂ (poleNeutralEvenCompressedCanonical L (Nat.ceil (L ^ 4)) u) u).re) ∨
       (∀ v : poleNeutralOddSubspace L (Nat.ceil (L ^ 4)),
        v ∈ oddMomentSlice L (Nat.ceil (L ^ 4)) →
          -(1 / (n : ℝ)) * ‖v‖ ^ 2 ≤
            (inner ℂ (poleNeutralOddCompressedCanonical L (Nat.ceil (L ^ 4)) v) v).re)) :=
  cofinal_moment_slice_bounds_of_riemannHypothesis

theorem exactZeroErrorReceiver (hRH : _root_.RiemannHypothesis)
    {L : ℝ} (hL : 0 < L) (K : ℕ) :
    EvenMomentSliceLowerBound L K 0 ∧ OddMomentSliceLowerBound L K 0 :=
  momentSliceLowerBounds_zero_of_riemannHypothesis hRH hL K

end Zeta23.OPICARound19.ReceiverAudit

set_option pp.fullNames true in
#check @Zeta23.OPICARound19.ReceiverAudit.exactReceiver
#print axioms Zeta23.OPICARound19.ReceiverAudit.exactReceiver
#print axioms Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver
