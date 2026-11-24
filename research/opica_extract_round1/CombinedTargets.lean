import OPICAExtractionPrincipal
import OPICAExtractionNative
import Lean

/-! Construct the conditional target from the actual supplier telescope.
    A source-written numeral can acquire a private generated proof constant
    during elaboration (observed at 401). This command preserves the exact
    compiler domains; it does not erase proofs or relax type comparison. -/
noncomputable section
open Lean Elab Command Meta

namespace OPICAExtractionR1.Combined

/-- Assemble the same closed proposition as the retrieval engine, using only
    the fixed principal supplier and one reviewed window/energy consumer. -/
def registerConditionalTarget (target consumer : Name) (hasBridge : Bool) :
    CommandElabM Unit := do
  let p ← getConstInfo `OPICAExtractionR1.principal_ramp_windows_of_topG_vwin
  let c ← getConstInfo consumer
  unless p.levelParams.isEmpty && c.levelParams.isEmpty do
    throwError "unexpected polymorphic interface in conditional target"
  let .forallE n₁ d₁ rest bi₁ := p.type
    | throwError "principal first binder differs"
  let .forallE n₂ d₂ last bi₂ := rest
    | throwError "principal second binder differs"
  unless last.isConstOf `OPICAExtractionR1.RampWindows do
    throwError "principal supplier conclusion differs"
  let tail ← if hasBridge then do
      let .forallE n d rest bi := c.type
        | throwError "missing direct bridge binder"
      let .forallE _ dw result _ := rest
        | throwError "missing ramp-window binder"
      unless d.isConstOf `OPICAExtractionR1.DirectEnergyToC1 &&
          dw.isConstOf `OPICAExtractionR1.RampWindows &&
          !d.hasLooseBVars && !result.hasLooseBVars do
        throwError "conditional bridge interface differs"
      pure (.forallE n d result bi)
    else do
      let .forallE _ dw result _ := c.type
        | throwError "missing ramp-window binder"
      unless dw.isConstOf `OPICAExtractionR1.RampWindows && !result.hasLooseBVars do
        throwError "conditional consumer interface differs"
      pure result
  unless !d₁.hasLooseBVars && !d₂.hasLooseBVars do
    throwError "dependent principal interface requires a different adapter"
  let value := Expr.forallE n₁ d₁ (.forallE n₂ d₂ tail bi₂) bi₁
  liftTermElabM do
    unless ← isProp value do
      throwError "conditional target is not a proposition"
    addDecl <| .defnDecl {
      name := target, levelParams := [], type := .sort .zero,
      value := value, hints := .abbrev, safety := .safe }

run_cmd registerConditionalTarget
  `OPICAExtractionR1.Combined.ConditionalNativeWindows
  `OPICAExtractionR1.native_windows_of_ramp_windows false

open Formalism.HC UpperTheory.Top

/-- Independently stated interface check, not a proof of the target. -/
example : ConditionalNativeWindows =
    (TopG → VWinAt PChar.one 401 → NativeLiteralWindows) := rfl

end OPICAExtractionR1.Combined
