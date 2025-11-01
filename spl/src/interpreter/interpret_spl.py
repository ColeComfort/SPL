# interpret_spl.py
from typing import Optional, Dict
from spl.src.parser.parser import Program, AffineAssign
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine
from spl.src.interpreter.interpret_spl_sets import interpret_sets

def interpret(p: int, prog: Program, context: Optional[Dict[str, str]] = None):
    # If any AffineAssign uses 'mul' (case-insensitive), switch to set semantics.
    needs_sets = any(
        isinstance(s, AffineAssign) and str(s.transform).strip().lower() == "and"
        for s in prog.stmts
    )
    if needs_sets:
        return interpret_sets(p, prog, context)
    return interpret_affine(p, prog, context)

