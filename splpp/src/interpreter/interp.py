from typing import *
from ..parser.ast import *
from ..compiler.compiler import *
from ..compiler.compiler import _affine_compare
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl_affine import interpret as spl_interpret

def parse_spl(text: str):
    return spl_parser.parse_spl(text) if hasattr(spl_parser, "parse_spl") else spl_parser.parse(text)


def functions_by_name(prog: Program) -> Dict[str, FnDecl]:
    return {d.name: d for d in prog.decls}


def run_assertions_via_spl(prog: Program) -> List[str]:
    dim = prog.dim or 2
    fns: Dict[str, FnDecl] = functions_by_name(prog)
    comp = Compiler(dim, fns=fns)
    if "main" not in fns:
        raise ValueError("entry point fn main() is required")

    reports: List[str] = []
    for s in fns["main"].body:
        if isinstance(s, AssertRel):
            if s.f1 not in fns or s.f2 not in fns:
                raise NameError(f"assert references unknown function(s): {s.f1}, {s.f2}")
            f = fns[s.f1]; g = fns[s.f2]
            spl_f = comp.compile_function_to_spl(f)
            spl_g = comp.compile_function_to_spl(g)
            Pf = parse_spl(spl_f); Pg = parse_spl(spl_g)
            _envf, Rf = spl_interpret(dim, Pf, context=(Pf.context or {}))
            _envg, Rg = spl_interpret(dim, Pg, context=(Pg.context or {}))
            if hasattr(Rf, "pairs"):
                ok = (Rf.pairs == Rg.pairs and Rf.n_in == Rg.n_in and Rf.n_out == Rg.n_out and Rf.p == Rg.p) \
                     if s.relop == "equal" else Rf.pairs.issubset(Rg.pairs)
            else:
                ok = _affine_compare(Rf, Rg, subset=(s.relop == "included"))
            reports.append(f"[ASSERT {s.relop} {s.f1} {s.f2}] {'OK' if ok else 'FAIL'}")
        elif isinstance(s, PrintSPL):
            pass
    return reports


