import OPICAExtractionPrincipal
import Development.AbelianVarietyTheory.Proofs.GlobalInterpolation.ShapeOf
import Development.AutomorphicArithmetic.CharacterBoxes.ShapeWin

/-! The exact shape arguments preceding plugWin, without its endpoint. -/
noncomputable section
open Formalism.BasicNotions Formalism.MainNotions Formalism.HC GlobalTheory.EX GlobalTheory.Fc UpperTheory.Top
namespace OPICAR2Original

theorem topG_of_green_hyps (hG : GlobalTheory.GLq.Green)
    (h : Nonempty (Hyps (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) DRS)) :
    TopG :=
  h.elim fun h => GlobalTheory.Fc.shape_of _ _ _ _ (UpperTheory.Top.shapeWin hG) trivial trivial h

theorem principal_connected_of_green_hyps_host (hG : GlobalTheory.GLq.Green)
    (h : Nonempty (Hyps (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) DRS))
    (hS : HostExW (3 / 2 : ℝ) (GChi PChar.one).req) :
    OPICAExtractionR1.PrincipalConnected :=
  OPICAExtractionR1.principal_connected_of_topG_host (topG_of_green_hyps hG h) hS

end OPICAR2Original
