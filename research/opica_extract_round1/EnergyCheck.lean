import OPICAExtractionEnergy
noncomputable section
example (h : OPICAExtractionR1.RampWindows) :
    ∀ η : ℝ, 0 < η → ∀ Y₀ : ℝ, ∃ Y : ℝ, max Y₀ 2 ≤ Y ∧
      Zeta23.OPICARound6.PrimeDeficit.literalGEnergy Y ≤ Y^η :=
  OPICAExtractionR1.native_energy_of_ramp_windows h
example (h : OPICAExtractionR1.DirectEnergyToC1) (w : OPICAExtractionR1.RampWindows) :
    Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds :=
  OPICAExtractionR1.native_c1_of_ramp_windows_of_direct_bridge h w
