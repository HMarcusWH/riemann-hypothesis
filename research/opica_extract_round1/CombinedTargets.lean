import OPICAExtractionPrincipal
import OPICAExtractionNative

/-! Window-only common-pin target; no energy-adapter dependency. -/
noncomputable section
namespace OPICAExtractionR1.Combined
open Formalism.HC UpperTheory.Top

def ConditionalNativeWindows : Prop :=
  TopG → VWinAt PChar.one 401 → NativeLiteralWindows

end OPICAExtractionR1.Combined
