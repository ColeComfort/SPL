from typing import Optional, Dict, List, Tuple
from spl.src.parser.parser import Program, Init, QInit, Discard, Meas, ApplyGate, AffineAssign, Ctrl
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine
from spl.src.interpreter.interpret_spl_sets import interpret as interpret_sets
from spl.src.dispatch.chunker import chunk_program, Chunk

PAULI_SET = {"X", "Z"}

def _is_nonpauli_ctrl(s: object) -> bool:
    if isinstance(s, Ctrl):
        g = str(getattr(s, "pauli", "")).strip().upper()
        return g not in PAULI_SET
    return False

def interpret(p: int, prog: Program, context: Optional[Dict[str, str]] = None):
    # Fast-fail on classical control over non-Pauli Clifford
    for s in prog.stmts:
        if _is_nonpauli_ctrl(s):
            raise TypeError("Classical control over non-Pauli Clifford not supported")

    # Normalize context shorthands to preexisting standard
    if context is not None:
        norm: Dict[str,str] = {}
        for k, v in context.items():
            if v in (1, "Dit", "dit", "pit"):
                norm[k] = "pit"
            elif v in (2, "Qdit", "qdit", "qpit"):
                norm[k] = "qpit"
            else:
                norm[k] = str(v)
        context = norm

    # Segment into chunks with live-in contexts
    chunks: List[Chunk] = chunk_program(prog)

    if not chunks:
        return interpret_sets(p, prog, context=context)

    kinds = {ch.kind for ch in chunks}

    # If any classical-affine assignment reads a quantum-typed var per provided context, use sets composition
    def _reads_quantum(ch: Chunk) -> bool:
        from spl.src.parser.parser import _names_of
        for s in ch.stmts:
            if isinstance(s, AffineAssign):
                t = str(getattr(s, "transform", "")).strip().lower()
                if t in {"sum", "copy", "plusone"} and context:
                    for n in _names_of(s.src):
                        ty = context.get(n, "").strip().lower() if isinstance(context.get(n, ""), str) else context.get(n, "")
                        if ty == "qpit":
                            return True
        return False

    if any(_reads_quantum(ch) for ch in chunks):
        composed_env = None
        composed_rel = None
        for ch in chunks:
            subprog = Program(stmts=ch.stmts, context=ch.live_in)
            env, rel = interpret_sets(p, subprog, context=ch.live_in)
            if composed_rel is None:
                composed_env, composed_rel = env, rel
            else:
                composed_rel = composed_rel.compose(rel)
        return composed_env, composed_rel

    # Pure affine
    if ("AFFINE" in kinds) and ("CLASSICAL" not in kinds):
        return interpret_affine(p, prog, context=context)
    # Pure classical
    if ("CLASSICAL" in kinds) and ("AFFINE" not in kinds):
        return interpret_sets(p, prog, context=context)

    # Mixed: compose per-chunk via sets
    composed_env = None
    composed_rel = None
    for ch in chunks:
        subprog = Program(stmts=ch.stmts, context=ch.live_in)
        env, rel = interpret_sets(p, subprog, context=ch.live_in)
        if composed_rel is None:
            composed_env, composed_rel = env, rel
        else:
            composed_rel = composed_rel.compose(rel)
    return composed_env, composed_rel

# Back-compat for tests expecting _segment_program
def _segment_program(stmts):
    from spl.src.parser.parser import Program, _names_of
    prog = Program(stmts=stmts, context=None)
    chunks = chunk_program(prog)
    mapped = []
    for ch in chunks:
        if ch.kind == "CLASSICAL":
            mapped.append(("FUNC", ch.stmts))
        else:
            # classify AFFINE chunks that are only classical-affine statements as FUNC for tests
            only_classical_aff = True
            for s in ch.stmts:
                if isinstance(s, (QInit, Meas, ApplyGate, Ctrl)):
                    only_classical_aff = False; break
                if isinstance(s, AffineAssign):
                    t = str(getattr(s, "transform", "")).strip().lower()
                    if t not in {"sum", "copy", "plusone"}:
                        only_classical_aff = False; break
                if not isinstance(s, (Init, Discard, AffineAssign)):
                    # Skip is also classical-affine but not imported here; treat unknowns as non-classical
                    pass
            mapped.append(("FUNC" if only_classical_aff else "AFFINE", ch.stmts))
    return mapped
