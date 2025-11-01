from typing import *
from ..parser.ast import *
def compile_program_fn(prog: Program, fn_name: str) -> str:
    fns = functions_by_name(prog)
    if fn_name not in fns: raise NameError(f"unknown function {fn_name}")
    dim = prog.dim or 2
    comp = Compiler(dim, fns=fns)
    return comp.compile_function_to_spl(fns[fn_name])


def compile_text_fn(src: str, fn_name: str) -> str:
    P = parse_splpp(src)
    return compile_program_fn(P, fn_name)




# ===== inlined utils (moved from utils.py) =====
from dataclasses import dataclass
from typing import *

class DaggerAs(Stmt):
    src: str
    dst: str


class Expr: ...


class IntLit(Expr): value: int


class BoolLit(Expr): value: bool


class VarRef(Expr): name: str


class BinOp(Expr): op: str; left: Expr; right: Expr


class UnOp(Expr): op: str; expr: Expr


class _ToAST(Transformer):
    def INT(self, t: Token): return int(t)
    def IDENT(self, t: Token): return str(t)
    def ATOMICTYPE(self, t: Token): return str(t)
    def KIND(self, t: Token): return str(t)
    def fntype(self, items): return items[0] if items else "Linear"

    def params(self, items): return items
    def outtypes(self, items): return [str(t) for t in items]
    def param(self, items): return (items[0], items[1])
    def dim_decl(self, items): return ("dim", items[0])
    def fn_decl(self, items): return items[0]

    def vardecl(self, items):
        name = items[0]
        expr = items[1] if len(items) == 2 else None
        return VarDecl(name, expr)

    def init_stmt(self, items):
        name = items[0]
        val = items[1] if len(items) == 2 else None
        return InitStmt(name, val)

    def qinit_stmt(self, items):
        name = items[0]
        if len(items) == 2:
            v = items[1]
            return QInitStmt(name, v if isinstance(v, int) else "mixed")
        return QInitStmt(name, None)

    def meas_stmt(self, items): return MeasStmt(items[0])
    def prep_stmt(self, items): return PrepStmt(items[0])

    def main_decl(self, items):
        i = 0
        in_params: List[Tuple[str,str]] = []
        if i < len(items) and isinstance(items[i], list) and (not items[i] or isinstance(items[i][0], tuple)):
            in_params = items[i]; i += 1
        body: List[Stmt] = []
        for x in items[i:]:
            if isinstance(x, Stmt): body.append(x)
            elif isinstance(x, list): body.extend(y for y in x if isinstance(y, Stmt))
        return FnDecl("main", in_params, [], None, body)

    def ann_fn_decl(self, items):
        kind = str(items[0]); name = str(items[1])
        i = 2
        in_params: List[Tuple[str,str]] = []
        if i < len(items) and isinstance(items[i], list) and (not items[i] or isinstance(items[i][0], tuple)):
            in_params = items[i]; i += 1
        if i >= len(items) or not isinstance(items[i], list):
            raise ValueError("function output types missing")
        out_types: List[str] = items[i]; i += 1
        body: List[Stmt] = []
        for x in items[i:]:
            if isinstance(x, Stmt): body.append(x)
            elif isinstance(x, list): body.extend(y for y in x if isinstance(y, Stmt))
        return FnDecl(name, in_params, out_types, kind, body)

    # --- unambiguous apply/qctrl/cctrl builders ---
    def apply_with_outs(self, items):
        gate = items[0]
        if len(items) == 2:
            args: List[str] = []
            outs: List[str] = items[1]
        else:
            args = items[1] if isinstance(items[1], list) else []
            outs = items[-1]
        return Apply(gate, args, outs)

    def apply_no_outs(self, items):
        gate = items[0]
        args = items[1] if len(items) >= 2 and isinstance(items[1], list) else []
        return Apply(gate, args, None)

    def qctrl_with_outs(self, items):
        ctrl, gate = items[0], items[1]
        if len(items) == 3:
            args: List[str] = []
            outs: List[str] = items[2]
        else:
            args = items[2] if isinstance(items[2], list) else []
            outs = items[-1]
        return QCtrlApply(ctrl, gate, args, outs)

    def qctrl_no_outs(self, items):
        ctrl, gate = items[0], items[1]
        args = items[2] if len(items) >= 3 and isinstance(items[2], list) else []
        return QCtrlApply(ctrl, gate, args, None)

    def cctrl_with_outs(self, items):
        ctrl, gate = items[0], items[1]
        if len(items) == 3:
            args: List[str] = []
            outs: List[str] = items[2]
        else:
            args = items[2] if isinstance(items[2], list) else []
            outs = items[-1]
        return CCtrlApply(ctrl, gate, args, outs)

    def cctrl_no_outs(self, items):
        ctrl, gate = items[0], items[1]
        args = items[2] if len(items) >= 3 and isinstance(items[2], list) else []
        return CCtrlApply(ctrl, gate, args, None)

    def assertion(self, items):
        rel = str(items[0]).lower()
        f = str(items[1]); g = str(items[2])
        return AssertRel("equal" if rel=="equal" else "included", f, g)

    def printspl(self, items): return PrintSPL(str(items[0]))
    def varlist(self, items): return list(items)
    def block(self, items): return [x for x in items if isinstance(x, Stmt)]
    def ifstmt(self, items):
        cond = items[0]
        then_body = items[1] if len(items) >= 2 else []
        else_body = items[2] if len(items) >= 3 else []
        return IfStmt(cond, then_body, else_body)

    def ret(self, items):
        return Return(items[0] if items else [])

    def daggeras(self, items): return DaggerAs(items[0], items[1])
    def true(self, _): return BoolLit(True)
    def false(self, _): return BoolLit(False)
    def intlit(self, items): return IntLit(items[0])
    def varref(self, items): return VarRef(items[0])
    def bor(self, items):
        if len(items) == 1: return items[0]
        e = items[0]
        for r in items[1:]: e = BinOp("or", e, r)
        return e
    def band(self, items):
        if len(items) == 1: return items[0]
        e = items[0]
        for r in items[1:]: e = BinOp("and", e, r)
        return e
    def not_(self, items): return UnOp("not", items[0])
    def cmp(self, items):
        if len(items) == 1: return items[0]
        return BinOp(str(items[1]), items[0], items[2])
    def aexpr(self, items):
        e = items[0]; i = 1
        while i < len(items):
            e = BinOp(items[i], e, items[i+1]); i += 2
        return e
    def term(self, items):
        e = items[0]; i = 1
        while i < len(items):
            e = BinOp(items[i], e, items[i+1]); i += 2
        return e

    def program(self, items):
        dim = None
        decls: List[FnDecl] = []

        def add_decl(x):
            if isinstance(x, FnDecl): decls.append(x)
            elif isinstance(x, list):
                for y in x: add_decl(y)

        for it in items:
            if isinstance(it, tuple) and it[0] == "dim": dim = it[1]
            else: add_decl(it)
        return Program(dim, decls)

    def start(self, items): return items[0]


class VarInfo:
    ty: Literal["Dit","Qdit","Bool"]
    phys: str


class Env:
    dim: int = 2
    vars: Dict[str, VarInfo] = field(default_factory=dict)   # logical -> VarInfo
    declared_phys: set = field(default_factory=set)           # allocated regs (init/qinit)

    def has(self, name: str) -> bool: return name in self.vars

    def require(self, name: str, expect: Optional[str]=None) -> VarInfo:
        if name not in self.vars: raise TypeError(f"undeclared variable {name}")
        vi = self.vars[name]
        if expect and vi.ty != expect:
            raise TypeError(f"type mismatch for {name}: expected {expect}, found {vi.ty}")
        return vi

    def declare(self, name: str, ty: str, phys: Optional[str]=None):
        if name in self.vars:
            raise TypeError(f"variable {name} already exists; discard before re-initializing")
        self.vars[name] = VarInfo(ty, phys or name)

    def set_type_same_phys(self, name: str, new_ty: str):
        if name not in self.vars: raise TypeError(f"undeclared variable {name}")
        self.vars[name] = VarInfo(new_ty, self.vars[name].phys)

    def phys_of(self, name: str) -> str:
        return self.require(name).phys

    def rename(self, name: str, new_ty: str, new_phys: str):
        if name not in self.vars: raise TypeError(f"undeclared variable {name}")
        self.vars[name] = VarInfo(new_ty, new_phys)


class SPLBuffer:
    lines: List[str] = field(default_factory=list)
    ctx: Dict[str,str] = field(default_factory=dict)
    def add(self, s: str): self.lines.append(s)
    def render(self) -> str:
        ctx_entries = [f"{k}: {v}" for k,v in self.ctx.items()]
        ctx_block = ("context {\n    " + "\n    ".join(ctx_entries) + "\n}\n") if ctx_entries else ""
        body = "\n".join(self.lines) if self.lines else "skip"
        return ctx_block + body + ("\n" if body and body[-1] != "\n" else "")


class Compiler:
    def __init__(self, dim: int, fns: Optional[Dict[str, FnDecl]] = None):
        self.dim = dim
        self.fns = fns or {}
        self._call_stack: List[str] = []
        self._tmp_counter = 0

    @staticmethod
    def ctx_of(ty: str) -> str:
        return "qpit" if ty == "Qdit" else "pit"

    # ---------- kind inference ----------

    def infer_required_kind(self, fn: FnDecl, seen: Optional[set]=None) -> str:
        if fn.kind is None:
            return "Nonlinear"
        seen = seen or set()
        if fn.name in seen:
            raise RecursionError(f"cyclic call graph not allowed in kind inference at {fn.name}")
        seen.add(fn.name)

        req = "Pauli"
        def join(k: str):
            nonlocal req
            req = _KIND_JOIN[req][k]

        for s in fn.body:
            if isinstance(s, VarDecl):
                # Any boolean-based initializer is nonlinear
                if s.expr is not None:
                    join("Nonlinear")

            elif isinstance(s, Apply):
                if s.gate in self.fns and self.fns[s.gate].name != "main":
                    cal = self.fns[s.gate]
                    join(self.infer_required_kind(cal, seen))
                else:
                    pk = _primitive_kind(s.gate)
                    if pk is None:
                        n = s.gate.lower()
                        if n in {"sum","plusone","copy"}:
                            join("Linear")
                        elif n in {"and"}:
                            join("Nonlinear")
                        elif n in {"meas","prep"}:
                            join("Linear")
                        else:
                            join("Linear")
                    else:
                        join(pk)

            elif isinstance(s, QCtrlApply):
                # only Pauli targets allowed; result kind Clifford
                tgt_kind: Optional[str] = None
                if s.gate in self.fns and self.fns[s.gate].name != "main":
                    tgt_kind = self.infer_required_kind(self.fns[s.gate], seen)
                elif _is_pauli_primitive(s.gate):
                    tgt_kind = "Pauli"
                else:
                    raise TypeError("quantum control only over Pauli")
                if tgt_kind == "Clifford":
                    raise TypeError("quantum control over @Clifford is not supported")
                if tgt_kind != "Pauli":
                    raise TypeError(f"quantum control over @{tgt_kind} not supported")
                join("Clifford")

            elif isinstance(s, CCtrlApply):
                tgt_kind: Optional[str] = None
                if s.gate in self.fns and self.fns[s.gate].name != "main":
                    tgt_kind = self.infer_required_kind(self.fns[s.gate], seen)
                elif _is_pauli_primitive(s.gate):
                    tgt_kind = "Pauli"
                else:
                    raise TypeError("classical control only over Pauli or Clifford")
                if tgt_kind == "Pauli":
                    join("Linear")
                elif tgt_kind == "Clifford":
                    join("Nonlinear")  # future implementation
                else:
                    raise TypeError(f"classical control over @{tgt_kind} not supported")

            elif isinstance(s, (InitStmt, QInitStmt, MeasStmt, PrepStmt)):
                # State ops count as Linear for kind inference
                join("Linear")

            elif isinstance(s, IfStmt):
                # Branching is nonlinear
                join("Nonlinear")

            elif isinstance(s, DaggerAs):
                if s.src not in self.fns: raise NameError(f"unknown function {s.src} in dagger")
                src_k = self.infer_required_kind(self.fns[s.src], seen)
                if src_k not in {"Pauli","Clifford"}:
                    raise TypeError("only Pauli or Clifford can be daggered")

        return req

    def _check_declared_kind(self, fn: FnDecl):
        inferred = self.infer_required_kind(fn)
        if _KIND_POS[fn.kind] < _KIND_POS[inferred]:
            raise TypeError(f"{fn.name}: declared @{fn.kind} but requires @{inferred}")

    # ---------- constant-fold simple bool/int for runtime 'if' selection ----------

    def eval_expr(self, e: Expr) -> Union[int,bool]:
        if isinstance(e, IntLit): return e.value
        if isinstance(e, BoolLit): return e.value
        if isinstance(e, VarRef): return 0
        if isinstance(e, UnOp):
            v = self.eval_expr(e.expr)
            if e.op == "not": return not bool(v)
            raise ValueError("unknown unary op")
        if isinstance(e, BinOp):
            l = self.eval_expr(e.left); r = self.eval_expr(e.right)
            if e.op in {"+","-","*","/"}:
                return int(l) + int(r) if e.op=="+" else int(l) - int(r) if e.op=="-" else int(l)*int(r) if e.op=="*" else int(l)//int(r)
            if e.op in {"==","!=", "<","<=",">",">="}:
                return eval(f"{l}{e.op}{r}")
            if e.op == "and": return bool(l) and bool(r)
            if e.op == "or":  return bool(l) or bool(r)
        raise ValueError("bad expression")

    # ---------- Boolean lowering helpers (only init/disc/copy/sum/plusone/and) ----------

    def _new_tmp(self) -> str:
        self._tmp_counter += 1
        return f"_t{self._tmp_counter}"

    def _alloc_zero(self, env: Env, buf: SPLBuffer, name: str):
        if env.has(name):
            return
        env.declare(name, "Dit", phys=name)
        if name in env.declared_phys:
            raise TypeError(f"register {name} already allocated; discard before re-init")
        buf.add(f"init {name}")
        env.declared_phys.add(name)

    def _plus_k(self, buf: SPLBuffer, reg: str, k: int, p: int):
        k %= p
        for _ in range(k):
            buf.add(f"{reg} = plusone * {reg}")

    def _scale_into(self, env: Env, buf: SPLBuffer, out: str, src: str, k: int, p: int):
        k %= p
        if k == 0:
            return
        terms = [src]
        need = k - 1
        pool = [src]
        while need > 0:
            base = pool.pop(0)
            a = self._new_tmp(); b = self._new_tmp()
            self._alloc_zero(env, buf, a); self._alloc_zero(env, buf, b)
            buf.add(f"({a}, {b}) = copy * {base}")
            terms.append(a); pool.append(b)
            need -= 1
        if len(terms) == 1:
            buf.add(f"{out} = sum * {terms[0]}")
        else:
            buf.add(f"{out} = sum * ({', '.join(terms)})")

    def _mk_const(self, env: Env, buf: SPLBuffer, k: int) -> str:
        p = env.dim
        t = self._new_tmp()
        self._alloc_zero(env, buf, t)
        self._plus_k(buf, t, k % p, p)
        return t

    def _lower_bexpr_into(self, env: Env, buf: SPLBuffer, out: str, e: Expr):
        p = env.dim

        def emit(e: Expr) -> str:
            if isinstance(e, BoolLit):
                return self._mk_const(env, buf, 1 if e.value else 0)
            if isinstance(e, IntLit):
                return self._mk_const(env, buf, 1 if (e.value % p) != 0 else 0)
            if isinstance(e, VarRef):
                if env.has(e.name):
                    vi = env.require(e.name)
                    if vi.ty == "Dit": return vi.phys
                    if vi.ty == "Bool":
                        self._alloc_zero(env, buf, e.name)
                        return e.name
                    raise TypeError(f"variable {e.name} not a classical bit")
                self._alloc_zero(env, buf, e.name)
                return e.name

            if isinstance(e, UnOp) and e.op == "not":
                a = emit(e.expr)
                one = self._mk_const(env, buf, 1)
                neg = self._new_tmp(); self._alloc_zero(env, buf, neg)
                self._scale_into(env, buf, neg, a, p-1, p)
                t = self._new_tmp(); self._alloc_zero(env, buf, t)
                buf.add(f"{t} = sum * ({one}, {neg})")
                return t

            if isinstance(e, BinOp):
                if e.op == "and":
                    a = emit(e.left); b = emit(e.right)
                    t = self._new_tmp(); self._alloc_zero(env, buf, t)
                    buf.add(f"{t} = and * ({a}, {b})")
                    return t

                if e.op == "or":
                    a = emit(e.left); b = emit(e.right)
                    ab = self._new_tmp(); self._alloc_zero(env, buf, ab)
                    buf.add(f"{ab} = and * ({a}, {b})")
                    abneg = self._new_tmp(); self._alloc_zero(env, buf, abneg)
                    self._scale_into(env, buf, abneg, ab, p-1, p)
                    s = self._new_tmp(); self._alloc_zero(env, buf, s)
                    buf.add(f"{s} = sum * ({a}, {b})")
                    t = self._new_tmp(); self._alloc_zero(env, buf, t)
                    buf.add(f"{t} = sum * ({s}, {abneg})")
                    return t

                if e.op in {"!=", "=="}:
                    a = emit(e.left); b = emit(e.right)
                    ab = self._new_tmp(); self._alloc_zero(env, buf, ab)
                    buf.add(f"{ab} = and * ({a}, {b})")
                    twoab = self._new_tmp(); self._alloc_zero(env, buf, twoab)
                    self._scale_into(env, buf, twoab, ab, 2, p)
                    s = self._new_tmp(); self._alloc_zero(env, buf, s)
                    buf.add(f"{s} = sum * ({a}, {b})")
                    neg_twoab = self._new_tmp(); self._alloc_zero(env, buf, neg_twoab)
                    self._scale_into(env, buf, neg_twoab, twoab, p-1, p)
                    xor_ = self._new_tmp(); self._alloc_zero(env, buf, xor_)
                    buf.add(f"{xor_} = sum * ({s}, {neg_twoab})")
                    if e.op == "!=":
                        return xor_
                    one = self._mk_const(env, buf, 1)
                    xnor = self._new_tmp(); self._alloc_zero(env, buf, xnor)
                    neg_xor = self._new_tmp(); self._alloc_zero(env, buf, neg_xor)
                    self._scale_into(env, buf, neg_xor, xor_, p-1, p)
                    buf.add(f"{xnor} = sum * ({one}, {neg_xor})")
                    return xnor

                if e.op in {"+", "-"}:
                    a = emit(e.left); b = emit(e.right)
                    t = self._new_tmp(); self._alloc_zero(env, buf, t)
                    if e.op == "+":
                        buf.add(f"{t} = sum * ({a}, {b})")
                    else:
                        bneg = self._new_tmp(); self._alloc_zero(env, buf, bneg)
                        self._scale_into(env, buf, bneg, b, p-1, p)
                        buf.add(f"{t} = sum * ({a}, {bneg})")
                    return t

                if e.op == "*":
                    a = emit(e.left); b = emit(e.right)
                    t = self._new_tmp(); self._alloc_zero(env, buf, t)
                    buf.add(f"{t} = and * ({a}, {b})")
                    return t

            raise TypeError("unsupported boolean expression")

        self._alloc_zero(env, buf, out)
        src = emit(e)
        if src != out:
            buf.add(f"{out} = sum * {src}")

    # ---------- enforce outs rule ----------

    def _enforce_outs_rule(self, gate: str, args: List[str], outs: Optional[List[str]]):
        if _is_unitary_gate(gate):
            if outs is None: return
            if len(outs) != len(args) or outs != args:
                raise TypeError("unitary must either omit outputs or use identical outs == ins (same order)")
        else:
            if outs is None:
                raise TypeError("non-unitary must specify outputs")

    # ---------- gate emission helpers ----------

    def _invert_gate_token(self, g: str, dim: int) -> str:
        G = g.strip()
        U = G.split("_",1)[0].upper()
        if U == "MUL":
            k_str = G.split("_",1)[1]
            k = int(k_str)
            kinv = pow(k % dim, -1, dim)
            return f"MUL_{kinv}"
        if G.endswith("^{-1}"):
            return G[:-5]
        return f"{G}^{{-1}}"

    def _emit_apply(self, env: Env, buf: SPLBuffer, gate: str, args: List[str], outs: Optional[List[str]]):
        G = gate.strip()
        BASE = G.split("_",1)[0].upper()
        phys_args = [env.phys_of(a) for a in args]
        phys_outs = [env.phys_of(o) for o in outs] if outs else None

        # Parametric unitary, includes inverse spellings passed-through
        if BASE in PARAM_UNITARY:
            if len(phys_args) != 1: raise TypeError(f"{G} arity")
            buf.add(f"{phys_args[0]} *= {G.upper()}")
            return

        # Unitaries
        if BASE in UNITARY_GATES_1:
            if len(phys_args) != 1: raise TypeError(f"{BASE} arity")
            buf.add(f"{phys_args[0]} *= {G.upper()}")
            return
        if BASE in UNITARY_GATES_2:
            if len(phys_args) != 2: raise TypeError(f"{BASE} arity")
            buf.add(f"({phys_args[0]}, {phys_args[1]}) *= {G.upper()}")
            return

        # Non-unitary transforms
        name_ident = G.lower()
        if name_ident in {"meas","prep"}:
            raise TypeError("use 'meas x;' / 'prep x;' forms")
        if name_ident in CLASSICAL_ASSIGN:
            if name_ident == 'copy':
                if not phys_outs or len(phys_outs) != 2: raise TypeError('copy expects 1 src, 2 dests')
                if len(phys_args) != 1: raise TypeError('copy expects exactly 1 input')
                buf.add(f"({', '.join(phys_outs)}) = copy * {phys_args[0]}")
            else:
                if not phys_outs or len(phys_outs) != 1: raise TypeError(f"{name_ident} requires exactly one output")
                if len(phys_args) == 1:
                    buf.add(f"{phys_outs[0]} = {name_ident} * {phys_args[0]}")
                elif len(phys_args) >= 2:
                    buf.add(f"{phys_outs[0]} = {name_ident} * ({', '.join(phys_args)})")
                else:
                    raise TypeError(f"{name_ident} needs inputs")
            return

        raise NameError(f"unknown primitive/transform '{gate}'")

    # ---- control lowering helpers ----

    def _emit_ctrl_pauli_primitive(self, buf: SPLBuffer, ctrl_phys: str, gate: str, tgt_phys: str):
        g = gate.upper()
        if g == "X": buf.add(f"ctrlX {ctrl_phys} {tgt_phys}")
        elif g == "Z": buf.add(f"ctrlZ {ctrl_phys} {tgt_phys}")
        else: raise TypeError("only Pauli X or Z allowed for control")

    def _emit_qctrl_pauli_primitive(self, buf: SPLBuffer, ctrl_phys: str, gate: str, tgt_phys: str):
        g = gate.upper()
        if g == "X":
            buf.add(f"({ctrl_phys}, {tgt_phys}) *= CX")
        elif g == "Z":
            buf.add(f"{tgt_phys} *= F")
            buf.add(f"({ctrl_phys}, {tgt_phys}) *= CX")
            buf.add(f"{tgt_phys} *= F")
            buf.add(f"{tgt_phys} *= F")
            buf.add(f"{tgt_phys} *= F")
        else:
            raise TypeError("only Pauli X or Z allowed for quantum control")

    def _inline_ctrl_over_pauli_fn(self, env: Env, buf: SPLBuffer, ctrl_phys: str,
                                   callee: FnDecl, arg_names: List[str],
                                   emit_ctrl):
        if len(arg_names) != len(callee.in_params):
            raise TypeError(f"controlled call arity mismatch to {callee.name}")
        name_to_phys: Dict[str, str] = {}
        for (param_name, _pty), actual in zip(callee.in_params, arg_names):
            name_to_phys[param_name] = env.phys_of(actual)

        for st in callee.body:
            if isinstance(st, Apply):
                base = st.gate.split("_",1)[0].upper()
                if base in {"X", "Z"} and len(st.args) == 1:
                    tgt_log = st.args[0]
                    tgt_phys = name_to_phys.get(tgt_log, env.phys_of(tgt_log))
                    emit_ctrl(buf, ctrl_phys, base, tgt_phys)
                    continue
                if st.gate in self.fns and self.fns[st.gate].kind == "Pauli":
                    nested = self.fns[st.gate]
                    nested_actuals = [a for a in st.args]
                    self._inline_ctrl_over_pauli_fn(env, buf, ctrl_phys, nested, nested_actuals, emit_ctrl)
                    continue
                raise TypeError(f"only Pauli X/Z or @Pauli calls allowed in controlled @Pauli, got {st.gate}")

            elif isinstance(st, (VarDecl, InitStmt, QInitStmt, MeasStmt, PrepStmt, QCtrlApply, CCtrlApply)):
                raise TypeError(f"unsupported stmt inside controlled @Pauli: {type(st).__name__}")
            elif isinstance(st, (IfStmt, DaggerAs, Return, PrintSPL, AssertRel)):
                continue
            else:
                raise TypeError(f"unsupported stmt inside controlled @Pauli: {type(st).__name__}")

    # ---- outputs of a function (names) ----

    def _resolve_outputs_of_fn(self, fn: FnDecl) -> Tuple[List[str], bool]:
        init_order: List[str] = []
        explicit_return: Optional[List[str]] = None

        def note(n: str):
            if n not in init_order: init_order.append(n)

        for s in fn.body:
            if isinstance(s, (InitStmt, QInitStmt)): note(s.name)
            elif isinstance(s, IfStmt):
                for t in s.then_body:
                    if isinstance(t, (InitStmt, QInitStmt)): note(t.name)
                for t in s.else_body:
                    if isinstance(t, (InitStmt, QInitStmt)): note(t.name)
            elif isinstance(s, Return):
                explicit_return = s.vars[:]
        if explicit_return is not None:
            return explicit_return, True
        return init_order[:], False

    # ---- unitary in-place inlining ----

    def _inline_unitary_noouts(self, caller_env: Env, buf: SPLBuffer,
                               callee: FnDecl, arg_names: List[str]):
        if len(arg_names) != len(callee.in_params):
            exp = [p for (p, _) in callee.in_params]
            raise TypeError(f"in-place call arity mismatch to {callee.name}: got {len(arg_names)}, expected {len(exp)}")

        name_to_phys = {pname: caller_env.phys_of(actual)
                        for (pname, _pty), actual in zip(callee.in_params, arg_names)}

        for st in callee.body:
            if isinstance(st, Apply):
                base = st.gate.split("_",1)[0].upper()
                if base in {"X","Z"} and len(st.args) == 1:
                    tgt_log = st.args[0]
                    tgt_phys = name_to_phys.get(tgt_log, caller_env.phys_of(tgt_log))
                    buf.add(f"{tgt_phys} *= {base}")
                    continue
                if st.gate in self.fns and self.fns[st.gate].kind in {"Pauli","Clifford"}:
                    nested = self.fns[st.gate]
                    nested_actuals = [a for a in st.args]
                    self._inline_unitary_noouts(caller_env, buf, nested, nested_actuals)
                    continue
                raise TypeError(f"unsupported apply in unitary in-place call: {st.gate}")

            elif isinstance(st, (VarDecl, InitStmt, QInitStmt, MeasStmt, PrepStmt, QCtrlApply, CCtrlApply)):
                raise TypeError(f"state/control not allowed in unitary in-place call: {type(st).__name__}")
            elif isinstance(st, (IfStmt, DaggerAs, Return, PrintSPL, AssertRel)):
                continue
            else:
                raise TypeError(f"unsupported stmt in unitary in-place call: {type(st).__name__}")

    # ---- DAGGER collection ----

    def _collect_unitary_ops(self, env: Env, callee: FnDecl, arg_names: List[str]) -> List[Tuple[str,List[str]]]:
        name_to_phys = {pname: env.phys_of(actual) if env.has(actual) else actual
                        for (pname,_),actual in zip(callee.in_params, arg_names)}
        ops: List[Tuple[str,List[str]]] = []

        def phys(n): return name_to_phys.get(n, env.phys_of(n) if env.has(n) else n)

        for st in callee.body:
            if isinstance(st, Apply):
                base = st.gate.split("_",1)[0].upper()
                if base in UNITARY_GATES_1 and len(st.args)==1:
                    ops.append( (st.gate, [phys(st.args[0])]) )
                elif base in UNITARY_GATES_2 and len(st.args)==2:
                    ops.append( (st.gate, [phys(st.args[0]), phys(st.args[1])]) )
                elif base in PARAM_UNITARY and len(st.args)==1:
                    ops.append( (st.gate, [phys(st.args[0])]) )
                elif st.gate in self.fns and self.fns[st.gate].kind in {"Pauli","Clifford"}:
                    ops.extend(self._collect_unitary_ops(env, self.fns[st.gate], st.args))
                else:
                    raise TypeError("dagger requires unitary-only body")
            elif isinstance(st, (VarDecl, InitStmt, QInitStmt, MeasStmt, PrepStmt, QCtrlApply, CCtrlApply)):
                raise TypeError("dagger requires unitary-only body")
            elif isinstance(st, IfStmt):
                raise TypeError("dagger does not support control flow")
        return ops

    # ---- compile a block ----

    def _compile_block(self, env: Env, buf: SPLBuffer, body: List[Stmt], fn_kind: Optional[str]):
        def forbid_state(op: str):
            if fn_kind in {"Pauli", "Clifford"}:
                raise TypeError(f"{op} not allowed in {fn_kind} functions")

        def ensure_kind(need: str, feature: str):
            if fn_kind is None: return
            if _KIND_POS[fn_kind] < _KIND_POS[need]:
                raise TypeError(f"{feature} requires @{need}, found @{fn_kind}")

        for s in body:
            if isinstance(s, VarDecl):
                if env.has(s.name): raise TypeError(f"variable {s.name} already exists; cannot redeclare as Bool")
                if s.expr is None:
                    env.declare(s.name, "Bool", phys=s.name)
                else:
                    # boolean-based init is lowered but classified nonlinear in kind inference
                    env.declare(s.name, "Dit", phys=s.name)
                    self._lower_bexpr_into(env, buf, s.name, s.expr)

            elif isinstance(s, InitStmt):
                forbid_state("init")
                if env.has(s.name): raise TypeError(f"variable {s.name} already exists; discard before init")
                env.declare(s.name, "Dit", phys=s.name)
                if s.name in env.declared_phys: raise TypeError(f"register {s.name} already allocated; discard before re-init")
                buf.add(f"init {s.name}"); env.declared_phys.add(s.name)
                if s.value is not None:
                    k = s.value % env.dim
                    self._plus_k(buf, s.name, k, env.dim)

            elif isinstance(s, QInitStmt):
                forbid_state("qinit")
                if env.has(s.name): raise TypeError(f"variable {s.name} already exists; discard before qinit")
                env.declare(s.name, "Qdit", phys=s.name)
                if s.name in env.declared_phys: raise TypeError(f"register {s.name} already allocated; discard before re-qinit")
                buf.add(f"qinit {s.name}"); env.declared_phys.add(s.name)
                if s.value == "mixed":
                    buf.add(f"{s.name} *= F")
                    buf.add(f"meas {s.name}")
                    buf.add(f"prep {s.name}")
                elif isinstance(s.value, int):
                    k = s.value % env.dim
                    for _ in range(k):
                        buf.add(f"{s.name} *= X")

            elif isinstance(s, MeasStmt):
                forbid_state("meas")
                vi = env.require(s.name, expect="Qdit")
                buf.add(f"meas {vi.phys}")
                env.set_type_same_phys(s.name, "Dit")

            elif isinstance(s, PrepStmt):
                forbid_state("prep")
                vi = env.require(s.name, expect="Dit")
                buf.add(f"disc {vi.phys}")
                if vi.phys in env.declared_phys: env.declared_phys.remove(vi.phys)
                buf.add(f"qinit {vi.phys}")
                env.set_type_same_phys(s.name, "Qdit")
                env.declared_phys.add(vi.phys)

            elif isinstance(s, Apply):
                if s.gate in self.fns and self.fns[s.gate].name != "main":
                    callee = self.fns[s.gate]
                    if s.outs is None and fn_kind in {"Pauli","Clifford"} and callee.kind in {"Pauli","Clifford"}:
                        for a in s.args: env.require(a)
                        self._inline_unitary_noouts(env, buf, callee, s.args)
                    else:
                        self._inline_fn_call(env, buf, callee, s.args, s.outs, caller_kind=fn_kind)
                else:
                    if not (_is_unitary_gate(s.gate) or _is_known_transform(s.gate)):
                        raise NameError(f"unknown function or primitive '{s.gate}'")
                    for a in s.args: env.require(a)
                    if s.outs is not None:
                        for o in s.outs: env.require(o)
                    self._enforce_outs_rule(s.gate, s.args, s.outs)
                    self._emit_apply(env, buf, s.gate, s.args, s.outs)

            elif isinstance(s, QCtrlApply):
                ensure_kind("Clifford", "quantum control")
                ctrl_vi = env.require(s.ctrl, expect="Qdit")
                ctrl_phys = ctrl_vi.phys
                g = s.gate.upper()
                if g in {"X","Z"}:
                    if len(s.args) != 1: raise TypeError("ctrl arity")
                    tgt_phys = env.phys_of(s.args[0])
                    self._emit_qctrl_pauli_primitive(buf, ctrl_phys, g, tgt_phys)
                elif s.gate in self.fns:
                    callee = self.fns[s.gate]
                    if callee.kind == "Pauli":
                        self._inline_ctrl_over_pauli_fn(env, buf, ctrl_phys, callee, s.args,
                                                        emit_ctrl=self._emit_qctrl_pauli_primitive)
                    elif callee.kind == "Clifford":
                        raise TypeError("quantum control over @Clifford is not supported")
                    else:
                        raise TypeError(f"quantum control over @{callee.kind} not supported")
                else:
                    raise NameError(f"unknown gate/function '{s.gate}' in qctrl")

            elif isinstance(s, CCtrlApply):
                # cctrl over Pauli ⇒ Linear; cctrl over Clifford ⇒ Nonlinear (typechecked), but no codegen yet
                ensure_kind("Linear", "classical control")
                ctrl_vi = env.require(s.ctrl, expect="Dit")
                ctrl_phys = ctrl_vi.phys
                g = s.gate.upper()
                if g in {"X","Z"}:
                    if len(s.args) != 1: raise TypeError("ctrl arity")
                    self._emit_ctrl_pauli_primitive(buf, ctrl_phys, g, env.phys_of(s.args[0]))
                elif s.gate in self.fns:
                    callee = self.fns[s.gate]
                    if callee.kind == "Pauli":
                        self._inline_ctrl_over_pauli_fn(env, buf, ctrl_phys, callee, s.args,
                                                        emit_ctrl=self._emit_ctrl_pauli_primitive)
                    elif callee.kind == "Clifford":
                        raise TypeError("classically controlled @Clifford not available")
                    else:
                        raise TypeError(f"classical control over @{callee.kind} not supported")
                else:
                    raise NameError(f"unknown gate/function '{s.gate}' in cctrl")

            elif isinstance(s, IfStmt):
                # runtime selection by constant-folded cond
                take_then = bool(self.eval_expr(s.cond))
                self._compile_block(env, buf, s.then_body if take_then else s.else_body, fn_kind)

            elif isinstance(s, DaggerAs):
                if s.src not in self.fns: raise NameError(f"unknown function {s.src} in dagger")
                srcf = self.fns[s.src]
                if srcf.kind not in {"Pauli","Clifford"}:
                    raise TypeError("only Pauli or Clifford can be daggered")
                tmp_env = Env(dim=env.dim)
                for pname, pty in srcf.in_params:
                    if env.has(pname):
                        vi = env.require(pname, expect=pty if pty != "Bool" else None)
                        tmp_env.declare(pname, pty, phys=vi.phys)
                    else:
                        tmp_env.declare(pname, pty, phys=pname)
                ops = self._collect_unitary_ops(tmp_env, srcf, [p for p,_ in srcf.in_params])
                for gate,args in reversed(ops):
                    inv = self._invert_gate_token(gate, env.dim)
                    base = inv.split("_",1)[0].upper()
                    if base in UNITARY_GATES_1 or base in PARAM_UNITARY:
                        if len(args)!=1: raise TypeError("arity mismatch during dagger")
                        buf.add(f"{args[0]} *= {inv}")
                    elif base in UNITARY_GATES_2:
                        if len(args)!=2: raise TypeError("arity mismatch during dagger")
                        buf.add(f"({args[0]}, {args[1]}) *= {inv}")
                    else:
                        raise TypeError("unknown unitary during dagger")

            elif isinstance(s, (Return, AssertRel, PrintSPL)):
                pass

            else:
                raise ValueError("unknown statement")

    # ---- inline user-defined function call ----

    def _inline_fn_call(self, caller_env: Env, buf: SPLBuffer,
                        callee: FnDecl, arg_names: List[str], outs: Optional[List[str]],
                        caller_kind: Optional[str]):
        if callee.name in self._call_stack:
            cycle = " -> ".join(self._call_stack + [callee.name])
            raise RecursionError(f"cyclic call graph not allowed: {cycle}")
        if len(arg_names) != len(callee.in_params):
            exp = [p for (p, _) in callee.in_params]
            raise TypeError(f"call arity mismatch to {callee.name}: got {len(arg_names)} arg(s) {arg_names}, expected {len(exp)} {exp}")

        # kind check
        if caller_kind is not None:
            allowed = _KIND_LEQ.get(caller_kind, set())
            if callee.kind not in allowed:
                raise TypeError(f"@{caller_kind} cannot call @{callee.kind} ({caller_kind} lacks privileges)")

        # outs presence
        if callee.out_types and outs is None:
            raise TypeError(f"call to {callee.name} must specify outs via '-> ...'")
        if not callee.out_types and outs is not None:
            raise TypeError(f"call to {callee.name} has no returns; outs must be omitted")

        # returns (names within callee)
        ret_names, _ = self._resolve_outputs_of_fn(callee)
        if len(callee.out_types) != len(ret_names):
            raise TypeError(f"{callee.name}: implicit/explicit return arity {len(ret_names)} != declared {len(callee.out_types)}")

        # temp env sharing allocation set
        tmp = Env(dim=caller_env.dim)
        tmp.declared_phys = caller_env.declared_phys

        # bind parameters
        for (pname, pty), actual in zip(callee.in_params, arg_names):
            vi = caller_env.require(actual, expect=pty if pty != "Bool" else None)
            tmp.declare(pname, pty, phys=vi.phys)

        # compile callee
        self._call_stack.append(callee.name)
        try:
            self._compile_block(tmp, buf, callee.body, callee.kind)
        finally:
            self._call_stack.pop()

        # materialize outs in caller
        if outs:
            if len(outs) != len(callee.out_types):
                raise TypeError(f"call to {callee.name}: outs arity {len(outs)} != {len(callee.out_types)}")
            for cal_log, out_name, out_ty in zip(ret_names, outs, callee.out_types):
                if not tmp.has(cal_log):
                    raise TypeError(f"{callee.name} did not produce return '{cal_log}'")
                cal_vi = tmp.require(cal_log)
                if caller_env.has(out_name):
                    caller_env.rename(out_name, out_ty, cal_vi.phys)
                else:
                    caller_env.declare(out_name, out_ty, phys=cal_vi.phys)

    # ---- compile function ----

    def compile_function_to_spl(self, fn: FnDecl) -> str:
        if fn.name == "main":
            raise ValueError("main is not compiled to SPL")
        # typecheck against inferred kind
        self._check_declared_kind(fn)

        env = Env(dim=self.dim)
        buf = SPLBuffer()

        # seed inputs in context
        for name, ty in fn.in_params:
            env.declare(name, ty, phys=name)
            buf.ctx[name] = self.ctx_of(ty)

        # compile body
        self._compile_block(env, buf, fn.body, fn.kind)

        # resolve outputs (explicit vs implicit)
        out_vars, explicit = self._resolve_outputs_of_fn(fn)

        if len(fn.out_types) > 0:
            if len(out_vars) != len(fn.out_types):
                raise TypeError(f"implicit/explicit return arity {len(out_vars)} != declared {len(fn.out_types)}")
            for name, needed_ty in zip(out_vars, fn.out_types):
                vi = env.require(name)
                if vi.ty != needed_ty:
                    raise TypeError(f"return variable {name} has type {vi.ty}, expected {needed_ty}")

        # If explicit return: discard everything not returned (project away)
        if explicit:
            keep = set(out_vars)
            keep_phys = {env.phys_of(v) for v in keep if env.has(v)}
            all_phys = {vi.phys for vi in env.vars.values()}
            to_disc = [p for p in all_phys if p not in keep_phys]
            for p in to_disc:
                buf.add(f"disc {p}")

        return buf.render()


def _is_unitary_gate(g: str) -> bool:
    base = g.split("_",1)[0].upper()
    return (base in UNITARY_GATES_1) or (base in UNITARY_GATES_2) or (base in PARAM_UNITARY)


def _is_known_transform(name: str) -> bool:
    n = name.lower()
    return (n in CLASSICAL_ASSIGN) or (n in {"meas","prep"})


def _primitive_kind(g: str) -> Optional[str]:
    base = g.split("_",1)[0].upper()
    if base in {"X","Z"}: return "Pauli"
    if base in {"F","S","T","CX","SWAP"}: return "Clifford"
    if base == "MUL": return "Clifford"
    return None


def _is_pauli_primitive(g: str) -> bool:
    return g.split("_",1)[0].upper() in {"X","Z"}


def _rref(A, p):
    A = [row[:] for row in A]
    m = len(A); n = len(A[0]) if A else 0
    r = 0
    for c in range(n):
        piv = next((i for i in range(r, m) if A[i][c] % p != 0), None)
        if piv is None: continue
        A[r], A[piv] = A[piv], A[r]
        inv = pow(A[r][c] % p, -1, p)
        for j in range(c, n): A[r][j] = (A[r][j]*inv) % p
        for i in range(m):
            if i == r: continue
            f = A[i][c] % p
            if f:
                for j in range(c, n):
                    A[i][j] = (A[i][j] - f*A[r][j]) % p
        r += 1
        if r == m: break
    return A


def _in_span(p, cols, v):
    d = len(v); k = len(cols)
    if k == 0: return all((vi % p) == 0 for vi in v)
    M = [[cols[j][i] % p for j in range(k)] for i in range(d)]
    Aug = [M[i][:] + [v[i] % p] for i in range(d)]
    R = _rref(Aug, p)
    for i in range(d):
        if all(R[i][j] == 0 for j in range(k)) and (R[i][k] % p != 0):
            return False
    return True


def _cols(rows):
    if not rows: return []
    d = len(rows); k = len(rows[0])
    return [[rows[i][j] for i in range(d)] for j in range(k)]


def _affine_compare(R1, R2, subset: bool) -> bool:
    if R1.p != R2.p or R1.n_in != R2.n_in or R1.n_out != R2.n_out:
        return False
    p = R1.p
    if [x % p for x in R1.subspace.shift] != [x % p for x in R2.subspace.shift]:
        return False
    cols1 = _cols(R1.subspace.basis)
    cols2 = _cols(R2.subspace.basis)
    def span_in(A, B):
        for v in A:
            if not _in_span(p, B, v): return False
        return True
    return span_in(cols1, cols2) if subset else (span_in(cols1, cols2) and span_in(cols2, cols1))





# ===== inlined former typechecker =====
from typing import *
from ..parser.ast import *

