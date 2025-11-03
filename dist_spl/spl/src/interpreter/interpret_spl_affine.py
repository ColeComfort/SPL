from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from spl.src.parser.parser import Program, Init, QInit, Discard, Meas, ApplyGate, AffineAssign, Ctrl, Skip, parse_spl
from spl.src.relations.affine_relations import AffineRelation

# ---------- helpers: graphs of affine maps with names ----------

def graph_of_affine_map(
    p: int,
    n: int,
    m: int,
    L: List[List[int]],
    a: List[int],
    in_names: Optional[Dict[int, str]] = None,
    out_names: Optional[Dict[int, str]] = None,
) -> AffineRelation:
    """
    Graph of y = L x + a over F_p, as an affine relation n -> m.
    Ambient order: [x0..x_{n-1} | y0..y_{m-1} || shift].
    Names are passed through to AffineRelation for printing.
    """
    cols: List[List[int]] = []
    for i in range(n):
        e_x = [0]*n
        e_x[i] = 1
        Ly = [L[r][i] % p for r in range(m)]
        cols.append(e_x + Ly)
    basis = [[cols[j][i] for j in range(n)] for i in range(n+m)] if n > 0 else [[] for _ in range(n+m)]
    shift = [0]*n + [a_i % p for a_i in a]
    return AffineRelation.from_shift_basis(p, n, m, shift, basis, in_names, out_names)

def graph_identity(p: int, d: int, names: Optional[Dict[int, str]] = None) -> AffineRelation:
    L = [[0]*d for _ in range(d)]
    for i in range(d): L[i][i] = 1
    return graph_of_affine_map(p, d, d, L, [0]*d, names, names)

def embed_update_on_slice(
    p: int,
    d: int,
    idxs: List[int],
    Ls: List[List[int]],
    a: List[int],
    names: Optional[Dict[int, str]],
) -> AffineRelation:
    """
    Build a relation d->d that applies y[idxs] := Ls * y[idxs] + a,
    leaving other output coordinates unchanged. Names preserved.
    """
    L = [[0]*d for _ in range(d)]
    for i in range(d): L[i][i] = 1
    for rL, r in enumerate(idxs):
        for cL, c in enumerate(idxs):
            L[r][c] = Ls[rL][cL] % p
    aff = [0]*d
    for rL, r in enumerate(idxs):
        aff[r] = a[rL] % p
    return graph_of_affine_map(p, d, d, L, aff, names, names)

# ---------- environment and variable bookkeeping ----------

@dataclass
class VarInfo:
    kind: str          # 'q' or 'c'
    out_idxs: List[int]

class Env:
    """
    Maintains current affine relation: self.current : n_in -> coord_dim (outputs)
    Context fixes n_in and names the first outputs (identity threaded).
    All ops act on OUTPUTS only. Domain never changes.
    """
    def __init__(self, p: int, n_in_ctx: int, ctx_order: List[Tuple[str,int]]):
        self.p = p
        self.n_in = n_in_ctx
        self.coord_dim = n_in_ctx
        self.input_names: Dict[int, str] = {}
        self.output_names: Dict[int, str] = {}

        out_cursor = 0
        in_cursor = 0
        for name, width in ctx_order:
            if width == 1:
                self.input_names[in_cursor] = name
                self.output_names[out_cursor] = name
                in_cursor += 1; out_cursor += 1
            elif width == 2:
                self.input_names[in_cursor]     = f"{name}.x"
                self.input_names[in_cursor + 1] = f"{name}.z"
                self.output_names[out_cursor]     = f"{name}.x"
                self.output_names[out_cursor + 1] = f"{name}.z"
                in_cursor += 2; out_cursor += 2
            else:
                raise ValueError("width must be 1 (pit) or 2 (qpit)")

        self.current = graph_identity(p, n_in_ctx, names=self.input_names)
        self.vars: Dict[str, VarInfo] = {}

        oc = 0
        for name, width in ctx_order:
            if width == 1:
                self.vars[name] = VarInfo('c', [oc]); oc += 1
            else:
                self.vars[name] = VarInfo('q', [oc, oc+1]); oc += 2

    # -- append outputs (state preparation); domain unchanged --
    def _append_outputs(self, k: int, names: List[str]) -> List[int]:
        if k <= 0: return []
        if len(names) != k:
            raise ValueError("name arity mismatch")
        d = self.coord_dim
        L = [[0]*d for _ in range(d+k)]
        for i in range(d): L[i][i] = 1
        a = [0]*(d+k)
        in_names = self.current.input_names
        out_names = {j: self.current.output_names.get(j, "") for j in range(d)}
        for j, nm in enumerate(names):
            out_names[d + j] = nm
        R = graph_of_affine_map(self.p, d, d+k, L, a, in_names, out_names)
        self.current = self.current.compose(R)
        new_idxs = list(range(d, d+k))
        self.coord_dim = d + k
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
        return new_idxs

    # -- variable creation --
    def add_classical(self, name: str):
        if name in self.vars: raise ValueError(f"var exists: {name}")
        outs = self._append_outputs(1, [name])
        self.vars[name] = VarInfo('c', outs)

    def add_quantum(self, name: str):
        if name in self.vars: raise ValueError(f"var exists: {name}")
        outs = self._append_outputs(2, [f"{name}.x", f"{name}.z"])
        self.vars[name] = VarInfo('q', outs)

    # -- measurement: drop z-output, keep x-output as classical --
    def measure(self, name: str):
        if name not in self.vars: raise ValueError(f"measure: unknown {name}")
        v = self.vars[name]
        if v.kind != 'q': return
        keep = [v.out_idxs[0]]
        drop = [v.out_idxs[1]]
        self._drop_outputs(drop)
        kept_idx = keep[0]
        self.current.output_names[kept_idx] = name
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
        v.kind = 'c'
        v.out_idxs = [kept_idx]

    # -- discard: remove outputs (domain untouched) --
    def drop_var(self, name: str):
        if name not in self.vars: raise ValueError(f"unknown var {name}")
        v = self.vars[name]
        self._drop_outputs(v.out_idxs)
        del self.vars[name]

    def _drop_outputs(self, to_drop_out_idxs: List[int]):
        if not to_drop_out_idxs: return
        n_in, d = self.n_in, self.coord_dim
        drop_ambient = set(n_in + j for j in to_drop_out_idxs if 0 <= j < d)
        keep_rows = [i for i in range(n_in + d) if i not in drop_ambient]
        sub = self.current.subspace.project(keep_rows)
        n_out_new = len(keep_rows) - n_in

        old_to_new = {old: new for new, old in enumerate(keep_rows)}
        def renumber_out_name(j: int) -> Optional[Tuple[int,str]]:
            old = n_in + j
            if old not in old_to_new: return None
            j_new = old_to_new[old] - n_in
            nm = self.current.output_names.get(j, "")
            return (j_new, nm)

        new_out_names: Dict[int,str] = {}
        for j in range(self.coord_dim):
            rn = renumber_out_name(j)
            if rn is not None:
                j_new, nm = rn
                new_out_names[j_new] = nm

        self.current = AffineRelation.from_shift_basis(
            self.p, n_in, n_out_new, sub.shift, sub.basis,
            input_names=self.current.input_names,
            output_names=new_out_names
        )
        for w in self.vars.values():
            new_idxs = []
            for j in w.out_idxs:
                old = n_in + j
                if old in old_to_new:
                    new_idxs.append(old_to_new[old] - n_in)
            w.out_idxs = new_idxs
        self.coord_dim = n_out_new
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}

    # ---- helpers for gate parsing ----
    @staticmethod
    # Replace _split_gate_token in interpret_spl_affine.py

    @staticmethod
    def _split_gate_token(tok: str):
        """
        Accept:
          - Non-MUL:  BASE^k, BASE^{k}          -> repetition count k
          - MUL:      MUL_k,  MUL_{k}           -> parameter k
        Returns (BASE, int or None). BASE uppercased.
        """
        s = tok.strip()
        # superscript form
        if "^" in s:
            base, tail = s.split("^", 1)
            base_uc = base.strip().upper()
            tail = tail.strip()
            if tail.startswith("{") and tail.endswith("}"):
                tail = tail[1:-1].strip()
            try:
                k = int(tail, 10)
            except ValueError:
                return base_uc, None
            if base_uc == "MUL":
                # Enforce: MUL must use subscript, not superscript
                raise ValueError("MUL expects subscript parameter, e.g., MUL_3")
            return base_uc, k
        # subscript form
        if "_" in s:
            base, tail = s.split("_", 1)
            base_uc = base.strip().upper()
            tail = tail.strip()
            if tail.startswith("{") and tail.endswith("}"):
                tail = tail[1:-1].strip()
            try:
                k = int(tail, 10)
            except ValueError:
                return base_uc, None
            if base_uc != "MUL":
                # Enforce: only MUL may use subscript
                raise ValueError(f"{base_uc} expects superscript repetition, not subscript.")
            return base_uc, k
        return s.upper(), None


    # ---- quantum gates on OUTPUTS ----
    def apply_quantum_gate(self, gate: str, regs: List[str]):
        """
        Qudit Clifford + dilation:
          F:  (x,z) -> (z, -x)
          S:  (x,z) -> (x, x+z)
          T:  (x,z) -> (x - z, z)                # F S F^{-1}
          X:  x := x + 1
          Z:  z := z + 1
          CX(control,target): (x1,z1,x2,z2) -> (x1, z1, x1+x2, z2 - z1)
          MUL_k: (x,z) -> (k x, k^{-1} z)        # k in F_p^×
        Repetition: G_n repeats G n times, except MUL_k which treats the number as parameter k.
        """
        p = self.p
        d = self.coord_dim
        base, suffix = self._split_gate_token(gate)

        def ensure_quantum_1(name: str) -> Tuple[int,int]:
            if name not in self.vars: raise ValueError(f"unknown var '{name}'")
            v = self.vars[name]
            if v.kind != 'q': raise ValueError(f"{base} expects quantum var")
            return v.out_idxs[0], v.out_idxs[1]

        if base in ("X","Z","S","F","T"):
            if len(regs) != 1: raise ValueError(f"{base} arity")
            x, z = ensure_quantum_1(regs[0])

            # repetition count
            if suffix is None:
                rep = 1
            else:
                rep = suffix % (4 if base == "F" else p)

            if base == "X":
                # x := x + rep
                Ls = [[1,0],[0,1]]; a = [rep % p, 0]
                rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)

            elif base == "Z":
                Ls = [[1,0],[0,1]]; a = [0, rep % p]
                rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)

            elif base == "S":
                # S^k = [[1,0],[k,1]]
                k = rep % p
                Ls = [[1,0],[k,1]]; a = [0,0]
                rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)

            elif base == "T":
                # T^k where T = [[1,-1],[0,1]] => T^k = [[1,-k],[0,1]]
                k = rep % p
                Ls = [[1, (-k) % p],[0,1]]; a = [0,0]
                rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)

            else:  # F
                # F^0=I, F^1=[[0,1],[-1,0]], F^2=[[-1,0],[0,-1]], F^3=[[0,-1],[1,0]]
                r = rep % 4
                if r == 0:
                    Ls = [[1,0],[0,1]]
                elif r == 1:
                    Ls = [[0,1],[(-1) % p, 0]]
                elif r == 2:
                    Ls = [[(-1) % p,0],[0,(-1) % p]]
                else:  # r == 3
                    Ls = [[0, (-1) % p],[1,0]]
                a = [0,0]
                rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)

            self.current = self.current.compose(rel)
            self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
            return

        if base == "CX":
            if len(regs) != 2: raise ValueError("CX arity")
            n1, n2 = regs
            if n1 not in self.vars or n2 not in self.vars: raise ValueError("unknown var in CX")
            v1, v2 = self.vars[n1], self.vars[n2]
            if v1.kind != 'q' or v2.kind != 'q': raise ValueError("CX expects quantum variables")
            x1, z1 = v1.out_idxs
            x2, z2 = v2.out_idxs
            times = 1 if suffix is None else (suffix % p)
            # apply once with parameter 'times' folded
            idxs = [x1,z1,x2,z2]
            Ls = [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [times % p, 0, 1, 0],
                [0, (-times) % p, 0, 1],
            ]
            rel = embed_update_on_slice(p, d, idxs, Ls, [0,0,0,0], self.current.output_names)
            self.current = self.current.compose(rel)
            self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
            return

        if base == "MUL":
            # parameterized dilation: token must be like MUL_k
            if len(regs) != 1: raise ValueError("MUL_k arity")
            if suffix is None:
                raise ValueError("MUL_k requires a numeric parameter, e.g., MUL_3")
            k = suffix % p
            if k == 0 or (p > 0 and (k % p) == 0):
                raise ValueError("MUL_k requires k in F_p^×")
            # compute multiplicative inverse mod p
            try:
                kinv = pow(k, -1, p)
            except ValueError:
                raise ValueError("MUL_k requires gcd(k,p)=1")
            x, z = ensure_quantum_1(regs[0])
            Ls = [[k % p, 0],[0, kinv % p]]
            a = [0,0]
            rel = embed_update_on_slice(p, d, [x,z], Ls, a, self.current.output_names)
            self.current = self.current.compose(rel)
            self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
            return

        raise ValueError(f"unknown quantum gate '{gate}'")

    # ---- affine classical transforms on OUTPUTS (strict: no auto-allocation) ----
    def apply_classical(self, transform: str, dsts: List[str], srcs: List[str]):
        tr = transform.strip().lower()

        def get_c_out(name: str) -> int:
            if name not in self.vars:
                raise ValueError(f"unknown var '{name}'")
            v = self.vars[name]
            if v.kind != 'c' or len(v.out_idxs) != 1:
                raise ValueError(f"variable '{name}' is not a classical 1-wire")
            return v.out_idxs[0]

        d = self.coord_dim
        L = [[0]*d for _ in range(d)]
        for i in range(d): L[i][i] = 1
        a = [0]*d

        if tr == "copy":
            if len(srcs) != 1 or len(dsts) != 2:
                raise ValueError("copy expects 1 source and 2 destinations")
            s = get_c_out(srcs[0])
            u = get_c_out(dsts[0])
            v = get_c_out(dsts[1])
            for j in range(d): L[u][j] = 0
            for j in range(d): L[v][j] = 0
            L[u][s] = 1; L[v][s] = 1

        elif tr == "sum":
            if len(srcs) != 2 or len(dsts) != 1:
                raise ValueError("sum expects 2 sources and 1 destination")
            s1 = get_c_out(srcs[0])
            s2 = get_c_out(srcs[1])
            y  = get_c_out(dsts[0])
            for j in range(d): L[y][j] = 0
            L[y][s1] = (L[y][s1] + 1) % self.p
            L[y][s2] = (L[y][s2] + 1) % self.p

        elif tr == "plusone":
            if len(srcs) != 1 or len(dsts) != 1 or srcs[0] != dsts[0]:
                raise ValueError("plusone expects one classical var in-place")
            x = get_c_out(srcs[0])
            a[x] = (a[x] + 1) % self.p

        elif tr == "and":
            # not supported in affine model; keep strict affine only
            raise ValueError("and: non-affine classical op not supported in affine interpreter")

        else:
            raise ValueError(f"unknown classical transform '{transform}'")

        rel = graph_of_affine_map(self.p, d, d, L, a, self.current.output_names, self.current.output_names)
        self.current = self.current.compose(rel)
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}

    # ---- classically controlled Pauli on a quantum OUTPUT (domain fixed) ----
    def apply_ctrl(self, gate: str, c_name: str, q_name: str):
        gate = gate.upper()
        if c_name not in self.vars or q_name not in self.vars:
            raise ValueError("ctrl: unknown vars")
        c = self.vars[c_name]; q = self.vars[q_name]
        if c.kind != 'c' or q.kind != 'q':
            raise ValueError("ctrl expects classical control and quantum target")
        c_idx = c.out_idxs[0]
        x_idx, z_idx = q.out_idxs
        d = self.coord_dim
        L = [[0]*d for _ in range(d)]
        for i in range(d): L[i][i] = 1
        a = [0]*d
        if gate in ("X","CTRLX"):
            L[x_idx][c_idx] = (L[x_idx][c_idx] + 1) % self.p
        elif gate in ("Z","CTRLZ"):
            L[z_idx][c_idx] = (L[z_idx][c_idx] + 1) % self.p
        else:
            raise ValueError(f"unknown controlled Pauli '{gate}'")
        rel = graph_of_affine_map(self.p, d, d, L, a, self.current.output_names, self.current.output_names)
        self.current = self.current.compose(rel)
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}

# ---------- interpreter ----------

def interpret(p: int, prog: Program, context: Optional[Dict[str, str]] = None):
    ctx = context if context is not None else getattr(prog, "context", None)
    n_in = 0
    ctx_order: List[Tuple[str,int]] = []
    if ctx:
        for name in sorted(ctx.keys()):
            ty = str(ctx[name]).strip().lower()
            if ty == "pit":
                ctx_order.append((name, 1)); n_in += 1
            elif ty == "qpit":
                ctx_order.append((name, 2)); n_in += 2
            else:
                raise ValueError(f"unknown context type for {name}: {ctx[name]}")
    env = Env(p, n_in, ctx_order)

    for s in prog.stmts:
        if isinstance(s, Skip):
            continue
        if isinstance(s, Init):
            regs = s.reg if isinstance(s.reg, list) else [s.reg]
            for r in regs: env.add_classical(r)
        elif isinstance(s, QInit):
            regs = s.reg if isinstance(s.reg, list) else [s.reg]
            for r in regs: env.add_quantum(r)
        elif isinstance(s, Meas):
            regs = s.reg if isinstance(s.reg, list) else [s.reg]
            for r in regs: env.measure(r)
        elif isinstance(s, Discard):
            regs = s.reg if isinstance(s.reg, list) else [s.reg]
            for r in regs: env.drop_var(r)
        elif isinstance(s, ApplyGate):
            regs = s.reg if isinstance(s.reg, list) else [s.reg]
            env.apply_quantum_gate(s.gate, regs)
        elif isinstance(s, AffineAssign):
            dsts = s.dst if isinstance(s.dst, list) else [s.dst]
            srcs = s.src if isinstance(s.src, list) else [s.src]
            env.apply_classical(s.transform, dsts, srcs)
        elif isinstance(s, Ctrl):
            def one(x): return x[0] if isinstance(x, list) else x
            pauli = getattr(s, "pauli", None)
            if pauli is None:
                raise NotImplementedError("Ctrl node missing 'pauli' field")
            env.apply_ctrl(str(pauli), one(s.ctrl), one(s.target))
        else:
            raise NotImplementedError(type(s))

    return env, env.current

if __name__ == "__main__":
    p = 5
    prog = parse_spl("qinit q; q *= MUL_2; q *= S_3; q *= T_4; q *= F_3;")
    env, rel = interpret(p, prog)
    print(rel)

