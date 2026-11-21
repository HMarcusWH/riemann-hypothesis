import Lean
open Lean

partial def constantsOf (e : Expr) : List Name :=
  match e with
  | .const n _ => [n]
  | .app f a => constantsOf f ++ constantsOf a
  | .lam _ t b _ | .forallE _ t b _ => constantsOf t ++ constantsOf b
  | .letE _ t v b _ => constantsOf t ++ constantsOf v ++ constantsOf b
  | .mdata _ b => constantsOf b
  | .proj n _ b => n :: constantsOf b
  | _ => []

unsafe def main (args : List String) : IO Unit := do
  let some path := args.head? | throw <| IO.userError "object path required"
  let (data, region) ← readModuleData path
  let wanted := [`Zeta23.OPICARound20.Closed.step4C1,
    `Zeta23.OPICARound20.Closed.literalC1,
    `Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity]
  let allowed := [`Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds,
    `Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis,
    `riemannHypothesis,
    `Zeta23.OPICARound19.ClaimFingerprint.requiredC1,
    `Zeta23.OPICARound20.AllBoundaryFlatNonnegative,
    `Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative,
    `Zeta23.OPICARound20.Closed.step4C1, `Iff.mp]
  if data.isModule then throw <| IO.userError "Unexpected module-system object"
  if data.constNames != data.constants.map (·.name) then
    throw <| IO.userError "Object constant-name array mismatch"
  if data.constants.size != wanted.length then
    throw <| IO.userError s!"Unexpected declaration count: {data.constants.size}"
  let mut found : List Name := []
  for c in data.constants do
    match c with
    | .thmInfo v =>
      if !wanted.contains v.name then throw <| IO.userError s!"Unexpected declaration: {v.name}"
      if !v.levelParams.isEmpty || v.type.hasFVar || v.value.hasFVar ||
          v.type.hasMVar || v.value.hasMVar then
        throw <| IO.userError "Unexpected parameters or metavariables"
      let expectedType := if v.name == wanted[0]! then
        mkConst `Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds
        else if v.name == wanted[1]! then mkConst `Zeta23.OPICARound19.ClaimFingerprint.requiredC1
        else mkConst `Zeta23.OPICARound20.AllBoundaryFlatNonnegative
      if v.type != expectedType then throw <| IO.userError s!"Wrong closed type: {v.name}"
      if v.name == wanted[0]! then
        let expected := mkApp
          (mkConst `Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis)
          (mkConst `riemannHypothesis)
        if v.value != expected then throw <| IO.userError "Unexpected C1 proof value"
      if v.name == wanted[1]! && v.value != mkConst `Zeta23.OPICARound20.Closed.step4C1 then
        throw <| IO.userError "Unexpected literal consumer proof value"
      for n in constantsOf v.type ++ constantsOf v.value do
        if !allowed.contains n then throw <| IO.userError s!"Uncovered direct dependency: {n}"
      IO.println s!"OPICA20_ACTUAL_THEOREM {v.name}"
      IO.println s!"TYPE {v.type}"
      IO.println s!"VALUE {v.value}"
      found := v.name :: found
    | _ => throw <| IO.userError "A closed target is not a theorem"
  if !wanted.all found.contains then throw <| IO.userError "Missing closed theorem"
  region.free
  IO.println "OPICA20_CLOSED_OBJECT_AUDIT_PASS"
