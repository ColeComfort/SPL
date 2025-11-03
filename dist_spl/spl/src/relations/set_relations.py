# set_relations.py
# Explicit relations R ⊆ (F_p^n_in) × (F_p^n_out) with brute-force composition.
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

def modp(a: int, p: int) -> int:
    return a % p

def vec_mod(v: List[int], p: int) -> List[int]:
    return [a % p for a in v]

def modality(headers: List[str]) -> str:
    ty, i = [], 0
    while i < len(headers):
        h = headers[i]
        if h.endswith(".x"):
            base = h[:-2]
            if i+1 < len(headers) and headers[i+1] == base + ".z":
                ty.append("Q(F_p^2)"); i += 2; continue
        ty.append("F_p"); i += 1
    return " ⊕ ".join(ty) if ty else "{*}"

@dataclass
class SetRelation:
    p: int
    n_in: int
    n_out: int
    pairs: Set[Tuple[Tuple[int, ...], Tuple[int, ...]]]  # {(x_tuple, y_tuple)}
    input_names: Dict[int, str]
    output_names: Dict[int, str]

    @staticmethod
    def identity(p: int, d: int, names: Optional[Dict[int, str]] = None) -> "SetRelation":
        pairs: Set[Tuple[Tuple[int,...], Tuple[int,...]]] = set()
        for x in _all_vecs(p, d):
            pairs.add((tuple(x), tuple(x)))
        nm = {j: (names.get(j, "") if names else "") for j in range(d)}
        return SetRelation(p, d, d, pairs, nm, nm)

    @staticmethod
    def from_graph_function(
        p: int, n: int, m: int,
        f,  # callable: List[int] -> List[int]
        in_names: Optional[Dict[int, str]] = None,
        out_names: Optional[Dict[int, str]] = None
    ) -> "SetRelation":
        pairs: Set[Tuple[Tuple[int,...], Tuple[int,...]]] = set()
        for x in _all_vecs(p, n):
            y = vec_mod(f(x[:]), p)
            pairs.add((tuple(x), tuple(y)))
        ins = {j: (in_names.get(j, "") if in_names else "") for j in range(n)}
        outs = {j: (out_names.get(j, "") if out_names else "") for j in range(m)}
        return SetRelation(p, n, m, pairs, ins, outs)

    @staticmethod
    def from_affine(R) -> "SetRelation":
        """
        Convert an AffineRelation to a SetRelation by enumeration.
        """
        return R.to_set_relation()

    def compose(self, other: "SetRelation") -> "SetRelation":
        assert self.p == other.p and self.n_out == other.n_in
        p = self.p
        n, m, ell = self.n_in, self.n_out, other.n_out
        # index other by its domain y
        idx: Dict[Tuple[int, ...], List[Tuple[int, ...]]] = defaultdict(list)
        for y, z in other._as_yz():
            idx[y].append(z)

        new_pairs: Set[Tuple[Tuple[int,...], Tuple[int,...]]] = set()
        for x, y in self._as_xy():
            zs = idx.get(y, [])
            for z in zs:
                new_pairs.add((x, z))
        return SetRelation(
            p, n, ell, new_pairs,
            {j: self.input_names.get(j, "") for j in range(n)},
            {j: other.output_names.get(j, "") for j in range(ell)}
        )

    # Helpers to view pairs with fixed shapes
    def _as_xy(self):
        for x, y in self.pairs:
            yield x, y

    def _as_yz(self):
        # treat current relation as (y,z) by reusing pairs (domain==y)
        for y, z in self.pairs:
            yield y, z

    # Pretty print with labels and types, show size and first few samples
    def __str__(self) -> str:
        p = self.p
        n, m = self.n_in, self.n_out
        in_headers  = [self.input_names.get(j, "") for j in range(n)]
        out_headers = [self.output_names.get(j, "") for j in range(m)]

        LEFT  = ", ".join(h if h else f"x{j}" for j, h in enumerate(in_headers))
        RIGHT = ", ".join(h if h else f"y{j}" for j, h in enumerate(out_headers))
        dom_ty = modality(in_headers)
        cod_ty = modality(out_headers)

        sz = len(self.pairs)
        samples = list(self.pairs)[:min(8, sz)]

        lines = [f"SetRelation over F_{p}: {n}->{m}",
                 f"Inputs:  [{LEFT}]",
                 f"Outputs: [{RIGHT}]",
                 f"Type: {dom_ty}  ->  {cod_ty}",
                 f"|R| = {sz}"]
        if samples:
            lines.append("Samples:")
            for (x, y) in samples:
                lx = " ".join(str(a % p) for a in x)
                ly = " ".join(str(b % p) for b in y)
                lines.append(f"  [{lx}] | [{ly}]")
        return "\n".join(lines)

def _all_vecs(p: int, d: int):
    if d == 0:
        yield []
        return
    # simple base-p counter
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

