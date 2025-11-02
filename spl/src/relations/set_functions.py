# set_functions.py
# Total functions F_p^n -> F_p^m with composition and graph conversion.
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple, Optional, Iterable
from collections import defaultdict

def _modp(a: int, p: int) -> int:
    return a % p

def _vec_mod(v: List[int], p: int) -> List[int]:
    return [a % p for a in v]

def _all_vecs(p: int, d: int) -> Iterable[List[int]]:
    if d == 0:
        yield []
        return
    x = [0]*d
    while True:
        yield x[:]
        i = d-1
        while i >= 0 and x[i] == p-1:
            x[i] = 0
            i -= 1
        if i < 0:
            break
        x[i] += 1

@dataclass(frozen=True)
class SetFunction:
    p: int
    n_in: int
    n_out: int
    # Functional semantics provided either by a callable or by a dense table.
    # Exactly one of f or table must be not None.
    f: Optional[Callable[[List[int]], List[int]]] = None
    table: Optional[Tuple[Tuple[int, ...], ...]] = None  # length p^n of m-tuples
    input_names: Optional[Dict[int, str]] = None
    output_names: Optional[Dict[int, str]] = None

    def __post_init__(self):
        if (self.f is None) == (self.table is None):
            raise ValueError("Provide exactly one of f or table")
        if self.p <= 1:
            raise ValueError("p must be prime power >= 2 for F_p arithmetic")
        if self.n_in < 0 or self.n_out < 0:
            raise ValueError("arities must be nonnegative")

    # ---------- evaluation ----------
    def eval(self, x: List[int]) -> List[int]:
        if len(x) != self.n_in:
            raise ValueError("input length mismatch")
        if self.f is not None:
            return _vec_mod(self.f(list(x)), self.p)
        # table case: decode base-p index
        idx = 0
        for a in x:
            if a < 0 or a >= self.p:
                raise ValueError("input not in F_p")
            idx = idx*self.p + a
        return list(self.table[idx])

    # ---------- composition ----------
    def compose(self, g: "SetFunction") -> "SetFunction":
        # self: n->m, g: m->ℓ, return g∘self: n->ℓ
        if self.p != g.p or self.n_out != g.n_in:
            raise ValueError("arity or field mismatch in composition")
        p = self.p
        n, m, ell = self.n_in, self.n_out, g.n_out
        # Build dense table for robustness
        table: List[Tuple[int, ...]] = []
        for x in _all_vecs(p, n):
            y = self.eval(x)
            z = g.eval(y)
            table.append(tuple(_vec_mod(z, p)))
        return SetFunction(
            p=p, n_in=n, n_out=ell,
            f=None,
            table=tuple(table),
            input_names=self.input_names,
            output_names=g.output_names
        )

    # ---------- constructors ----------
    @staticmethod
    def from_callable(p: int, n: int, m: int, f: Callable[[List[int]], List[int]],
                      in_names: Optional[Dict[int,str]]=None,
                      out_names: Optional[Dict[int,str]]=None) -> "SetFunction":
        return SetFunction(p=p, n_in=n, n_out=m, f=f, table=None,
                           input_names=in_names, output_names=out_names)

    @staticmethod
    def identity(p: int, n: int, names: Optional[Dict[int,str]]=None) -> "SetFunction":
        def f(x: List[int]) -> List[int]:
            return _vec_mod(x, p)
        return SetFunction.from_callable(p, n, n, f, in_names=names, out_names=names)

    # ---------- adapters ----------
    def to_set_relation(self):
        # Late import to avoid cycle
        from .set_relations import SetRelation
        pairs = set()
        for x in _all_vecs(self.p, self.n_in):
            y = tuple(self.eval(x))
            pairs.add((tuple(x), y))
        ins  = {i: (self.input_names.get(i, "") if self.input_names else "") for i in range(self.n_in)}
        outs = {i: (self.output_names.get(i, "") if self.output_names else "") for i in range(self.n_out)}
        return SetRelation(self.p, self.n_in, self.n_out, pairs, ins, outs)

    # ---------- presentation ----------
    def __str.label__(self, names: Optional[Dict[int,str]], n: int) -> str:
        return "(" + ", ".join(names.get(i, "") if names else "" for i in range(n)) + ")"

    def __str__(self) -> str:
        inode = self.__str.label__(self.input_names, self.n_in)
        onode = self.__str.label__(self.output_names, self.n_out)
        return f"SetFunction F_{self.p}^{self.n_in} -> F_{self.p}^{self.n_out} {inode} -> {onode}"
