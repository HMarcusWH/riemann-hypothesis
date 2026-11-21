import OPICAStep4.IndependentConsumer
import OPICAStep4.ClaimFingerprint

/-!
The solver must actually prove the separately fingerprinted C1 target.
Fingerprint reflexivity by itself is never a closure result.
-/
namespace Zeta23.OPICARound19.Audit

theorem provedRequiredC1 : ClaimFingerprint.requiredC1 := literalC1

end Zeta23.OPICARound19.Audit

set_option pp.fullNames true
set_option pp.universes true

#eval IO.println "OPICA19_TYPE_BEGIN Zeta23.OPICARound19.Audit.provedRequiredC1"
#check @Zeta23.OPICARound19.Audit.provedRequiredC1
#eval IO.println "OPICA19_TYPE_END Zeta23.OPICARound19.Audit.provedRequiredC1"
#print axioms Zeta23.OPICARound19.Audit.provedRequiredC1
