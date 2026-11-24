import OPICAExtractionPrincipal
import Zeta23.RHRC.OpicaTypeExprExport
import Lean.Util.FoldConsts
import Lean.Util.CollectAxioms

open Lean Elab Command Meta
set_option maxHeartbeats 0

namespace OPICAExtractionR1.Audit

def forbiddenSuffixes : List String :=
  ["riemannHypothesis", "rhOfAll", "allChi", "claimAll", "critAll",
   "riemannZeta_eq_zero_re", "LFunction_ne_zero_of_half_lt_re", "LFunction_eq_zero_re",
   "LFunction_eq_zero_re_of_isPrimitive", "everyCharacter", "everyCharacter_of_row",
   "every_character_of_literature_of_vWin", "zeroFreeAll_of_topG",
   "zero_free_all_of_green_v_win", "zeroFree_of_rpow_window", "formB",
   "level_of_tiedWin", "zeroFreeOn_of_tiedWin_cyc"]

def closure (root : Name) : CoreM (Array Name) := do
  let mut seen : NameSet := {}
  let mut discovered : NameSet := {}
  discovered := discovered.insert root
  let mut todo := #[root]
  let mut i := 0
  while i < todo.size do
    if todo.size > 250000 then throwError "principal audit closure budget"
    let n := todo[i]!
    i := i+1
    if seen.contains n then continue
    seen := seen.insert n
    if forbiddenSuffixes.any (fun s => n.toString == s || n.toString.endsWith ("." ++ s)) then
      throwError "forbidden endpoint dependency {n}"
    let info ← getConstInfo n
    let mut deps := info.type.getUsedConstantsAsSet
    if let some v := info.value? (allowOpaque := true) then
      deps := deps.merge v.getUsedConstantsAsSet
    match info with
    | .inductInfo q =>
      for c in q.ctors ++ q.all do deps := deps.insert c
    | .ctorInfo q => deps := deps.insert q.induct
    | .recInfo q =>
      for c in q.all do deps := deps.insert c
      for rule in q.rules do
        deps := deps.insert rule.ctor
        deps := deps.merge rule.rhs.getUsedConstantsAsSet
    | _ => pure ()
    for q in deps.toList do
      if !discovered.contains q then
        discovered := discovered.insert q
        todo := todo.push q
  pure seen.toList.toArray

def emit (n : Name) : CommandElabM Unit := do
  let info ← getConstInfo n
  let deps ← liftTermElabM <| closure n
  let axs ← Lean.collectAxioms n
  for ax in axs do
    unless ax == ``propext || ax == ``Classical.choice || ax == ``Quot.sound do
      throwError "unapproved transitive axiom {ax}"
  let dagText ← liftIO <| Zeta23.RHRC.OpicaTypeExprExport.exportType info.type
  let dag ← ofExcept <| Json.parse dagText
  let proofs ← liftTermElabM do
    let mut ps : List String := []
    for used in info.type.getUsedConstantsAsSet.toList do
      if ← isProp (← getConstInfo used).type then ps := used.toString :: ps
    return ps.mergeSort (· < ·)
  let j := Json.mkObj [
    ("name", .str n.toString), ("type_expression", dag),
    ("proof_constants", toJson proofs),
    ("axioms", toJson (axs.toList.map Name.toString)),
    ("dependency_names", toJson (deps.toList.map Name.toString))]
  liftIO <| IO.println ("OPICA_R1_PRINCIPAL\t" ++ j.compress)

end OPICAExtractionR1.Audit
run_cmd OPICAExtractionR1.Audit.emit `OPICAExtractionR1.principal_ramp_windows_of_topG_vwin
run_cmd OPICAExtractionR1.Audit.emit `OPICAExtractionR1.principal_ramp_windows_of_topG_host
run_cmd OPICAExtractionR1.Audit.emit `OPICAExtractionR1.principal_vwin_of_all
