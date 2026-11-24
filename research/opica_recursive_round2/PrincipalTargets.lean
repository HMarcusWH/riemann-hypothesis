import OPICAExtractionPrincipal
namespace OPICAR2Original
open Formalism.BasicNotions Formalism.MainNotions Formalism.HC GlobalTheory.EX UpperTheory.Top
def PrincipalConnectedNamed : Prop := OPICAExtractionR1.PrincipalConnected
def RampWindowsNamed : Prop := OPICAExtractionR1.RampWindows
def TopGNamed : Prop := TopG
def PrincipalHostNamed : Prop := HostExW (3 / 2 : ℝ) (GChi PChar.one).req
def PrincipalVWinNamed : Prop := VWinAt PChar.one 401
end OPICAR2Original
