module
public import Main

/-!
Typed ingress from the unchanged community Main. These five consumers are
independent expected statements, not new arithmetic arguments. The actual
original public roots are audited and later independently replayed.
-/
@[expose] public section

namespace OPICACommunityV436

theorem suppliedRH : RiemannHypothesis := _root_.riemannHypothesis

theorem suppliedZetaZeros :
    ∀ s : ℂ, riemannZeta s = 0 → (¬∃ n : ℕ, s = -2 * ((n : ℂ) + 1)) → s ≠ 1 → s.re = 1 / 2 :=
  _root_.riemannZeta_eq_zero_re

theorem suppliedNonvanishing :
    ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
      1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) → DirichletCharacter.LFunction χ s ≠ 0 :=
  _root_.LFunction_ne_zero_of_half_lt_re

theorem suppliedLZeros :
    ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ),
      0 < s.re → s.re < 1 → DirichletCharacter.LFunction χ s = 0 → s.re = 1 / 2 :=
  _root_.LFunction_eq_zero_re

theorem suppliedPrimitive :
    ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N), χ.IsPrimitive →
      ∀ s : ℂ, 0 < s.re → s.re < 1 → DirichletCharacter.LFunction χ s = 0 → s.re = 1 / 2 :=
  _root_.LFunction_eq_zero_re_of_isPrimitive

end OPICACommunityV436

#check (_root_.riemannHypothesis : RiemannHypothesis)
#check (OPICACommunityV436.suppliedRH : RiemannHypothesis)
#print axioms riemannHypothesis
#print axioms riemannZeta_eq_zero_re
#print axioms LFunction_ne_zero_of_half_lt_re
#print axioms LFunction_eq_zero_re
#print axioms LFunction_eq_zero_re_of_isPrimitive
#print axioms OPICACommunityV436.suppliedRH
