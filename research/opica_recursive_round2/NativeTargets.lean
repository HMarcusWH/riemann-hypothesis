import Zeta23.OPICARound6.NextSearch.BipolarTransfer
import Zeta23.OPICARound6.PrimeDeficit.Source
import Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentClosure

/-! Research targets only. No new independent arithmetic bound is asserted. -/
noncomputable section
namespace OPICAR2
open Zeta23.OPICARound6.NextSearch
open Zeta23.OPICARound6.PrimeFactorPaths.NativeCells
open Zeta23.OPICARound6.PrimeDeficit
open Zeta23.OPICARound4.ArithmeticFrontier

def C1Named : Prop := CofinalMomentSliceVanishingErrorBounds
def PositiveNamed : Prop := PositiveRawSubpower
def NegativeNamed : Prop := NegativeRawSubpower
def OnePolarityNamed : Prop := OnePolarityRawSubpower
def DeficitNamed : Prop := LargePrimeDeficitSubpower
def DeficitBridgeNamed : Prop := MissingPrimeDeficitToLiteralGBridge

def UniformRemainder : Prop :=
  ∃ r : ℕ → Removal,
    TailSubpower (fun X => unsignedErrorEnergy X + completeRemovalCost X (r X))

def SamePolicyOpposedSupply : Prop :=
  ∃ r : ℕ → Removal,
    TailSubpower (fun X => unsignedErrorEnergy X + completeRemovalCost X (r X)) ∧
      (CofinalSubpower (fun X => opposedSurvivorEnergy X (r X)) ∨
       CofinalSubpower (fun X => reverseOpposedSurvivorEnergy X (r X)))

theorem onePolarity_of_samePolicyOpposedSupply (h : SamePolicyOpposedSupply) :
    OnePolarityRawSubpower := by
  obtain ⟨r, hr, hs⟩ := h
  exact (onePolarityRawSubpower_iff_opposed_of_tail_error r hr).mpr hs

/-- Weaker sufficient target: the opposed energy and its full remainder
are small on the same cofinal scales, with fixed polarity and policy. -/
def JointCofinalOpposedSupply : Prop :=
  ∃ r : ℕ → Removal,
    CofinalSubpower (fun X => opposedSurvivorEnergy X (r X) +
      unsignedErrorEnergy X + completeRemovalCost X (r X)) ∨
    CofinalSubpower (fun X => reverseOpposedSurvivorEnergy X (r X) +
      unsignedErrorEnergy X + completeRemovalCost X (r X))

theorem cofinalSubpower_of_pointwise_le (f g : ℕ → ℝ)
    (hfg : ∀ X, f X ≤ g X) (hg : CofinalSubpower g) : CofinalSubpower f := by
  intro ε hε
  obtain ⟨C,hC,hwin⟩ := hg ε hε
  refine ⟨C,hC,?_⟩
  intro X₀
  obtain ⟨X,hX,hbound⟩ := hwin X₀
  exact ⟨X,hX,(hfg X).trans hbound⟩

theorem onePolarity_of_jointCofinalOpposedSupply (h : JointCofinalOpposedSupply) :
    OnePolarityRawSubpower := by
  obtain ⟨r,hs⟩ := h
  rcases hs with hp | hn
  · left
    change CofinalSubpower rawPositiveEnergy
    exact cofinalSubpower_of_pointwise_le _ _ (fun X => (rawPositiveEnergy_bracket X (r X)).2) hp
  · right
    change CofinalSubpower rawNegativeEnergy
    exact cofinalSubpower_of_pointwise_le _ _ (fun X => (rawNegativeEnergy_bracket X (r X)).2) hn

/-- At each cofinal witness the removal may be chosen anew. Polarity
    stays fixed before every exponent and horizon. This weakens the fixed
    policy contract; it does not claim an admissible stopped-cut graph. -/
def AdaptiveOpposedSupply (opposed : ℕ → Removal → ℝ) : Prop :=
  ∀ ε : ℝ, 0 < ε → ∃ C : ℝ, 0 ≤ C ∧ ∀ X₀ : ℕ,
    ∃ X : ℕ, ∃ r : Removal, max X₀ 64 ≤ X ∧
      opposed X r + unsignedErrorEnergy X + completeRemovalCost X r ≤
        C * (X : ℝ)^ε

def AdaptiveOnePolarityOpposedSupply : Prop :=
  AdaptiveOpposedSupply opposedSurvivorEnergy ∨
    AdaptiveOpposedSupply reverseOpposedSurvivorEnergy

def AdaptiveBipolarSupply : Prop :=
  AdaptiveOpposedSupply pairedOpposedSurvivorEnergy

def BipolarRawSubpower : Prop := CofinalSubpower rawSquareEnergy

theorem cofinalSubpower_of_adaptiveOpposedSupply
    (raw : ℕ → ℝ) (opp : ℕ → Removal → ℝ)
    (hb : ∀ X r, raw X ≤ opp X r + unsignedErrorEnergy X + completeRemovalCost X r)
    (h : AdaptiveOpposedSupply opp) : CofinalSubpower raw := by
  intro ε hε
  obtain ⟨C,hC,hw⟩ := h ε hε
  refine ⟨C,hC,?_⟩
  intro X₀
  obtain ⟨X,r,hX,hbnd⟩ := hw X₀
  exact ⟨X,hX,(hb X r).trans hbnd⟩

theorem onePolarity_of_adaptiveOpposedSupply
    (h : AdaptiveOnePolarityOpposedSupply) : OnePolarityRawSubpower := by
  rcases h with hp | hn
  · left
    change CofinalSubpower rawPositiveEnergy
    exact cofinalSubpower_of_adaptiveOpposedSupply _ _ (fun X r => (rawPositiveEnergy_bracket X r).2) hp
  · right
    change CofinalSubpower rawNegativeEnergy
    exact cofinalSubpower_of_adaptiveOpposedSupply _ _ (fun X r => (rawNegativeEnergy_bracket X r).2) hn

theorem adaptiveOpposedSupply_of_fixed (opp : ℕ → Removal → ℝ)
    (r : ℕ → Removal)
    (h : CofinalSubpower (fun X => opp X (r X) +
      unsignedErrorEnergy X + completeRemovalCost X (r X))) :
    AdaptiveOpposedSupply opp := by
  intro ε hε
  obtain ⟨C,hC,hw⟩ := h ε hε
  refine ⟨C,hC,?_⟩
  intro X₀
  obtain ⟨X,hX,hb⟩ := hw X₀
  exact ⟨X,r X,hX,hb⟩

theorem adaptiveOpposedSupply_of_jointCofinal
    (h : JointCofinalOpposedSupply) : AdaptiveOnePolarityOpposedSupply := by
  obtain ⟨r,hs⟩ := h
  rcases hs with hp | hn
  · exact Or.inl (adaptiveOpposedSupply_of_fixed _ r hp)
  · exact Or.inr (adaptiveOpposedSupply_of_fixed _ r hn)

/-- Both polarities share the same witness and pay the remainder once. -/
theorem bipolarRaw_of_adaptiveSupply (h : AdaptiveBipolarSupply) :
    BipolarRawSubpower := by
  change CofinalSubpower rawSquareEnergy
  exact cofinalSubpower_of_adaptiveOpposedSupply rawSquareEnergy pairedOpposedSurvivorEnergy
    (fun X r => by
      rw [rawSquareEnergy_eq_polarities]
      exact (rawBipolarEnergy_bracket X r).2) h

theorem onePolarity_of_bipolarRaw (h : BipolarRawSubpower) : OnePolarityRawSubpower := by
  left
  change CofinalSubpower rawPositiveEnergy
  apply cofinalSubpower_of_pointwise_le rawPositiveEnergy rawSquareEnergy _ h
  intro X
  rw [rawSquareEnergy_eq_polarities]
  have hn : 0 ≤ rawNegativeEnergy X := by
    unfold rawNegativeEnergy
    exact Finset.sum_nonneg fun j _ => mul_nonneg (weight_nonneg j) (sq_nonneg _)
  linarith

/-- A finite choice of two signs can be fixed across all exponents by
    the cofinal quantifiers. No bound on either energy is assumed. -/
private theorem failure_threshold (f : ℕ → ℝ) (h : ¬ CofinalSubpower f) :
    ∃ ε : ℝ, 0 < ε ∧ ∀ C : ℝ, 0 ≤ C → ∃ X₀ : ℕ, ∀ X : ℕ,
      max X₀ 64 ≤ X → C * (X : ℝ)^ε < f X := by
  unfold CofinalSubpower at h
  push_neg at h
  exact h

theorem cofinalSubpower_min_iff (f g : ℕ → ℝ) :
    CofinalSubpower (fun X => min (f X) (g X)) ↔
      CofinalSubpower f ∨ CofinalSubpower g := by
  classical
  constructor
  · intro h
    by_cases hf : CofinalSubpower f
    · exact Or.inl hf
    by_cases hg : CofinalSubpower g
    · exact Or.inr hg
    exfalso
    obtain ⟨ε,hε,hf'⟩ := failure_threshold f hf
    obtain ⟨δ,hδ,hg'⟩ := failure_threshold g hg
    obtain ⟨C,hC,hw⟩ := h (min ε δ) (lt_min hε hδ)
    obtain ⟨A,hA⟩ := hf' C hC
    obtain ⟨B,hB⟩ := hg' C hC
    obtain ⟨X,hX,hmin⟩ := hw (max A B)
    have h64 : 64 ≤ X := (le_max_right (max A B) 64).trans hX
    have hab : max A B ≤ X := (le_max_left (max A B) 64).trans hX
    have hXA : max A 64 ≤ X := max_le ((le_max_left A B).trans hab) h64
    have hXB : max B 64 ≤ X := max_le ((le_max_right A B).trans hab) h64
    have hX1 : (1 : ℝ) ≤ (X : ℝ) := by exact_mod_cast (show 1 ≤ X by omega)
    have hpf := mul_le_mul_of_nonneg_left
      (Real.rpow_le_rpow_of_exponent_le hX1 (min_le_left ε δ)) hC
    have hpg := mul_le_mul_of_nonneg_left
      (Real.rpow_le_rpow_of_exponent_le hX1 (min_le_right ε δ)) hC
    exact (not_lt_of_ge hmin) (lt_min (hpf.trans_lt (hA X hXA)) (hpg.trans_lt (hB X hXB)))
  · intro h
    rcases h with hf | hg
    · exact cofinalSubpower_of_pointwise_le _ _ (fun X => min_le_left (f X) (g X)) hf
    · exact cofinalSubpower_of_pointwise_le _ _ (fun X => min_le_right (f X) (g X)) hg

def MinPolarityRawSubpower : Prop :=
  CofinalSubpower (fun X => min (rawPositiveEnergy X) (rawNegativeEnergy X))

theorem minPolarityRawSubpower_iff :
    MinPolarityRawSubpower ↔ OnePolarityRawSubpower := by
  change CofinalSubpower (fun X => min (rawPositiveEnergy X) (rawNegativeEnergy X)) ↔
    CofinalSubpower rawPositiveEnergy ∨ CofinalSubpower rawNegativeEnergy
  exact cofinalSubpower_min_iff _ _

/-- The sign and removal may both vary at the selected cutoff. The finite
    bracket and min theorem recover one fixed polarity after the fact. -/
def AdaptiveMinOpposedSupply : Prop :=
  AdaptiveOpposedSupply (fun X r => min (opposedSurvivorEnergy X r)
    (reverseOpposedSurvivorEnergy X r))

theorem onePolarity_of_adaptiveMinOpposedSupply (h : AdaptiveMinOpposedSupply) :
    OnePolarityRawSubpower := by
  apply minPolarityRawSubpower_iff.mp
  change CofinalSubpower (fun X => min (rawPositiveEnergy X) (rawNegativeEnergy X))
  apply cofinalSubpower_of_adaptiveOpposedSupply _ _ _ h
  intro X r
  rcases le_total (opposedSurvivorEnergy X r) (reverseOpposedSurvivorEnergy X r) with hp | hn
  · rw [min_eq_left hp]
    exact (min_le_left _ _).trans (rawPositiveEnergy_bracket X r).2
  · rw [min_eq_right hn]
    exact (min_le_right _ _).trans (rawNegativeEnergy_bracket X r).2

end OPICAR2
