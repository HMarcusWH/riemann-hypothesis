import Comparator.Compare

/-!
Comparison-only test harness around the unmodified upstream Comparator API.
This is not a kernel replay and does not prove either C1 or RH.
The full portable gate separately requires official Comparator and its kernels.
-/

private def primitiveTargets : Array Lean.Name := #[
  ``Nat.add, ``Nat.sub, ``Nat.mul, ``Nat.pow, ``Nat.gcd, ``Nat.div, ``Nat.mod,
  ``Nat.beq, ``Nat.ble, ``Nat.land, ``Nat.lor, ``Nat.xor, ``Nat.shiftLeft,
  ``Nat.shiftRight, ``String.ofList, ``Char.ofNat, ``List, ``eagerReduce,
  ``Nat, ``String, ``String.mk, ``Char, ``optParam, ``autoParam,
  ``semiOutParam, ``outParam
]

def main (args : List String) : IO UInt32 := do
  let challengePath :: solutionPath :: names := args
    | throw <| IO.userError "Usage: CompareExports CHALLENGE SOLUTION THEOREM..."
  let (targetNames, closedSuffix) := names.span (· != "--closed")
  let closedNames := closedSuffix.drop 1
  if targetNames.isEmpty then
    throw <| IO.userError "At least one ordinary theorem target is required"
  let challengeHandle ← IO.FS.Handle.mk challengePath .read
  let solutionHandle ← IO.FS.Handle.mk solutionPath .read
  let challenge ← Export.parseStream (IO.FS.Stream.ofHandle challengeHandle)
  let solution ← Export.parseStream (IO.FS.Stream.ofHandle solutionHandle)
  let targets := targetNames.toArray.map fun name =>
    Lean.Syntax.decodeNameLit ("`" ++ name) |>.get!
  let closedTargets := closedNames.toArray.map fun name =>
    Lean.Syntax.decodeNameLit ("`" ++ name) |>.get!
  let legalAxioms := #[``propext, ``Quot.sound, ``Classical.choice]
  -- An empty definition-target list is essential: definitions must be compared
  -- recursively, not treated as open definition holes.
  IO.ofExcept <| Comparator.compareAt challenge solution (targets ++ legalAxioms)
    #[] primitiveTargets
  IO.ofExcept <| Comparator.checkAxioms solution (targets ++ closedTargets) #[] legalAxioms
  if !closedTargets.isEmpty then
    -- These are closed theorem types in the very same export that will be
    -- kernel checked, not promises inferred from the fingerprint theorems.
    let expected : Array (Lean.Name × Lean.Name) := #[
      (`Zeta23.OPICARound19.Audit.provedRequiredC1,
        `Zeta23.OPICARound19.ClaimFingerprint.requiredC1),
      (`Zeta23.OPICARound19.step4C1,
        `Zeta23.OPICARound4.ArithmeticFrontier.CofinalMomentSliceVanishingErrorBounds),
      (`UpperTheory.FinalTheorems.riemannHypothesis, `RiemannHypothesis),
      (`Zeta23.OPICARound19.Audit.nativeConsumerReachesMathlibRH, `RiemannHypothesis)
    ]
    for (name, expectedType) in expected do
      if !closedTargets.contains name then
        throw <| IO.userError s!"Required closed export target was not audited: {name}"
      let some (.thmInfo info) := solution.constMap[name]?
        | throw <| IO.userError s!"Required closed theorem is absent: {name}"
      if !info.levelParams.isEmpty || info.type != Lean.mkConst expectedType then
        throw <| IO.userError s!"Required closed theorem has a substituted type: {name}"
    IO.println s!"OPICA19_CLOSED_EXPORT_AXIOMS_PASS {closedTargets.size}"
  IO.println "OPICA19_DEFINITION_COMPARISON_PASS"
  IO.println "Compared complete statement dependencies; no kernel or C1 closure claim."
  return 0
