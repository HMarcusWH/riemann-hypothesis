import Zeta23.RHRC.OpicaRound3AtlasExport
import Zeta23.RHRC.OpicaComposition.Export
open Lean Elab Command Meta
namespace OPICAR2Export

/-- Read a literal compiler declaration and its transitive dependency closure. -/
def emitRow (n : Name) : CommandElabM Unit := do
  let env ← getEnv
  let some idx := env.getModuleIdxFor? n
    | throwError "R2 declaration lacks imported origin: {n}"
  let origin := env.allImportedModuleNames[idx.toNat]!.toString
  Zeta23.RHRC.OpicaRound3AtlasExport.exportAtlas #[{declaration := n.toString, moduleName := origin}]
  Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants n "type"
  let closure ← liftTermElabM <| Zeta23.RHRC.OpicaComposition.dependencyClosure n
  let info ← getConstInfo n
  let isProof ← liftTermElabM <| isProp info.type
  let row := Json.mkObj [
    ("name", .str n.toString), ("is_prop", .bool isProof),
    ("dependencies", toJson (closure.toList.map Name.toString |>.mergeSort (· < ·)))]
  liftIO <| IO.println ("OPICA_R2_CLOSURE\t" ++ row.compress)

/-- Register an actual proposition binder, not a guessed string. If dependent,
    retain its full earlier telescope; this is a contextual research obligation,
    not a proof that the premise can be independently discharged. -/
def registerPremise (owner : Name) (slot : Nat) (target : Name) : CommandElabM Unit := do
  let info ← getConstInfo owner
  let (value, dependent) ← liftTermElabM do
    forallTelescope info.type fun xs _ => do
      unless slot < xs.size do throwError "R2 premise index out of range"
      let localDecl ← xs[slot]!.fvarId!.getDecl
      unless ← isProp localDecl.type do throwError "R2 binder is not a proposition"
      let dependent := localDecl.type.hasFVar
      let value ← if dependent then mkForallFVars (xs.extract 0 slot) localDecl.type else pure localDecl.type
      unless !value.hasFVar && !value.hasMVar && !value.hasLooseBVars do
        throwError "R2 premise is not closed"
      unless ← isProp value do throwError "R2 premise closure is not a proposition"
      pure (value, dependent)
  liftTermElabM <| addDecl <| .defnDecl {
    name := target, levelParams := info.levelParams, type := .sort .zero,
    value := value, hints := .abbrev, safety := .safe }
  liftIO <| IO.println ("OPICA_R2_PREMISE\t" ++
    (Json.mkObj [("owner", .str owner.toString), ("slot", toJson slot),
      ("name", .str target.toString), ("contextual", .bool dependent)]).compress)
  Zeta23.RHRC.OpicaComposition.exportTarget target "value"
  Zeta23.RHRC.OpicaComposition.exportRetrievalProofConstants target "value"

end OPICAR2Export
