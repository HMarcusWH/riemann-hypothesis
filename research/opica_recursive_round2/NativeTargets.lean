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


/-! Complete-cost optimality for the UNRESTRICTED Removal surrogate.
    This is not a statement about admissible nonempty stopped-cut policies. -/

open Zeta23.OPICARound6.PrimeFactorPaths

def emptyRemoval : Removal := ⟨∅, ∅⟩

theorem emptyRemoval_cost_zero (X : ℕ) :
    completeRemovalCost X emptyRemoval = 0 := by
  classical
  simp [completeRemovalCost, removedLabels, emptyRemoval, Removal.all, RoughNodeCharges.charge]

theorem emptyRemoval_survivor (X : ℕ) (j : Key) :
    survivorCharge X j emptyRemoval =
      RoughNodeCharges.charge (roughCutoff X) (rawLabels X j) := by
  classical
  simp [survivorCharge, survivingLabels, emptyRemoval, Removal.all]

private theorem clipped_le_add_abs (a b d : ℝ) :
    max (a-d) 0 ≤ max (b-d) 0 + |a-b| := by
  have h := abs_max_sub_max_le_abs (a-d) (b-d) 0
  rw [show (a-d)-(b-d) = a-b by ring] at h
  have h' := (le_abs_self (max (a-d) 0 - max (b-d) 0)).trans h
  linarith

def clippedOpposedEnergy (X : ℕ) (r : Removal) (pol : ℝ) : ℝ :=
  ∑ j ∈ wholeCoarseKeys X, weight j *
    max ((max (pol * survivorCharge X j r) 0)^2 -
      (unsignedDiscrepancy X j)^2) 0

theorem clippedOpposedEnergy_one (X : ℕ) (r : Removal) :
    clippedOpposedEnergy X r 1 = opposedSurvivorEnergy X r := by
  simp only [clippedOpposedEnergy, opposedSurvivorEnergy,
    NativeStoppingCost.native_opposed_cost, one_mul]

theorem clippedOpposedEnergy_neg_one (X : ℕ) (r : Removal) :
    clippedOpposedEnergy X r (-1) = reverseOpposedSurvivorEnergy X r := by
  simp only [clippedOpposedEnergy, reverseOpposedSurvivorEnergy,
    NativeStoppingCost.native_opposed_cost_reverse, neg_one_mul]

/-- Clipping by the same unsigned discrepancy cannot increase the
    positive-part square loss. The full removal charge therefore pays
    for every possible reduction of the opposed energy. -/
theorem empty_clippedOpposedEnergy_le (X : ℕ) (r : Removal)
    (pol : ℝ) (hpol : |pol| = 1) :
    clippedOpposedEnergy X emptyRemoval pol ≤
      clippedOpposedEnergy X r pol + completeRemovalCost X r := by
  unfold clippedOpposedEnergy completeRemovalCost
  rw [← Finset.sum_add_distrib]
  apply Finset.sum_le_sum
  intro j _
  rw [← mul_add]
  apply mul_le_mul_of_nonneg_left _ (weight_nonneg j)
  rw [emptyRemoval_survivor]
  let s := RoughNodeCharges.charge (roughCutoff X) (rawLabels X j)
  let t := survivorCharge X j r
  let H : ℝ := (rawLabels X j).card
  have hs : |pol*s| ≤ H := by
    rw [abs_mul, hpol, one_mul]
    exact RoughNodeCharges.abs_charge_le_card _ _
  have ht : |pol*t| ≤ H := by
    rw [abs_mul, hpol, one_mul]
    dsimp [t, H]
    unfold survivorCharge survivingLabels
    exact (RoughNodeCharges.abs_charge_le_card _ _).trans
      (by exact_mod_cast Finset.card_le_card
        (Finset.sdiff_subset (s := rawLabels X j) (t := r.all)))
  have h := FiniteSelectorEnergy.posSq_sub_le (pol*s) (pol*t) H hs ht
  have hd : s-t =
      RoughNodeCharges.charge (roughCutoff X) (removedLabels X j r) :=
    RoughNodeCharges.charge_sub_survivors (roughCutoff X) (rawLabels X j) r.all
  rw [← mul_sub, abs_mul, hpol, one_mul, hd] at h
  exact (clipped_le_add_abs ((max (pol*s) 0)^2) ((max (pol*t) 0)^2)
    ((unsignedDiscrepancy X j)^2)).trans (add_le_add_left h _)

def EmptyRemovalMinSupply : Prop :=
  CofinalSubpower (fun X => min (opposedSurvivorEnergy X emptyRemoval)
    (reverseOpposedSurvivorEnergy X emptyRemoval) + unsignedErrorEnergy X)

/-- With both signs charged on the same source and the complete removal
    penalty included, the empty policy minimizes the unrestricted budget. -/
theorem empty_min_budget_optimal (X : ℕ) (r : Removal) :
    min (opposedSurvivorEnergy X emptyRemoval)
      (reverseOpposedSurvivorEnergy X emptyRemoval) + unsignedErrorEnergy X ≤
      min (opposedSurvivorEnergy X r) (reverseOpposedSurvivorEnergy X r) +
        unsignedErrorEnergy X + completeRemovalCost X r := by
  have hp := empty_clippedOpposedEnergy_le X r 1 (by norm_num)
  have hn := empty_clippedOpposedEnergy_le X r (-1) (by norm_num)
  simp only [clippedOpposedEnergy_one] at hp
  simp only [clippedOpposedEnergy_neg_one] at hn
  rcases le_total (opposedSurvivorEnergy X r) (reverseOpposedSurvivorEnergy X r) with h | h
  · rw [min_eq_left h]
    linarith [min_le_left (opposedSurvivorEnergy X emptyRemoval)
      (reverseOpposedSurvivorEnergy X emptyRemoval)]
  · rw [min_eq_right h]
    linarith [min_le_right (opposedSurvivorEnergy X emptyRemoval)
      (reverseOpposedSurvivorEnergy X emptyRemoval)]

/-- Exact equivalence of the adaptive unrestricted supplier to one with
    NO removal parameter. The cofinal unsigned remainder remains essential. -/
theorem adaptiveMin_iff_emptyRemoval :
    AdaptiveMinOpposedSupply ↔ EmptyRemovalMinSupply := by
  constructor
  · intro h ε hε
    obtain ⟨C,hC,hw⟩ := h ε hε
    refine ⟨C,hC,?_⟩
    intro X₀
    obtain ⟨X,r,hX,hb⟩ := hw X₀
    exact ⟨X,hX,(empty_min_budget_optimal X r).trans hb⟩
  · intro h ε hε
    obtain ⟨C,hC,hw⟩ := h ε hε
    refine ⟨C,hC,?_⟩
    intro X₀
    obtain ⟨X,hX,hb⟩ := hw X₀
    refine ⟨X,emptyRemoval,hX,?_⟩
    simpa only [emptyRemoval_cost_zero, add_zero] using hb

theorem onePolarity_of_emptyRemovalSupply (h : EmptyRemovalMinSupply) :
    OnePolarityRawSubpower :=
  onePolarity_of_adaptiveMinOpposedSupply (adaptiveMin_iff_emptyRemoval.mpr h)


/-! A further finite compression: after full-cost removal elimination,
    the clipped opposed energy plus unsigned discrepancy is equivalent
    (up to factor two) to the raw minimum plus that same discrepancy. -/

def RawMinWithUnsignedSupply : Prop :=
  CofinalSubpower (fun X => min (rawPositiveEnergy X) (rawNegativeEnergy X) +
    unsignedErrorEnergy X)

private theorem opposed_nonneg (X : ℕ) (r : Removal) :
    0 ≤ opposedSurvivorEnergy X r := by
  unfold opposedSurvivorEnergy
  exact Finset.sum_nonneg fun j _ => mul_nonneg (weight_nonneg j)
    (mul_nonneg (mul_nonneg (by norm_num) (le_max_right _ _)) (le_max_right _ _))

private theorem reverse_opposed_nonneg (X : ℕ) (r : Removal) :
    0 ≤ reverseOpposedSurvivorEnergy X r := by
  unfold reverseOpposedSurvivorEnergy
  exact Finset.sum_nonneg fun j _ => mul_nonneg (weight_nonneg j)
    (mul_nonneg (mul_nonneg (by norm_num) (le_max_right _ _)) (le_max_right _ _))

/-- Exact empty-removal budget and raw-plus-unsigned comparison, at the
    same native cutoff. No asymptotic estimate is introduced. -/
theorem empty_min_budget_raw_comparison (X : ℕ) :
    (min (opposedSurvivorEnergy X emptyRemoval)
      (reverseOpposedSurvivorEnergy X emptyRemoval) + unsignedErrorEnergy X ≤
        min (rawPositiveEnergy X) (rawNegativeEnergy X) + unsignedErrorEnergy X) ∧
    (min (rawPositiveEnergy X) (rawNegativeEnergy X) + unsignedErrorEnergy X ≤
      2 * (min (opposedSurvivorEnergy X emptyRemoval)
        (reverseOpposedSurvivorEnergy X emptyRemoval) + unsignedErrorEnergy X)) := by
  have hp := rawPositiveEnergy_bracket X emptyRemoval
  have hn := rawNegativeEnergy_bracket X emptyRemoval
  simp only [emptyRemoval_cost_zero, add_zero] at hp hn
  have hu : 0 ≤ min (opposedSurvivorEnergy X emptyRemoval)
      (reverseOpposedSurvivorEnergy X emptyRemoval) :=
    le_min (opposed_nonneg X _) (reverse_opposed_nonneg X _)
  have hraw : min (rawPositiveEnergy X) (rawNegativeEnergy X) ≤
      min (opposedSurvivorEnergy X emptyRemoval)
        (reverseOpposedSurvivorEnergy X emptyRemoval) + unsignedErrorEnergy X := by
    rcases le_total (opposedSurvivorEnergy X emptyRemoval)
        (reverseOpposedSurvivorEnergy X emptyRemoval) with h | h
    · rw [min_eq_left h]
      exact (min_le_left _ _).trans hp.2
    · rw [min_eq_right h]
      exact (min_le_right _ _).trans hn.2
  constructor
  · exact add_le_add_right (min_le_min hp.1 hn.1) _
  · linarith

private theorem cofinalSubpower_mul_const (f : ℕ → ℝ) (a : ℝ)
    (ha : 0 ≤ a) (h : CofinalSubpower f) :
    CofinalSubpower (fun X => a * f X) := by
  intro ε hε
  obtain ⟨C,hC,hwin⟩ := h ε hε
  refine ⟨a*C,mul_nonneg ha hC,?_⟩
  intro X₀
  obtain ⟨X,hX,hb⟩ := hwin X₀
  refine ⟨X,hX,?_⟩
  calc
    a * f X ≤ a * (C * (X : ℝ)^ε) := mul_le_mul_of_nonneg_left hb ha
    _ = (a*C) * (X : ℝ)^ε := by ring

theorem emptyRemovalSupply_iff_rawMinUnsigned :
    EmptyRemovalMinSupply ↔ RawMinWithUnsignedSupply := by
  constructor
  · intro h
    exact cofinalSubpower_of_pointwise_le _ _
      (fun X => (empty_min_budget_raw_comparison X).2)
      (cofinalSubpower_mul_const _ 2 (by norm_num) h)
  · intro h
    exact cofinalSubpower_of_pointwise_le _ _
      (fun X => (empty_min_budget_raw_comparison X).1) h

private theorem min_add_common (a b c : ℝ) :
    min (a+c) (b+c) = min a b + c := by
  rcases le_total a b with h | h
  · rw [min_eq_left (add_le_add_right h c), min_eq_left h]
  · rw [min_eq_right (add_le_add_right h c), min_eq_right h]

/-- One fixed polarity is recovered without any exchange of quantifiers.
    BOTH terms still use the same cofinal witness. -/
theorem rawMinUnsigned_iff_fixed :
    RawMinWithUnsignedSupply ↔
      CofinalSubpower (fun X => rawPositiveEnergy X + unsignedErrorEnergy X) ∨
      CofinalSubpower (fun X => rawNegativeEnergy X + unsignedErrorEnergy X) := by
  have h : (fun X => min (rawPositiveEnergy X) (rawNegativeEnergy X) + unsignedErrorEnergy X) =
      (fun X => min (rawPositiveEnergy X + unsignedErrorEnergy X)
        (rawNegativeEnergy X + unsignedErrorEnergy X)) := by
    funext X
    exact (min_add_common _ _ _).symm
  unfold RawMinWithUnsignedSupply
  rw [h]
  exact cofinalSubpower_min_iff _ _

theorem adaptiveMin_iff_fixed_raw_unsigned :
    AdaptiveMinOpposedSupply ↔
      CofinalSubpower (fun X => rawPositiveEnergy X + unsignedErrorEnergy X) ∨
      CofinalSubpower (fun X => rawNegativeEnergy X + unsignedErrorEnergy X) :=
  adaptiveMin_iff_emptyRemoval.trans
    (emptyRemovalSupply_iff_rawMinUnsigned.trans rawMinUnsigned_iff_fixed)

end OPICAR2
