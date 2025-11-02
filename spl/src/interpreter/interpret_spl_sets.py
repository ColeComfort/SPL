from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from spl.src.parser.parser import Program, Init, QInit, Discard, Meas, ApplyGate, AffineAssign, Ctrl, Skip
from spl.src.relations.set_relations import SetRelation, vec_mod

@dataclass
class VarInfo:
    kind: str              # 'q' or 'c'
    out_idxs: List[int]    # output coordinates used by this var

class EnvSets:
    """
    Explicit set semantics. Domain is fixed by the context. All ops act on OUTPUTS only.
    """
    def __init__(self, p: int, n_in_ctx: int, ctx_order: List[Tuple[str,int]]):
        self.p = p
        self.n_in = n_in_ctx
        self.coord_dim = n_in_ctx
        self.input_names: Dict[int, str] = {}
        self.output_names: Dict[int, str] = {}
        out_cursor = 0
        in_cursor  = 0
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
                raise ValueError("width must be 1 or 2")
        self.current = SetRelation.identity(p, n_in_ctx, names=self.input_names)
        self.vars: Dict[str, VarInfo] = {}
        oc = 0
        for name, width in ctx_order:
            if width == 1:
                self.vars[name] = VarInfo('c', [oc]); oc += 1
            else:
                self.vars[name] = VarInfo('q', [oc, oc+1]); oc += 2

    # ---- structure helpers ----
    def _append_outputs(self, k: int, names: List[str]) -> List[int]:
        if k == 0: return []
        if len(names) != k: raise ValueError("name arity mismatch")
        p = self.p
        d_old = self.coord_dim
        d_new = d_old + k

        def f(y_old: List[int]) -> List[int]:
            return y_old + [0]*k

        rel_extend = SetRelation.from_graph_function(
            p, d_old, d_new, f,
            in_names=self.current.output_names,
            out_names={**self.current.output_names, **{d_old+j: names[j] for j in range(k)}}
        )
        self.current = self.current.compose(rel_extend)
        self.coord_dim = d_new
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
        return list(range(d_old, d_new))

    def add_classical(self, name: str):
        outs = self._append_outputs(1, [name])
        self.vars[name] = VarInfo('c', outs)

    def add_quantum(self, name: str):
        outs = self._append_outputs(2, [f"{name}.x", f"{name}.z"])
        self.vars[name] = VarInfo('q', outs)

    def _pointwise_update(self, updater, new_out_names: Dict[int, str]):
        p = self.p
        d = self.coord_dim
        rel = SetRelation.from_graph_function(
            p, d, d, lambda y: vec_mod(updater(y[:]), p),
            in_names=self.current.output_names,
            out_names=new_out_names
        )
        self.current = self.current.compose(rel)
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}

    def _drop_outputs(self, to_drop: List[int]):
        if not to_drop: return
        keep = sorted(set(range(self.coord_dim)) - set(to_drop))
        index = {old: i for i, old in enumerate(keep)}
        p = self.p

        def proj(y: List[int]) -> List[int]:
            return [y[j] for j in keep]

        new_names = {index[j]: self.current.output_names.get(j, "") for j in keep}
        rel_proj = SetRelation.from_graph_function(
            p, self.coord_dim, len(keep), proj,
            in_names=self.current.output_names, out_names=new_names
        )
        self.current = self.current.compose(rel_proj)
        self.coord_dim = len(keep)
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
        for v in self.vars.values():
            v.out_idxs = [index[j] for j in v.out_idxs if j in index]

    # ---- ops ----
    def measure(self, name: str):
        v = self.vars[name]
        if v.kind != 'q': return
        x, z = v.out_idxs
        self._drop_outputs([z])
        self.current.output_names[x] = name
        self.output_names = {j: self.current.output_names.get(j, "") for j in range(self.coord_dim)}
        v.kind = 'c'; v.out_idxs = [x]

    def drop_var(self, name: str):
        v = self.vars[name]
        self._drop_outputs(v.out_idxs)
        del self.vars[name]

    @staticmethod
    def _split_gate_token(tok: str):
        """
        Accept:
          - Non-MUL:  BASE^k, BASE^{k}
          - MUL:      MUL_k,  MUL_{k}
        Returns (BASE, int or None). BASE uppercased.
        """
        s = tok.strip()
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
                raise ValueError("MUL expects subscript parameter, e.g., MUL_3")
            return base_uc, k
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
                raise ValueError(f"{base_uc} expects superscript repetition, not subscript.")
            return base_uc, k
        return s.upper(), None



    # Quantum gates
    def apply_quantum_gate(self, gate: str, regs: List[str]):
        g_base, suffix = self._split_gate_token(gate)
        p = self.p

        if g_base in ("X","Z","S","F","T"):
            if len(regs) != 1: raise ValueError(f"{g_base} arity")
            v = self.vars[regs[0]]
            if v.kind != 'q': raise ValueError(f"{g_base} expects quantum var")
            x,z = v.out_idxs
            rep = 1 if suffix is None else (suffix % (4 if g_base == "F" else p))

            def upd(y):
                if g_base == "X":
                    y[x] = (y[x] + rep) % p
                elif g_base == "Z":
                    y[z] = (y[z] + rep) % p
                elif g_base == "S":
                    # S^k: z := z + k x
                    y[z] = (y[z] + rep * y[x]) % p
                elif g_base == "T":
                    # T^k: x := x - k z
                    y[x] = (y[x] - rep * y[z]) % p
                else:  # F^rep
                    r = rep % 4
                    a, b = y[x], y[z]
                    if r == 0: y[x], y[z] = a, b
                    elif r == 1: y[x], y[z] = b % p, (-a) % p
                    elif r == 2: y[x], y[z] = (-a) % p, (-b) % p
                    else: y[x], y[z] = (-b) % p, a % p
                return y

            self._pointwise_update(upd, self.current.output_names)
            return

        if g_base == "CX":
            if len(regs) != 2: raise ValueError("CX arity")
            v1, v2 = self.vars[regs[0]], self.vars[regs[1]]
            if v1.kind != 'q' or v2.kind != 'q': raise ValueError("CX quantum targets")
            x1,z1 = v1.out_idxs; x2,z2 = v2.out_idxs
            times = 1 if suffix is None else (suffix % p)
            def upd(y):
                y[x2] = (y[x2] + times * y[x1]) % p
                y[z2] = (y[z2] - times * y[z1]) % p
                return y
            self._pointwise_update(upd, self.current.output_names)
            return

        if g_base == "MUL":
            if len(regs) != 1: raise ValueError("MUL_k arity")
            if suffix is None: raise ValueError("MUL_k requires a numeric parameter, e.g., MUL_3")
            k = suffix % p
            if k == 0: raise ValueError("MUL_k requires k in F_p^×")
            try:
                kinv = pow(k, -1, p)
            except ValueError:
                raise ValueError("MUL_k requires gcd(k,p)=1")
            v = self.vars[regs[0]]
            if v.kind != 'q': raise ValueError("MUL_k expects quantum var")
            x,z = v.out_idxs
            def upd(y):
                y[x] = (k * y[x]) % p
                y[z] = (kinv * y[z]) % p
                return y
            self._pointwise_update(upd, self.current.output_names)
            return

        raise ValueError(f"unknown quantum gate '{gate}'")

    # Classical ops
    def apply_classical(self, transform: str, dsts: List[str], srcs: List[str]):
        tr = transform.strip().lower()
        def get_c_out(name: str) -> int:
            v = self.vars[name]
            if v.kind != 'c' or len(v.out_idxs) != 1:
                raise ValueError(f"{name} not a classical 1-wire")
            return v.out_idxs[0]

        if tr == "copy":
            if len(srcs)!=1 or len(dsts)!=2: raise ValueError("copy 1->2")
            s = get_c_out(srcs[0]); u = get_c_out(dsts[0]); v = get_c_out(dsts[1])
            def upd(y):
                y[u] = y[s] % self.p
                y[v] = y[s] % self.p
                return y
            self._pointwise_update(upd, self.current.output_names)

        elif tr == "sum":
            if len(srcs)!=2 or len(dsts)!=1: raise ValueError("sum 2->1")
            s1 = get_c_out(srcs[0]); s2 = get_c_out(srcs[1]); t = get_c_out(dsts[0])
            def upd(y):
                y[t] = (y[s1] + y[s2]) % self.p
                return y
            self._pointwise_update(upd, self.current.output_names)

        elif tr == "plusone":
            if len(srcs)!=1 or len(dsts)!=1 or srcs[0]!=dsts[0]:
                raise ValueError("plusone in-place")
            x = get_c_out(srcs[0])
            def upd(y):
                y[x] = (y[x] + 1) % self.p
                return y
            self._pointwise_update(upd, self.current.output_names)

        elif tr == "and":
            # t := s1 * s2 over F_p
            if len(srcs)!=2 or len(dsts)!=1: raise ValueError("and 2->1")
            s1 = get_c_out(srcs[0]); s2 = get_c_out(srcs[1]); t = get_c_out(dsts[0])
            def upd(y):
                y[t] = (y[s1] * y[s2]) % self.p
                return y
            self._pointwise_update(upd, self.current.output_names)

        else:
            raise ValueError(f"unknown classical transform '{transform}'")

    
    def apply_ctrl(self, gate: str, c_name: str, q_name: str):
        gate = gate.upper()
        c = self.vars[c_name]; q = self.vars[q_name]
        if c.kind != 'c' or q.kind != 'q':
            raise ValueError("ctrl expects classical then quantum")
        c_idx = c.out_idxs[0]; x_idx, z_idx = q.out_idxs
        def upd(y):
            k = y[c_idx] % self.p
            if gate in ("X","CTRLX"):
                y[x_idx] = (y[x_idx] + k) % self.p
            elif gate in ("Z","CTRLZ"):
                y[z_idx] = (y[z_idx] + k) % self.p
            elif gate == "S":
                # S^k: (x,z) -> (x, z + k*x)
                y[z_idx] = (y[z_idx] + k * y[x_idx]) % self.p
            elif gate == "F":
                # F^k: multiply by F^k in SL(2,p): (x,z) -> (x,z) if k even? We implement k times F
                k_mod = k % self.p
                for _ in range(k_mod):
                    x, z = y[x_idx], y[z_idx]
                    y[x_idx], y[z_idx] = z % self.p, (-x) % self.p
            elif gate.startswith("MUL"):
                # Expect MUL_t or MUL_t^?; parse integer t
                t = None
                m = gate.split("_")
                if len(m) == 2:
                    try:
                        t = int(m[1])
                    except ValueError:
                        t = None
                if t is None:
                    raise ValueError(f"unknown gate token for MUL: {gate}")
                # Apply scaling x -> t^k * x, z -> (t^{-k}) * z
                # Compute t^k mod p and its inverse
                tk = pow(t, k, self.p)
                # inverse of tk modulo p
                inv = pow(tk, -1, self.p)
                y[x_idx] = (tk * y[x_idx]) % self.p
                y[z_idx] = (inv * y[z_idx]) % self.p
            else:
                raise ValueError(f"unknown controlled gate '{gate}'")
            return y
        self._pointwise_update(upd, self.current.output_names)



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
                raise ValueError("bad ctx type")

    env = EnvSets(p, n_in, ctx_order)
    for s in prog.stmts:
        if isinstance(s, Skip):
            pass
        elif isinstance(s, Init):
            env.add_classical(s.reg if isinstance(s.reg, str) else s.reg[0])
        elif isinstance(s, QInit):
            env.add_quantum(s.reg if isinstance(s.reg, str) else s.reg[0])
        elif isinstance(s, Meas):
            env.measure(s.reg if isinstance(s.reg, str) else s.reg[0])
        elif isinstance(s, Discard):
            env.drop_var(s.reg if isinstance(s.reg, str) else s.reg[0])
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

def interpret_sets(p, prog, context=None):
    return interpret(p, prog, context)