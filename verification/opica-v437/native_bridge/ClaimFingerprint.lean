import Mathlib.NumberTheory.LSeries.RiemannZeta
import Zeta23.OPICARound4.ArithmeticFrontier.MomentSlices

/-!
Canonical statement fingerprint. Compile and export this module first in the
native-only common-pin environment, before loading the external solution.

These ordinary reflexivity theorems compare statements and their complete
definition dependencies. They prove neither C1 nor RH. Comparator must list the
theorems below as theorem targets and leave definition targets empty: a listed
definition target is a hole and would not bind the definition's value.
-/
noncomputable section
open Zeta23.CCM Zeta23.OPICARound4.ArithmeticFrontier

namespace Zeta23.OPICARound19.ClaimFingerprint

/-- The literal physical C1 target, with no arithmetic or RH premise. -/
def requiredC1 : Prop :=
  ∀ n : ℕ, 1 ≤ n → ∃ L : ℝ, (n : ℝ) + 2 ≤ L ∧
    ((∀ u : poleNeutralEvenSubspace L (Nat.ceil (L ^ 4)),
      u ∈ evenMomentSlice L (Nat.ceil (L ^ 4)) →
        -(1 / (n : ℝ)) * ‖u‖ ^ 2 ≤
          (inner ℂ (poleNeutralEvenCompressedCanonical L (Nat.ceil (L ^ 4)) u) u).re) ∨
     (∀ v : poleNeutralOddSubspace L (Nat.ceil (L ^ 4)),
      v ∈ oddMomentSlice L (Nat.ceil (L ^ 4)) →
        -(1 / (n : ℝ)) * ‖v‖ ^ 2 ≤
          (inner ℂ (poleNeutralOddCompressedCanonical L (Nat.ceil (L ^ 4)) v) v).re))

theorem requiredC1_reflexive : requiredC1 ↔ requiredC1 := Iff.rfl

/-- Comparing this theorem also binds the registered native C1 definition. -/
theorem requiredC1_is_native :
    requiredC1 ↔ CofinalMomentSliceVanishingErrorBounds := Iff.rfl

/-- RH is compared separately because the C1 target alone need not mention zeta. -/
theorem requiredRH_reflexive :
    _root_.RiemannHypothesis ↔ _root_.RiemannHypothesis := Iff.rfl

end Zeta23.OPICARound19.ClaimFingerprint
