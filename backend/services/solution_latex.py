"""A deliberately bounded solution-body dialect for in-app PDF compilation.

Full .tex export remains available. Do not treat TeX's file flags as a sandbox:
new TeX Live versions ignore openin_any. Reject programmable/file-access commands
before invoking the local compiler; only the application supplies the preamble.
"""

import re

COMMANDS = set(
    r"""
section subsection subsubsection paragraph textbf textit texttt textrm textsf emph
underline text normalfont small large Large tiny footnotesize scriptsize
begin end item label ref eqref pageref par noindent newline newpage clearpage
medskip smallskip bigskip quad qquad hfill vfill centering raggedright
frac dfrac tfrac binom dbinom tbinom sqrt overline overbrace underbrace
hat widehat tilde widetilde bar vec dot ddot acute grave breve check
mathbf mathit mathrm mathsf mathtt mathcal mathbb mathfrak boldsymbol
left right middle big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr Biggl Biggr
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
sum prod coprod int iint iiint oint lim limsup liminf sup inf max min
sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh log ln exp det dim ker
hom arg deg gcd Pr operatorname underset overset stackrel substack
forall exists nexists neg land lor wedge vee bigwedge bigvee implies iff
Rightarrow Leftarrow Leftrightarrow rightarrow leftarrow leftrightarrow mapsto
to gets longrightarrow longleftarrow longleftrightarrow Longrightarrow Longleftrightarrow
uparrow downarrow Uparrow Downarrow hookrightarrow leadsto
in notin ni subset subseteq supset supseteq subsetneq supsetneq
cup cap bigcup bigcap setminus emptyset varnothing complement
le leq ge geq neq ne equiv approx sim simeq cong propto asymp ll gg
infty partial nabla times cdot circ bullet ast star pm mp div otimes oplus
cdots ldots vdots ddots dots ell hbar imath jmath Re Im aleph
langle rangle lceil rceil lfloor rfloor lvert rvert lVert rVert vert Vert
lbrace rbrace backslash mid nmid parallel perp top bot angle triangle square
checkmark therefore because not colon prime restriction
textbackslash textasciitilde textasciicircum TeX LaTeX
underleftarrow underrightarrow overleftarrow overrightarrow
nonumber notag tag displaystyle textstyle scriptstyle scriptscriptstyle
hspace vspace rule phantom hphantom vphantom boxed fbox mbox
qed qedhere
""".split()
)
ENVIRONMENTS = set(
    "enumerate itemize description equation equation* align align* aligned alignat alignat* alignedat gather gather* gathered split multline multline* cases matrix pmatrix bmatrix Bmatrix vmatrix Vmatrix smallmatrix array tabular center flushleft quote quotation proof".split()
)
SYMBOLS = set("\\%$&#_{} ,;:!()[]|'\"`~^=. /")


def validate_solution(source):
    if "^^" in source or any(
        ord(char) < 32 and char not in "\n\r\t" for char in source
    ):
        raise ValueError("LATEX_UNSUPPORTED_COMMAND")
    # Retain comments in the compiler input, but do not let them split environment names.
    for match in re.finditer(r"\\([A-Za-z@]+|[^A-Za-z@])", source):
        command = match[1]
        if command not in COMMANDS and not (len(command) == 1 and command in SYMBOLS):
            raise ValueError("LATEX_UNSUPPORTED_COMMAND")
        if command in {"begin", "end"}:
            environment = re.match(r"\s*\{([A-Za-z*]+)\}", source[match.end() :])
            if not environment or environment[1] not in ENVIRONMENTS:
                raise ValueError("LATEX_UNSUPPORTED_ENVIRONMENT")
