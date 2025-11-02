
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Callable, Set

from spl.src.parser.parser import Program, Init, QInit, Discard, Meas, ApplyGate, AffineAssign, Ctrl, Skip, _names_of
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine
from spl.src.interpreter.interpret_spl_sets import interpret as interpret_sets
from spl.src.relations.set_relations import SetRelation
from spl.src.relations.affine_relations import AffineRelation

# ---------- helpers: classify and segment ----------

def _is_classical_stmt(s) -> bool:
    return isinstance(s, (Init, Discard, AffineAssign, Skip))

def _is_quantum_stmt(s) -> bool:
    return isinstance(s, (QInit, Meas, ApplyGate, Ctrl))

def _needs_sets_stmt(s) -> bool:
    # Non-Pauli ctrl
    if isinstance(s, Ctrl):
        g = (s.pauli or "").upper()
        return g not in {"X","Z"}
    return False

def _has_and_assign(s) -> bool:
    return isinstance(s, AffineAssign) and str(s.transform).strip().lower() == "and"

def _segment_program(stmts: List[object]) -> List[Tuple[str, List[object]]]:
    """Return list of (kind, chunk_stmts) where kind in {'FUNC','AFFINE','SETS'}.
       We form maximal classical chunks (FUNC), and maximal quantum chunks.
       Quantum chunks are marked 'AFFINE' unless they contain non-Pauli ctrl; then 'SETS'.
    """
    chunks: List[Tuple[str, List[object]]] = []
    cur_kind = None
    cur: List[object] = []

    def flush():
        nonlocal cur, cur_kind
        if cur:
            chunks.append((cur_kind, cur))
            cur = []
            cur_kind = None

    i = 0
    while i < len(stmts):
        s = stmts[i]
        if _is_classical_stmt(s):
            kind = "FUNC"
        elif _is_quantum_stmt(s):
            kind = "SETS" if _needs_sets_stmt(s) else "AFFINE"
        else:
            kind = "SETS"  # conservative default

        if cur_kind is None:
            cur_kind = kind; cur = [s]
        else:
            # merge classical with classical; merge quantum kinds if same label; else flush
            if (cur_kind == "FUNC" and kind == "FUNC") or (cur_kind in {"AFFINE","SETS"} and kind in {"AFFINE","SETS"} and (cur_kind == "SETS" or kind == "AFFINE" or cur_kind==kind)):
                # once SETS, keep as SETS
                if kind == "SETS": cur_kind = "SETS"
                cur.append(s)
            else:
                flush()
                cur_kind = kind; cur = [s]
        i += 1
    flush()
    return chunks

# function-chunk interpreter moved to interpret_spl_functions.py

# compatibility wrapper
def _mk_function_from_chunk(p: int, chunk: List[object]):
    return interpret_function_chunk(p, chunk)

# ---------- function-chunk interpreter ----------

def _chunk_has_and(stmts: List[object]) -> bool:
    for s in stmts:
        if isinstance(s, AffineAssign) and str(s.transform).strip().lower() == "and":
            return True
    return False


def _collect_vars_func_chunk(chunk: List[object]) -> Tuple[Set[str], Set[str]]:
    reads: Set[str] = set()
    writes: Set[str] = set()
    for s in chunk:
        if isinstance(s, Init):
            writes.update(_names_of(s.reg))
        elif isinstance(s, Discard):
            writes.update(_names_of(s.reg))
        elif isinstance(s, AffineAssign):
            writes.update(_names_of(s.dst))
            reads.update(_names_of(s.src))
        elif isinstance(s, Skip):
            pass
        else:
            raise NotImplementedError("non-classical stmt in function chunk")
    return reads, writes

def _mk_function_from_chunk(p: int, chunk: List[object]):
    """
    Build a SetRelation for a classical function chunk.
    """
    reads, writes = _collect_vars_func_chunk(chunk)
    in_names = sorted(list(reads - writes))
    out_names = sorted(list(writes))

    def make_f(in_order: List[str], out_order: List[str]):
        def getv(env: Dict[str,int], name: str) -> int:
            return env.get(name, 0) % p
        def f(xvec: List[int]) -> List[int]:
            env: Dict[str,int] = {}
            for i, name in enumerate(in_order):
                env[name] = xvec[i] % p
            for s in chunk:
                if isinstance(s, Init):
                    for n in _names_of(s.reg):
                        env[n] = 0
                elif isinstance(s, Discard):
                    for n in _names_of(s.reg):
                        if n in env:
                            del env[n]
                elif isinstance(s, AffineAssign):
                    op = str(s.transform).strip().lower()
                    dsts = _names_of(s.dst)
                    srcs = _names_of(s.src)
                    if op == "plusone":
                        assert len(dsts) == 1 and len(srcs) == 1
                        env[dsts[0]] = (getv(env, srcs[0]) + 1) % p
                    elif op == "sum":
                        total = 0
                        for n in srcs:
                            total = (total + getv(env, n)) % p
                        assert len(dsts) == 1
                        env[dsts[0]] = total % p
                    elif op == "copy":
                        assert len(srcs) == 1 and len(dsts) == 2
                        v = getv(env, srcs[0])
                        env[dsts[0]] = v
                        env[dsts[1]] = v
                    elif op == "and":
                        assert len(dsts) == 1 and len(srcs) == 2
                        env[dsts[0]] = (getv(env, srcs[0]) * getv(env, srcs[1])) % p
                    else:
                        total = 0
                        for n in srcs:
                            total = (total + getv(env, n)) % p
                        assert len(dsts) == 1
                        env[dsts[0]] = total % p
                elif isinstance(s, Skip):
                    pass
                else:
                    raise NotImplementedError("non-classical stmt in function chunk")
            return [getv(env, n) for n in out_order]
        return f

    f = make_f(in_names, out_names)
    rel = SetRelation.from_graph_function(
        p, len(in_names), len(out_names), f,
        in_names={i:n for i,n in enumerate(in_names)},
        out_names={i:n for i,n in enumerate(out_names)},
    )
    return rel, in_names, out_names

# ---------- affine-to-set cast ----------

def _affine_to_set(R: AffineRelation) -> SetRelation:
    p = R.p; n = R.n_in; m = R.n_out
    B = R.subspace.basis
    d = n + m
    r = len(B[0]) if B else 0
    cols = [[B[i][j] % p for i in range(d)] for j in range(r)] if r>0 else []
    shift = [v % p for v in R.subspace.shift]
    pairs = set()
    def all_vecs_r(p, r):
        if r == 0:
            yield []
            return
        from itertools import product
        for t in product(range(p), repeat=r):
            yield list(t)
    for t in all_vecs_r(p, r):
        vec = shift[:]
        for j in range(r):
            tj = t[j] % p
            if tj:
                for i in range(d):
                    vec[i] = (vec[i] + tj*cols[j][i]) % p
        x = tuple(vec[:n]); y = tuple(vec[n:])
        pairs.add((x,y))
    return SetRelation(p, n, m, pairs, dict(R.input_names), dict(R.output_names))

# ---------- interpreter (segmentation + casting + composition) ----------

def interpret(p: int, prog: Program, context: Optional[Dict[str, str]] = None):
    ctx = context if context is not None else getattr(prog, "context", None)
    # Normalize declared context to types for sub-interpreters
    declared_ctx = getattr(prog, "context", None) or {}
    def _norm_ty(ty: str) -> str:
        t0 = str(ty).strip().lower()
        if t0 in ("dit", "pit", "bit"):
            return "pit"
        if t0 in ("qdit", "qpit", "qudit", "qubit"):
            return "qpit"
        raise ValueError(f"unknown declared context type: {ty}")
    ctx_decl_order = list(declared_ctx.keys())
    fwd_context = {name: _norm_ty(declared_ctx[name]) for name in ctx_decl_order}
    chunks = _segment_program(prog.stmts)

    used = set()  # domains used

    composed: Optional[SetRelation] = None

    # track known input types from prior chunks
    known_ctx: Dict[str,str] = {}

    # If any chunk requires SETS, dispatch whole program to sets interpreter
    if any(k == 'SETS' for (k, _) in chunks):
        return interpret_sets(p, prog, context=fwd_context)
    # If both FUNC and AFFINE exist and any FUNC chunk contains 'and', do whole-program sets to keep interface alignment
    kinds = {k for (k,_) in chunks}
    if ('FUNC' in kinds and 'AFFINE' in kinds) and any((k=='FUNC') and _chunk_has_and(st) for (k,st) in chunks):
        return interpret_sets(p, prog, context=fwd_context)
    # Otherwise continue with possible chunked composition/minimization
    if any(k == 'SETS' for (k, _) in chunks):
        return interpret_sets(p, prog, context=fwd_context)
    if all(k != 'SETS' for (k, _) in chunks) and any(k == 'AFFINE' for (k,_) in chunks) and all((k!='FUNC') or (not _chunk_has_and(st)) for (k,st) in chunks):
        # prefer whole-program affine only when no classical 'and' appears
        return interpret_affine(p, prog, context=fwd_context)

    for kind, stmts in chunks:
        subprog = Program(stmts=stmts, context=ctx)
        if kind == "FUNC":
            Rset, in_names, out_names = _mk_function_from_chunk(p, stmts)
            for n in out_names:
                known_ctx.setdefault(n, 'pit')
            used.add("FUNC")
            cur = Rset
        elif kind == "AFFINE":
            _env, Raff = interpret_affine(p, subprog, context=known_ctx or ctx)
            used.add("AFFINE")
            cur = _affine_to_set(Raff)
        else:
            _env, Rset = interpret_sets(p, subprog, context=known_ctx or ctx)
            used.add("SETS")
            cur = Rset

        composed = cur if composed is None else composed.compose(cur)

    # Prefer set interpreter if any SETS features were used
    if "SETS" in used:
        return interpret_sets(p, prog, context=fwd_context)
    # Prefer affine when only func+affine used (and no 'and' needed in affine anyway)
    if used == {"AFFINE"} or (used.issubset({"FUNC","AFFINE"}) and not any(_has_and_assign(s) for s in prog.stmts)):
        return interpret_affine(p, prog, context=fwd_context)
    if used == {"FUNC"}:
        return interpret_sets(p, prog, context=fwd_context)
    return interpret_sets(p, prog, context=fwd_context)