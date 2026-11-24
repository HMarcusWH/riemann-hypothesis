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

end OPICAR2
