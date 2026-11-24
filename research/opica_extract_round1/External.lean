import OPICAExtractionCommon
import Development.AutomorphicArithmetic.DedekindLFunctions.CharFamily

noncomputable section
namespace OPICAExtractionR1

theorem external_G_eq_rampG (y : ℝ) : Deduction.G y = rampG y := by
  have hr : (∑ n ∈ Finset.range (⌊y⌋₊ + 1),
      (ArithmeticFunction.vonMangoldt n : ℂ) * (1 : ℂ) *
        ((max (y / (n : ℝ) - 1) 0 : ℝ) : ℂ)).re =
      ∑ n ∈ Finset.range (⌊y⌋₊ + 1),
        ArithmeticFunction.vonMangoldt n * max (y / (n : ℝ) - 1) 0 := by
    change Complex.reCLM (∑ n ∈ Finset.range (⌊y⌋₊ + 1),
      (ArithmeticFunction.vonMangoldt n : ℂ) * (1 : ℂ) *
        ((max (y / (n : ℝ) - 1) 0 : ℝ) : ℂ)) = _
    rw [map_sum]
    apply Finset.sum_congr rfl
    intro n hn
    simp [Complex.mul_re]
  unfold Deduction.G Deduction.ramp rampG
  rw [hr]

theorem external_windows_to_ramp (h : OneSidedWindows Deduction.G) :
    OneSidedWindows rampG :=
  windows_congr external_G_eq_rampG h

end OPICAExtractionR1
#print axioms OPICAExtractionR1.external_G_eq_rampG
#print axioms OPICAExtractionR1.external_windows_to_ramp
