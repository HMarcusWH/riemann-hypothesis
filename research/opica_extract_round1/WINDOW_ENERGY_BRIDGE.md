# Conditional window-to-energy reduction (DERIVED on paper; Lean OPEN)

Let (G) denote the exact centered all-prime-power ramp in the contract. Suppose
`OneSidedWindows G`: for every (1/2<\theta<1) there is a constant (C_\theta)
such that arbitrarily late **complete real** intervals ([Y,Y^{3/2}]) satisfy
(G(y)\le C_\theta y^\theta) for every point in the interval.

Fix \(\eta>0\), and set \(\epsilon=\min(\eta/12,1/4)>0\),
\(\theta=1/2+\epsilon\). Replace (C_\theta) by (A=\max(C_\theta,0)\).
On a complete window with (Y\ge2),

\[
\int_Y^{Y^{3/2}} \frac{[G(y)]_+^2}{y^2}\,dy
\le A^2\int_Y^{Y^{3/2}}y^{-1+2\epsilon}\,dy
\le \frac{A^2}{2\epsilon}Y^{3\epsilon}.
\]

Choose the lower horizon at least (2,Y_0), and sufficiently large that
(A^2/(2\epsilon)\le Y^{\eta-3\epsilon}) thereafter. This is possible since
(3\epsilon\le\eta/4<\eta). The original window assumption then selects a
(Y) above that horizon. Thus the native **literalGEnergy** subpower
conclusion follows, provided the exact source normalization is transported.
The integrand is integrable on each such compact interval: the ramp agrees
there with a finite sum of continuous truncated affine terms (the (n=0)
von Mangoldt coefficient is zero), and the denominator stays positive.

This proves a conditional implication, not an actual arithmetic supplier.
It does not prove the large-prime-deficit estimate or its converse; it also
does not prove the direct energy-to-C1 detector transfer. Formalize the
integrability and rpow integral estimate in the native pin before accepting
this bridge. This is a narrower adapter than deriving RH via localized
Landau and then using RH-to-C1. Quantifier control, sign, full window width,
prime powers and normalization are essential.
