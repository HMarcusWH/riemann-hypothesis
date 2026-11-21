import OPICAStep4.ImportGuard

/-!
Versioned Round20 composition. Uses the exact public Main export target covered
by the independently checked supplier certificate. This source is a candidate;
only a complete modular gate receipt grants its recorded validation scope.
-/
namespace Zeta23.OPICARound20.Closed

open Zeta23.OPICARound4.ArithmeticFrontier

theorem step4C1 : CofinalMomentSliceVanishingErrorBounds :=
  cofinal_moment_slice_bounds_of_riemannHypothesis _root_.riemannHypothesis

theorem literalC1 : Zeta23.OPICARound19.ClaimFingerprint.requiredC1 :=
  step4C1

theorem fullBoundaryFlatPositivity : Zeta23.OPICARound20.AllBoundaryFlatNonnegative :=
  Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative.mp step4C1

end Zeta23.OPICARound20.Closed

set_option pp.fullNames true
set_option pp.universes true

#eval IO.println "OPICA19_TYPE_BEGIN riemannHypothesis"
#check @_root_.riemannHypothesis
#eval IO.println "OPICA19_TYPE_END riemannHypothesis"
#print axioms _root_.riemannHypothesis

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound20.Closed.step4C1"
#check @Zeta23.OPICARound20.Closed.step4C1
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound20.Closed.step4C1"
#print axioms Zeta23.OPICARound20.Closed.step4C1

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound20.Closed.literalC1"
#check @Zeta23.OPICARound20.Closed.literalC1
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound20.Closed.literalC1"
#print axioms Zeta23.OPICARound20.Closed.literalC1

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity"
#check @Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity"
#print axioms Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity
