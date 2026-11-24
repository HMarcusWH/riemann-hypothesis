import OPICAExtractionPrincipal
import OPICAR2Export

/-! Exact original compiler telescope domains, not freshly elaborated
    copies of numeric typeclass evidence. The common-pin compiler audits
    the reconstructed values against the authenticated retrieval types. -/
namespace OPICAR2Original

run_cmd OPICAR2Export.registerPremise
  `OPICAExtractionR1.principal_ramp_windows_of_connected 0
  `OPICAR2Original.PrincipalConnectedNamed

def RampWindowsNamed : Prop := OPICAExtractionR1.RampWindows

run_cmd OPICAR2Export.registerPremise
  `OPICAExtractionR1.principal_ramp_windows_of_topG_vwin 0
  `OPICAR2Original.TopGNamed

run_cmd OPICAR2Export.registerPremise
  `OPICAExtractionR1.principal_connected_of_topG_host 1
  `OPICAR2Original.PrincipalHostNamed

run_cmd OPICAR2Export.registerPremise
  `OPICAExtractionR1.principal_ramp_windows_of_topG_vwin 1
  `OPICAR2Original.PrincipalVWinNamed

run_cmd OPICAR2Export.registerPremise
  `OPICAExtractionR1.principal_vwin_of_all 0
  `OPICAR2Original.VWinNamed

end OPICAR2Original
