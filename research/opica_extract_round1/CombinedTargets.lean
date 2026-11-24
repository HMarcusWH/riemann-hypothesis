import OPICAExtractionPrincipal
import OPICAExtractionEnergy

/-! Literal expected targets for a same-pin port of a research composition.
    These definitions assert no proof. They remain conditional, including
    the OPEN direct detector premise. -/
noncomputable section
namespace OPICAExtractionR1.Combined
open Formalism.HC UpperTheory.Top

def ConditionalNativeWindows : Prop :=
  TopG → VWinAt PChar.one 401 → NativeLiteralWindows

def ConditionalEnergy : Prop :=
  TopG → VWinAt PChar.one 401 → NativeEnergySubpower

def ConditionalC1 : Prop :=
  TopG → VWinAt PChar.one 401 → DirectEnergyToC1 →
    Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds

end OPICAExtractionR1.Combined
