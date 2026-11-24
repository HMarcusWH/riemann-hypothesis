import OPICAR2PrincipalShape
import Development.AutomorphicArithmetic.ThetaCorrespondence.FockModels.EveryCharacterE

/-! The published component assembly in everyE₂ before plugAll.
Every mathematical input is retained; no zero exclusion consumer is used. -/
noncomputable section
open Formalism.BasicNotions Formalism.MainNotions Formalism.HC GlobalTheory.EX GlobalTheory.EX.OB
open GlobalTheory.Mem GlobalTheory.Mem.Top GlobalTheory.Mem.Top.Bl GlobalTheory.Fc
open GlobalTheory.Mem.LiteralAutomorphy UpperTheory.Top
namespace OPICAR2Original

theorem topG_of_literature_components
    (P : S0.HypothesesUE) (F : GlobalTheory.FunPr.Hypotheses₂)
    (hA : GlobalTheory.IndefiniteRowSideFullHecke.WeilTensorModels.ThetaIntegralsAgree)
    (hM : GlobalTheory.IndefiniteRowSideFullHecke.WeilTensorModels.LocalMatching)
    (hX : GlobalTheory.CovTop.CovolX) (hL : GlobalTheory.Published.LocalLanglandsGL) :
    TopG :=
  topG_of_green_hyps (GlobalTheory.GreenBridge.green_of_regular P.greenRegularCharacters)
    (UpperTheory.Lit.hypsE₂ P F hA hM hX hL fun cDep =>
      UpperTheory.N.boundAtTwoThree_at_prm_of_prints P.nLink (prm1 hL cDep))

end OPICAR2Original
