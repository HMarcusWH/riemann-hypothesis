import OPICAExtractionCombinedTargets
import OPICAExtractionEnergy

/-! Preserve the actual principal telescope and consumer binder domains.
    No arithmetic or detector premise is discharged by this registration. -/
noncomputable section
namespace OPICAExtractionR1.Combined

run_cmd registerConditionalTarget
  `OPICAExtractionR1.Combined.ConditionalEnergy
  `OPICAExtractionR1.native_energy_of_ramp_windows false

run_cmd registerConditionalTarget
  `OPICAExtractionR1.Combined.ConditionalC1
  `OPICAExtractionR1.native_c1_of_ramp_windows_of_direct_bridge true

open Formalism.HC UpperTheory.Top

example : ConditionalEnergy =
    (TopG → VWinAt PChar.one 401 → NativeEnergySubpower) := rfl

example : ConditionalC1 =
    (TopG → VWinAt PChar.one 401 → DirectEnergyToC1 →
      Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds) := rfl

end OPICAExtractionR1.Combined
