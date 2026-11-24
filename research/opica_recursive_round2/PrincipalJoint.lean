import OPICAExtractionPrincipal
import Development.AutomorphicArithmetic.AutomorphicVarieties.HeightAndVanishing.JointWinOfCounts

/-! Small original-source joint-window cut found in the authenticated
export. Neither JointWin nor ThmBc nor TopG is proved here. -/
noncomputable section
open Formalism.BasicNotions Formalism.MainNotions Formalism.HC GlobalTheory.EX UpperTheory.Top UpperTheory.V

namespace OPICAR2Original

theorem principal_vwin_of_joint
    (hJ : JointWin 401) (hc : ThmBc 401) : VWinAt PChar.one 401 :=
  (vwin_of_joint hJ hc) PChar.one

theorem principal_host_of_joint
    (hJ : JointWin 401) (hc : ThmBc 401) :
    HostExW (3 / 2 : ℝ) (GChi PChar.one).req :=
  supplyChi PChar.one (principal_vwin_of_joint hJ hc)

theorem principal_windows_of_joint_topG
    (hG : TopG) (hJ : JointWin 401) (hc : ThmBc 401) :
    OPICAExtractionR1.RampWindows :=
  OPICAExtractionR1.principal_ramp_windows_of_topG_host hG
    (principal_host_of_joint hJ hc)

end OPICAR2Original
