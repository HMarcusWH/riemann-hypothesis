import Lean

/-!
Diagnostic only. This executable does not construct, export, replay, or accept any
project theorem. It uses the public, unmodified Lean 4.33.1 import functions.

The `exact-guard` import array is copied from the recorded Round24 KernelBridge
header. The `lean-control` array is a separate small local control and must never
be reported as evidence that the supplier or guard imported successfully.

The split path preserves the production import settings: empty options/plugins/
artifact overrides, trustLevel=0, private level, leakEnv=true, loadExts=false.
It follows Lean.importModules' public implementation but inserts flushed markers
between importModulesCore and finalizeImport. The stock path calls importModules
directly with the same settings. Neither mode writes an olean or proof receipt.
-/

open Lean

namespace ImportPhaseProbe

def initImports : Array Import := #[{module := `Init}, {module := `Init, isMeta := true}]

def exactGuardImports : Array Import := initImports ++ #[
  {module := `Main}, {module := `OPICAStep4.NativeValidated}, {module := `Lean}]

def leanControlImports : Array Import := initImports ++ #[{module := `Lean}]

def emit (message : String) : IO Unit := do
  let out ← IO.getStdout
  out.putStrLn s!"IMPORT_DIAGNOSTIC mono_ms={← IO.monoMsNow} {message}"
  out.flush

def splitImport (imports : Array Import) : IO Environment := do
  -- This rejects the same malformed import input as Lean.importModules.
  for imp in imports do
    if imp.module matches .anonymous then
      throw <| IO.userError "import failed, trying to import module with anonymous name"
  withImporting do
    -- Production has no plugins and no artifact overrides.
    emit "CORE_BEGIN"
    let (_, state) ← importModulesCore (globalLevel := .private) imports {} |>.run
    emit "CORE_END"
    emit "FINALIZE_BEGIN leakEnv=true loadExts=false level=private trustLevel=0"
    let env ← finalizeImport (leakEnv := true) (loadExts := false) (level := .private)
      state imports {} 0
    emit "FINALIZE_END"
    return env

def run (selection mode : String) : IO Unit := do
  let imports ← match selection with
    | "exact-guard" => pure exactGuardImports
    | "lean-control" => pure leanControlImports
    | _ => throw <| IO.userError "selection must be exact-guard or lean-control"
  emit s!"DIAGNOSTIC_ONLY selection={selection} mode={mode} imports={imports}"
  emit "NO_THEOREM_ACCEPTANCE no_object_output no_kernel_replay no_axiom_audit"
  let env ← match mode with
    | "split" => splitImport imports
    | "stock" => do
      emit "STOCK_IMPORT_BEGIN"
      let env ← importModules imports {} (trustLevel := 0) (loadExts := false)
        (leakEnv := true) (level := .private)
      emit "STOCK_IMPORT_END"
      pure env
    | _ => throw <| IO.userError "mode must be split or stock"
  if env.header.isModule || env.header.imports != imports || env.header.trustLevel != 0 then
    throw <| IO.userError "diagnostic imported environment header mismatch"
  emit s!"HEADER_MATCH modules={env.allImportedModuleNames.size}"
  emit "DIAGNOSTIC_COMPLETE no_proof_validity_established"

end ImportPhaseProbe

def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  match args with
    | [selection, mode] => ImportPhaseProbe.run selection mode
    | _ => throw <| IO.userError "Usage: import_phase_probe (exact-guard|lean-control) (split|stock)"
  return 0
