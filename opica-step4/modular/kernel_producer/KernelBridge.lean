import Lean

/-!
Stock Lean 4.33.1 kernel producer for the three frozen Round20 proof expressions.
This does not claim that the original source files elaborated. It imports their
exact ordinary headers with loadExts=false, checks fresh theorem declarations
through Environment.addDeclCore(doCheck=true), and uses the stock module-data
writer. Empty newly authored extension metadata is an explicit difference from
elaborator output; no logical constant, type, proof, or import is omitted.

The imported environment is retained until process exit (leakEnv=true). This
avoids final RC/free walks; no imported regions are manually freed. Imported
proof validity still requires the separate stock/identity/independent gates.
-/

open Lean

namespace KernelBridge

def guardModule : Name := `OPICAStep4.ImportGuard
def closedModule : Name := `OPICAStep4.MainClosedBridge
def closedNames : Array Name := #[
  `Zeta23.OPICARound20.Closed.step4C1,
  `Zeta23.OPICARound20.Closed.literalC1,
  `Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity]

/-- Exact implicit imports inserted by the pinned HeaderSyntax.imports. -/
def initImports : Array Import := #[{module := `Init}, {module := `Init, isMeta := true}]
def guardImports : Array Import := initImports ++ #[
  {module := `Main}, {module := `OPICAStep4.NativeValidated}, {module := `Lean}]
def closedImports : Array Import := initImports ++ #[{module := guardModule}]

def closedTypeNames : Array Name := #[
  `Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredC1,
  `Zeta23.OPICARound20.AllBoundaryFlatNonnegative]

def closedValues : Array Expr := #[
  mkApp (mkConst `Zeta23.OPICARound4.ArithmeticFrontier.cofinal_moment_slice_bounds_of_riemannHypothesis)
    (mkConst `riemannHypothesis),
  mkConst closedNames[0]!,
  mkApp4 (mkConst `Iff.mp)
    (mkConst closedTypeNames[0]!) (mkConst closedTypeNames[2]!)
    (mkConst `Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative)
    (mkConst closedNames[0]!)]


/- Generated from round21 modular constants; see SELECTED_ROOT_INVENTORY.json. -/
def selectedRootNames : Array Name := #[
  `Quot,
  `Quot.mk,
  `Quot.lift,
  `Quot.ind,
  `riemannHypothesis,
  `riemannZeta_eq_zero_re,
  `LFunction_ne_zero_of_half_lt_re,
  `LFunction_eq_zero_re,
  `LFunction_eq_zero_re_of_isPrimitive,
  `propext,
  `Quot.sound,
  `Classical.choice,
  `Nat.add,
  `Nat.sub,
  `Nat.mul,
  `Nat.pow,
  `Nat.gcd,
  `Nat.div,
  `Nat.mod,
  `Nat.beq,
  `Nat.ble,
  `Nat.land,
  `Nat.lor,
  `Nat.xor,
  `Nat.shiftLeft,
  `Nat.shiftRight,
  `String.ofList,
  `Char.ofNat,
  `List,
  `eagerReduce,
  `Nat,
  `String,
  `String.mk,
  `Char,
  `optParam,
  `autoParam,
  `semiOutParam,
  `outParam,
  `Zeta23.OPICARound19.ReceiverAudit.exactReceiver,
  `Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredC1_reflexive,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredC1_is_native,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive,
  `Zeta23.OPICARound20.even_zero_bound_of_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.riemannHypothesis_iff_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.finite_negative_boundary_flat_witness_refutes_c1,
  `Zeta23.OPICARound20.Closed.step4C1,
  `Zeta23.OPICARound20.Closed.literalC1,
  `Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity]

def mathematicalRootNames : Array Name := #[
  `riemannHypothesis,
  `riemannZeta_eq_zero_re,
  `LFunction_ne_zero_of_half_lt_re,
  `LFunction_eq_zero_re,
  `LFunction_eq_zero_re_of_isPrimitive,
  `Zeta23.OPICARound19.ReceiverAudit.exactReceiver,
  `Zeta23.OPICARound19.ReceiverAudit.exactZeroErrorReceiver,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredC1_reflexive,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredC1_is_native,
  `Zeta23.OPICARound19.ClaimFingerprint.requiredRH_reflexive,
  `Zeta23.OPICARound20.even_zero_bound_of_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.c1_iff_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.riemannHypothesis_iff_all_boundary_flat_nonnegative,
  `Zeta23.OPICARound20.finite_negative_boundary_flat_witness_refutes_c1,
  `Zeta23.OPICARound20.Closed.step4C1,
  `Zeta23.OPICARound20.Closed.literalC1,
  `Zeta23.OPICARound20.Closed.fullBoundaryFlatPositivity]

def closedDeclarations : Array Declaration :=
  (closedNames.zip (closedTypeNames.zip closedValues)).map fun (name, typeName, value) =>
    .thmDecl {name, levelParams := [], type := mkConst typeName, value}

def emit (s : String) : IO Unit := do
  let out ← IO.getStdout
  out.putStrLn s
  out.flush

def fail (s : String) : IO α := throw (IO.userError s)

def requireAbsent (env : Environment) (names : Array Name) : IO Unit := do
  for n in names do
    if env.toKernelEnv.find? n |>.isSome then
      fail s!"Forbidden preexisting theorem name: {n}"

def importExact (imports : Array Import) : IO Environment := do
  emit s!"OPICA21_PHASE IMPORT_BEGIN {imports.map (·.module)}"
  let env ← importModules imports {} (trustLevel := 0) (loadExts := false)
    (leakEnv := true) (level := .private)
  if env.header.isModule || env.header.imports != imports || env.header.trustLevel != 0 then
    fail "Imported environment header mismatch"
  emit s!"OPICA21_PHASE IMPORT_END modules={env.allImportedModuleNames.size}"
  return env

def addChecked (env : Environment) (decl : Declaration) : IO Environment := do
  emit s!"OPICA21_PHASE KERNEL_ADD_BEGIN {decl.getTopLevelNames}"
  match env.addDeclCore 0 0 decl none (doCheck := true) with
  | .ok result =>
    emit s!"OPICA21_PHASE KERNEL_ADD_END {decl.getTopLevelNames}"
    return result
  | .error _ => fail s!"Stock kernel rejected declaration {decl.getTopLevelNames}"

def requireNoSidecars (path : System.FilePath) : IO Unit := do
  for side in #[OLeanLevel.server.adjustFileName path, OLeanLevel.private.adjustFileName path,
      path.withExtension "ir", path.withExtension "ir.sig"] do
    if ← side.pathExists then fail s!"Unexpected authored module sidecar: {side}"

def requireOrdinaryData (data : ModuleData) (imports : Array Import)
    (expected : Array Declaration) : IO Unit := do
  if data.isModule || data.imports != imports then fail "Ordinary module import header mismatch"
  if !data.entries.isEmpty || !data.extraConstNames.isEmpty then
    fail "Unexpected authored extension entries or extra constant names"
  if data.constants.size != expected.size || data.constNames != data.constants.map (·.name) then
    fail "Wrong authored declaration count or name table"
  let mut found : NameHashSet := {}
  for ci in data.constants do
    if found.contains ci.name then fail "Duplicate authored theorem name"
    found := found.insert ci.name
    let some decl := expected.find? (fun d => d.getTopLevelNames.contains ci.name)
      | fail s!"Unexpected authored constant: {ci.name}"
    match ci, decl with
    | .thmInfo actual, .thmDecl wanted =>
      if actual != wanted || !actual.levelParams.isEmpty ||
          actual.type.hasMVar || actual.type.hasFVar || actual.value.hasMVar || actual.value.hasFVar then
        fail s!"Authored theorem type/value/kind mismatch: {ci.name}"
    | _, _ => fail "An authored entry is not an ordinary safe theorem"

def writeChecked (env : Environment) (moduleName : Name) (imports : Array Import)
    (decls : Array Declaration) (path : System.FilePath) : IO Unit := do
  if ← path.pathExists then fail s!"Output object already exists: {path}"
  requireNoSidecars path
  emit s!"OPICA21_PHASE WRITE_BEGIN {moduleName}"
  -- Stock mkModuleData selects only the fresh stage2 kernel constants. Passing
  -- empty extension entries avoids all extension export callbacks, including a
  -- second full transitive axiom walk. These modules add only plain theorems.
  let data ← mkModuleData (env.setMainModule moduleName) .private
    (extEntries? := some (.uniform #[]))
  requireOrdinaryData data imports decls
  saveModuleData path moduleName data
  let (actual, _) ← readModuleData path
  requireOrdinaryData actual imports decls
  requireNoSidecars path
  emit s!"OPICA21_PHASE WRITE_END {moduleName} constants={actual.constants.size} entries=0 extraConstNames=0"

/-- All expression constants and projection type names, visiting shared DAG
nodes once. Metadata annotations have no logical dependencies. -/
def expressionDependencies (expressions : Array Expr) (initial : NameSet := {}) : NameSet := Id.run do
  let mut names := initial
  let mut pending := expressions
  let mut seen : Std.HashSet Expr := {}
  while !pending.isEmpty do
    let e := pending.back!
    pending := pending.pop
    if seen.contains e then continue
    seen := seen.insert e
    match e with
    | .const n _ => names := names.insert n
    | .proj n _ b => names := names.insert n; pending := pending.push b
    | .app f a => pending := pending.push f |>.push a
    | .lam _ t b _ | .forallE _ t b _ => pending := pending.push t |>.push b
    | .letE _ t v b _ => pending := pending.push t |>.push v |>.push b
    | .mdata _ b => pending := pending.push b
    | _ => pure ()
  return names

/-- `ConstantInfo.value? (allowOpaque := true)` is the pinned stock API used
by getUsedConstantsAsSet. Retain types, all available bodies, and additionally
the inductive/constructor/recursor metadata and every reduction-rule RHS. -/
def logicalDependencies (ci : ConstantInfo) : NameSet := Id.run do
  let mut expressions := #[ci.type]
  if let some value := ci.value? (allowOpaque := true) then
    expressions := expressions.push value
  let mut names : NameSet := {}
  match ci with
  | .inductInfo v =>
    for n in v.all ++ v.ctors do names := names.insert n
  | .ctorInfo v => names := names.insert v.induct
  | .recInfo v =>
    for n in v.all do names := names.insert n
    for rule in v.rules do
      names := names.insert rule.ctor
      expressions := expressions.push rule.rhs
  | _ => pure ()
  return expressionDependencies expressions names

/-- Actual raw logical dependency traversal. A bit per root computes exact
per-root axiom reachability without trusting serialized axiom extensions.
Missing constants, unsafe/partial logical dependencies, and nonstandard axioms
fail closed. The monotone worklist also handles inductive/constructor cycles.
This is an audit, not a proof checker; the full independent gate is retained. -/
def actualAxioms (env : Environment) (roots : Array Name) : IO (Array (Array Name)) := do
  let allowed := #[`propext, `Classical.choice, `Quot.sound]
  let kenv := env.toKernelEnv
  let mut reach : Std.HashMap Name (Nat × Nat) := {}
  let mut todo : Array Name := #[]
  -- Descendants precede ancestors for the actual four audit roots, so the
  -- supplier is usually traversed once with every relevant root bit.
  for k in [:roots.size] do
    let i := roots.size - 1 - k
    let n := roots[i]!
    let mask := 2 ^ i
    let old := reach[n]?.getD (0, 0)
    reach := reach.insert n (Nat.lor old.1 mask, old.2)
    if old.1 == old.2 then todo := todo.push n
  let mut axMasks : Std.HashMap Name Nat := {}
  let mut cursor := 0
  while cursor < todo.size do
    let n := todo[cursor]!
    cursor := cursor + 1
    let (seen, done) := reach[n]!
    let bits := Nat.xor seen done
    if bits == 0 then continue
    reach := reach.insert n (seen, seen)
    let some ci := kenv.find? n | fail s!"Unresolved logical dependency: {n}"
    if ci.isUnsafe || ci.isPartial then fail s!"Unsafe or partial logical dependency: {n}"
    if ci.isAxiom then
      if !allowed.contains n then fail s!"Forbidden transitive axiom: {n}"
      axMasks := axMasks.insert n (Nat.lor (axMasks[n]?.getD 0) bits)
    for dep in logicalDependencies ci do
      let old := reach[dep]?.getD (0, 0)
      let joined := Nat.lor old.1 bits
      if joined != old.1 then
        reach := reach.insert dep (joined, old.2)
        if old.1 == old.2 then todo := todo.push dep
    if cursor % 50000 == 0 then
      emit s!"OPICA21_PHASE AXIOM_PROGRESS work={cursor} queued={todo.size} constants={reach.size}"
  emit s!"OPICA21_PHASE AXIOM_CLOSURE_END work={cursor} constants={reach.size}"
  return roots.mapIdx fun i _ =>
    allowed.filter fun n => Nat.land (axMasks[n]?.getD 0) (2 ^ i) != 0

def auditActualTargets (env : Environment) : IO Unit := do
  let roots := #[`riemannHypothesis] ++ closedNames
  let expected := #[`RiemannHypothesis] ++ closedTypeNames
  for n in roots, ty in expected do
    let some (.thmInfo ci) := env.toKernelEnv.find? n | fail s!"Target is not a safe theorem: {n}"
    if !ci.levelParams.isEmpty || ci.type != mkConst ty ||
        ci.type.hasMVar || ci.type.hasFVar || ci.value.hasMVar || ci.value.hasFVar then
      fail s!"Wrong closed target type: {n}"
    emit s!"OPICA19_TYPE_BEGIN {n}"
    emit s!"{n} : {ty}"
    emit s!"OPICA19_TYPE_END {n}"
    emit s!"OPICA21_PHASE AXIOM_COLLECTION_BEGIN {n}"
  let axiomSets ← actualAxioms env roots
  for n in roots, axioms in axiomSets do
    emit s!"'{n}' depends on axioms: [{String.intercalate ", " (axioms.toList.map toString)}]"
    emit s!"OPICA21_PHASE AXIOM_COLLECTION_END {n}"

/-- Check that every requested independent-checker root is actually present and
eligible for checking. Mathematical roots must be ordinary safe theorems;
primitive, inductive, constructor, quotient and allowed axiom roots keep their
legitimate kinds. No additional transitive walk is performed here. -/
def requireSelectedRootInventory (env : Environment) (roots mathematical : Array Name)
    (emitMarkers : Bool := true) : IO Unit := do
  if !(mathematical.all roots.contains) then fail "A mathematical root is absent from the inventory"
  let mut seen : NameHashSet := {}
  for n in roots do
    if seen.contains n then fail s!"Duplicate selected root: {n}"
    seen := seen.insert n
    let some ci := env.toKernelEnv.find? n | fail s!"Missing selected root: {n}"
    if ci.isUnsafe || ci.isPartial then fail s!"Unsafe or partial selected root: {n}"
    if mathematical.contains n then
      match ci with
      | .thmInfo _ => pure ()
      | _ => fail s!"Mathematical selected root is not a theorem: {n}"
    if emitMarkers then emit s!"OPICA21_SAFE_SELECTED_ROOT {n}"

def runGuard (path : System.FilePath) : IO Unit := do
  let env ← importExact guardImports
  requireAbsent env closedNames
  writeChecked env guardModule guardImports #[] path
  emit "OPICA20_NEW_NAMES_ABSENT"

def runClosed (path : System.FilePath) : IO Unit := do
  let guardPath ← findOLean guardModule
  requireNoSidecars guardPath
  let (guardData, _) ← readModuleData guardPath
  requireOrdinaryData guardData guardImports #[]
  -- Re-import the serialized guard as an actual ordinary module. No imported
  -- environment is fabricated and no header is retargeted after construction.
  let mut env ← importExact closedImports
  requireAbsent env closedNames
  for decl in closedDeclarations do env ← addChecked env decl
  writeChecked env closedModule closedImports closedDeclarations path
  if selectedRootNames.size != 50 || mathematicalRootNames.size != 17 then
    fail "Selected root inventory cardinality mismatch"
  requireSelectedRootInventory env selectedRootNames mathematicalRootNames
  -- writeChecked has reread the serialized object and compared every complete
  -- TheoremVal to the same checked AST before this actual dependency audit.
  auditActualTargets env
  emit "OPICA21_KERNEL_CLOSED_OBJECT_PASS"

def runControls : IO Unit := do
  let env ← importExact initImports
  -- Exercise the production writer and actual guard re-import using only core
  -- True theorems. These are unrelated fixture names, never closed C1 claims.
  IO.FS.withTempDir fun dir => do
    let controlGuard := `KernelBridgeControlGuard
    let controlClosed := `KernelBridgeControlClosed
    writeChecked env controlGuard initImports #[] (dir / "KernelBridgeControlGuard.olean")
    let originalPath ← searchPathRef.get
    searchPathRef.set (dir :: originalPath)
    try
      let imports := initImports ++ #[{module := controlGuard}]
      let mut imported ← importExact imports
      let names := #[`KernelBridgeControl.first, `KernelBridgeControl.alias, `KernelBridgeControl.iff]
      let p := mkConst `True
      let values := #[mkConst `True.intro, mkConst names[0]!,
        mkApp4 (mkConst `Iff.mp) p p (mkApp (mkConst `Iff.rfl) p) (mkConst names[0]!)]
      let declarations := (names.zip values).map fun (name, value) =>
        Declaration.thmDecl {name, levelParams := [], type := p, value}
      for declaration in declarations do imported ← addChecked imported declaration
      writeChecked imported controlClosed imports declarations (dir / "KernelBridgeControlClosed.olean")
      let axioms ← actualAxioms imported names
      if axioms != #[#[], #[], #[]] then fail "Core writer fixture axiom audit mismatch"
      let checker := (← findSysroot) / "bin" / "leanchecker"
      let child ← IO.Process.output {
        cmd := checker.toString
        args := #["--verbose", controlClosed.toString]
        env := #[("LEAN_PATH", some (String.intercalate ":" ((dir :: originalPath).map toString)))]}
      emit "OPICA21_CONTROL_STOCK_STDOUT_BEGIN"
      emit child.stdout
      emit "OPICA21_CONTROL_STOCK_STDOUT_END"
      emit "OPICA21_CONTROL_STOCK_STDERR_BEGIN"
      emit child.stderr
      emit "OPICA21_CONTROL_STOCK_STDERR_END"
      if child.exitCode != 0 then fail s!"Stock replay of writer fixture failed: {child.stderr}"
      -- Pinned stock verbose mode exposes module names, not individual
      -- declaration names. Exact theorem names/types/values were reread above.
      if ((child.stdout.splitOn "\n").filter
          (· == s!"replaying {controlClosed}")).length != 1 then
        fail "Missing or duplicated exact stock replay module line"
      emit "EMPTY_GUARD_AND_THREE_THEOREM_OBJECTS_REPLAYED"
    finally
      searchPathRef.set originalPath
  let safeName := `KernelBridge.Control.safe
  let safe : Declaration := .thmDecl {
    name := safeName, levelParams := [], type := mkConst `True, value := mkConst `True.intro}
  let env ← addChecked env safe
  let bad : Declaration := .thmDecl {
    name := `KernelBridge.Control.invalid, levelParams := [],
    type := mkConst `False, value := mkConst `True.intro}
  match env.addDeclCore 0 0 bad none (doCheck := true) with
  | .ok _ => fail "Invalid proof control unexpectedly accepted"
  | .error _ => emit "INVALID_PROOF_REJECTED"
  let duplicateRejected ← try requireAbsent env #[safeName]; pure false catch _ => pure true
  if !duplicateRejected then fail "Existing name control unexpectedly accepted"
  emit "EXISTING_NAME_REJECTED"
  let custom := `KernelBridge.Control.nonstandard
  let env ← addChecked env (.axiomDecl {
    name := custom, levelParams := [], type := mkConst `True, isUnsafe := false})
  let safeAxioms ← actualAxioms env #[safeName]
  if safeAxioms != #[#[]] then fail "Unreached axiom polluted safe root audit"
  let transitive := `KernelBridge.Control.transitive
  let opaqueName := `KernelBridge.Control.opaqueProof
  let env ← addChecked env (.opaqueDecl {
    name := opaqueName, levelParams := [], type := mkConst `True,
    value := mkConst custom, isUnsafe := false})
  let env ← addChecked env (.thmDecl {
    name := transitive, levelParams := [], type := mkConst `True, value := mkConst opaqueName})
  let axiomRejected ← try discard <| actualAxioms env #[transitive]; pure false
    catch e => pure ("Forbidden transitive axiom:".isPrefixOf e.toString ||
      (e.toString.splitOn "Forbidden transitive axiom:").length > 1)
  if !axiomRejected then fail "Transitive nonstandard axiom control did not reject correctly"
  emit "OPAQUE_TRANSITIVE_NONSTANDARD_AXIOM_REJECTED"
  let missingRejected ← try discard <| actualAxioms env #[`KernelBridge.Control.absent]; pure false
    catch e => pure ((e.toString.splitOn "Unresolved logical dependency:").length > 1)
  if !missingRejected then fail "Missing dependency control did not reject correctly"
  emit "UNRESOLVED_DEPENDENCY_REJECTED"
  requireSelectedRootInventory env #[safeName, `True, `Quot] #[safeName] false
  let wrongKindRejected ← try
      requireSelectedRootInventory env #[`True] #[`True] false; pure false
    catch e => pure ((e.toString.splitOn "Mathematical selected root is not a theorem:").length > 1)
  if !wrongKindRejected then fail "Wrong mathematical-root kind control failed"
  emit "NON_THEOREM_MATHEMATICAL_ROOT_REJECTED"
  let missingRootRejected ← try
      requireSelectedRootInventory env #[`KernelBridge.Control.absent] #[] false; pure false
    catch e => pure ((e.toString.splitOn "Missing selected root:").length > 1)
  if !missingRootRejected then fail "Missing selected-root control failed"
  emit "MISSING_SELECTED_ROOT_REJECTED"
  let duplicateRootRejected ← try
      requireSelectedRootInventory env #[safeName, safeName] #[safeName] false; pure false
    catch e => pure ((e.toString.splitOn "Duplicate selected root:").length > 1)
  if !duplicateRootRejected then fail "Duplicate selected-root control failed"
  emit "DUPLICATE_SELECTED_ROOT_REJECTED"
  let unsafeName := `KernelBridge.Control.unsafeSelected
  let env ← addChecked env (.defnDecl {
    name := unsafeName, levelParams := [], type := mkConst `True,
    value := mkConst `True.intro, hints := .abbrev, safety := .unsafe})
  let unsafeRejected ← try requireSelectedRootInventory env #[unsafeName] #[] false; pure false
    catch e => pure ((e.toString.splitOn "Unsafe or partial selected root:").length > 1)
  if !unsafeRejected then fail "Unsafe selected-root control failed"
  emit "UNSAFE_SELECTED_ROOT_REJECTED"
  let partialName := `KernelBridge.Control.partialSelected
  let env ← addChecked env (.defnDecl {
    name := partialName, levelParams := [], type := mkConst `True,
    value := mkConst `True.intro, hints := .abbrev, safety := .partial})
  let partialRejected ← try requireSelectedRootInventory env #[partialName] #[] false; pure false
    catch e => pure ((e.toString.splitOn "Unsafe or partial selected root:").length > 1)
  if !partialRejected then fail "Partial selected-root control failed"
  emit "PARTIAL_SELECTED_ROOT_REJECTED"
  emit "OPICA21_KERNEL_CONTROLS_PASS"

end KernelBridge

def main (args : List String) : IO UInt32 := do
  initSearchPath (← findSysroot)
  match args with
  | ["guard", path] => KernelBridge.runGuard path
  | ["closed", path] => KernelBridge.runClosed path
  | ["controls"] => KernelBridge.runControls
  | _ => throw (IO.userError "Usage: kernel_bridge guard OUTPUT.olean | closed OUTPUT.olean | controls")
  return 0
