import Main
import OPICAStep4.NativeValidated
import Lean

open Lean Elab Command in
run_elab do
  let env ← getEnv
  for n in [`Zeta23.OPICARound20.Closed.step4C1,
            `Zeta23.OPICARound20.Closed.literalC1,
            `Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity] do
    if env.contains n then
      throwError "Forbidden preexisting closed theorem name: {n}"

#eval IO.println "OPICA20_NEW_NAMES_ABSENT"
