import OPICAExtractionCombinedTargets
import OPICAExtractionEnergy

/-! Conditional energy and C1 queries; all arithmetic and direct bridge
premises are retained. -/
noncomputable section
namespace OPICAExtractionR1.Combined
open Formalism.HC UpperTheory.Top

def ConditionalEnergy : Prop :=
  TopG → VWinAt PChar.one 401 → NativeEnergySubpower

def ConditionalC1 : Prop :=
  TopG → VWinAt PChar.one 401 → DirectEnergyToC1 →
    Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds

end OPICAExtractionR1.Combined
