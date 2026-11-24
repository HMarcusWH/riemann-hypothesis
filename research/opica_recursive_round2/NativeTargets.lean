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

end OPICAR2
