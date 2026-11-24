import OPICAExtractionPrincipal
open Formalism.BasicNotions Formalism.MainNotions Formalism.HC GlobalTheory.EX UpperTheory.Top
noncomputable section
example (hG : UpperTheory.Top.TopG) (hV : UpperTheory.Top.VWinAt PChar.one 401) :
    ∀ θ : ℝ, 1 / 2 < θ → θ < 1 → ∃ C : ℝ, ∀ Y₀ : ℝ, ∃ Y : ℝ, Y₀ ≤ Y ∧
      ∀ y ∈ Set.Icc Y (Y^(3/2:ℝ)), OPICAExtractionR1.rampG y ≤ C*y^θ :=
  OPICAExtractionR1.principal_ramp_windows_of_topG_vwin hG hV
