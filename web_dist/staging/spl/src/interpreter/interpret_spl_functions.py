# interpret_spl_functionss.py
from typing import Dict, List, Tuple, Set, Callable
from spl.src.parser.parser import Init, Discard, AffineAssign, Skip, _names_of
from spl.src.relations.set_functions import SetFunction

# Interpret a classical function-chunk as a SetFunction F_p^n -> F_p^m
def interpret_function_chunk(p: int, chunk: List[object]):
    # 1) collect I/O interface for the chunk: inputs = free reads, outputs = last writes
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
            raise NotImplementedError("only classical statements allowed in function chunk")

    # Outputs = variables written in the chunk but not discarded
    # For a simple model, take all writes as outputs and all reads as inputs.
    in_names: List[str] = sorted(list(reads - writes))
    # Keep output order by first-write in the chunk
    seen_out: List[str] = []
    for s in chunk:
        if isinstance(s, (Init, AffineAssign)):
            for n in _names_of(getattr(s, "reg", getattr(s, "dst", []))):
                if n not in seen_out:
                    seen_out.append(n)
    out_names: List[str] = seen_out

    # 2) build evaluator over F_p
    def make_f(in_order: List[str], out_order: List[str]):
        idx = {n:i for i,n in enumerate(in_order)}
        def getv(env: Dict[str,int], n: str) -> int:
            return env.get(n, 0)
        def f(x: List[int]) -> List[int]:
            env: Dict[str,int] = {}
            for n,i in idx.items():
                env[n] = x[i] % p
            for s in chunk:
                if isinstance(s, Init):
                    for n in _names_of(s.reg):
                        env[n] = 0
                elif isinstance(s, Discard):
                    for n in _names_of(s.reg):
                        env.pop(n, None)
                elif isinstance(s, AffineAssign):
                    dsts = _names_of(s.dst)
                    srcs = _names_of(s.src)
                    if s.transform == "copy":
                        assert len(dsts) == 2 and len(srcs) == 1
                        v = getv(env, srcs[0])
                        env[dsts[0]] = v % p
                        env[dsts[1]] = v % p
                    elif s.transform == "sum":
                        assert len(dsts) == 1 and len(srcs) >= 1
                        total = 0
                        for n in srcs: total += getv(env, n)
                        env[dsts[0]] = total % p
                    elif s.transform == "plusone":
                        assert len(dsts) == 1 and len(srcs) == 1
                        env[dsts[0]] = (getv(env, srcs[0]) + 1) % p
                    elif s.transform == "and":
                        # multiplication over F_p
                        assert len(dsts) == 1 and len(srcs) == 2
                        env[dsts[0]] = (getv(env, srcs[0]) * getv(env, srcs[1])) % p
                    else:
                        raise NotImplementedError(f"unknown transform {s.transform}")
                elif isinstance(s, Skip):
                    pass
                else:
                    raise NotImplementedError("non-classical stmt in function chunk")
            return [getv(env, n) for n in out_order]
        return f

    f = make_f(in_names, out_names)
    sf = SetFunction.from_callable(
        p, n=len(in_names), m=len(out_names), f=f,
        in_names={i:n for i,n in enumerate(in_names)},
        out_names={i:n for i,n in enumerate(out_names)},
    )
    return sf, in_names, out_names

# Convenience adapter returning a SetRelation using the graph
def interpret_function_chunk_as_relation(p: int, chunk: List[object]):
    sf, ins, outs = interpret_function_chunk(p, chunk)
    return sf.to_set_relation(), ins, outs
