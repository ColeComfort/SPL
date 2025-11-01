# spl_parser.py
# Parser for the Stabiliser Programming Language (SPL)
# Requires: pip install lark

from dataclasses import dataclass
from typing import List, Union, Dict, Optional
from lark import Lark, Transformer, v_args, Token

# ===================== GRAMMAR =====================

GRAMMAR = r"""
    start: program

    // program = optional context block, then statements
    program: _SEP* (context_block _SEP*)? stmt (_SEP+ stmt)* _SEP*

    // context
    context_block: "context" "{" _SEP* ctx_entry (_SEP+ ctx_entry)* _SEP* "}"
    ctx_entry: IDENT ":" IDENT                         -> ctx_pair

    ?stmt: "skip"                                      -> skip
         | "init" reg                                  -> init
         | "qinit" reg                                 -> qinit
         | "disc" reg                                  -> disc
         | "discard" reg                               -> disc
         | "meas" reg                                  -> meas
         | reg "*=" gate_atom                          -> apply_gate
         | reg "=" IDENT "*" reg                       -> affine_assign
         | "ctrl" IDENT reg reg                        -> ctrl_generic
         | "ctrlX" reg reg                             -> ctrl_x
         | "ctrlZ" reg reg                             -> ctrl_z

    // Gate atoms:
    // - MUL has a subscript parameter: MUL_k or MUL_{k}
    //   Also accept IDENT SIGNED_INT when IDENT ends with "MUL_"
    // - All other gates have a superscript repetition: G^n or G^{n}
    ?gate_atom: IDENT                                  -> gate_bare
              | "MUL" "_" SIGNED_INT                   -> mul_param
              | "MUL" "_" "{" SIGNED_INT "}"           -> mul_param
              | IDENT SIGNED_INT                       -> mul_param_noscore
              | IDENT "{" SIGNED_INT "}"               -> mul_param_noscore
              | IDENT "^" SIGNED_INT                   -> gate_pow
              | IDENT "^" "{" SIGNED_INT "}"           -> gate_pow

    ?reg: IDENT                                        -> reg_single
        | "(" ident_list ")"                           -> reg_tuple
    ident_list: IDENT ("," IDENT)*

    // separators: semicolon or newline(s)
    _SEP: ";" | _NEWLINE
    _NEWLINE: /(\r?\n)+/

    %import common.CNAME -> IDENT
    SIGNED_INT: /[+-]?[0-9]+/
    %import common.WS_INLINE
    %ignore WS_INLINE

    COMMENT: "%" /[^\n]*/
    %ignore COMMENT
"""

# ===================== AST DEFINITIONS =====================

Reg = Union[str, List[str]]  # a single name or a list of names

def _pp_reg(r: Reg) -> str:
    return "(" + ", ".join(r) + ")" if isinstance(r, list) else r

@dataclass
class Skip:
    def __str__(self) -> str:
        return "skip"
    __repr__ = __str__

@dataclass
class Init:
    reg: Reg
    def __str__(self) -> str:
        return f"init {_pp_reg(self.reg)}"
    __repr__ = __str__

@dataclass
class QInit:
    reg: Reg
    def __str__(self) -> str:
        return f"qinit {_pp_reg(self.reg)}"
    __repr__ = __str__

@dataclass
class Discard:
    reg: Reg
    def __str__(self) -> str:
        return f"disc {_pp_reg(self.reg)}"
    __repr__ = __str__

@dataclass
class Meas:
    reg: Reg
    def __str__(self) -> str:
        return f"meas {_pp_reg(self.reg)}"
    __repr__ = __str__

@dataclass
class ApplyGate:
    reg: Reg
    gate: str
    def __str__(self) -> str:
        return f"{_pp_reg(self.reg)} *= {self.gate}"
    __repr__ = __str__

@dataclass
class AffineAssign:
    dst: Reg
    transform: str
    src: Reg
    def __str__(self) -> str:
        return f"{_pp_reg(self.dst)} = {self.transform} * {_pp_reg(self.src)}"
    __repr__ = __str__

@dataclass
class Ctrl:
    pauli: str
    ctrl: Reg
    target: Reg
    def __str__(self) -> str:
        tag = f"ctrl{self.pauli}" if self.pauli in {"X", "Z"} else f"ctrl {self.pauli}"
        return f"{tag} {_pp_reg(self.ctrl)} {_pp_reg(self.target)}"
    __repr__ = __str__

# ===================== PROGRAM =====================

def _names_of(r: Reg) -> List[str]:
    return r if isinstance(r, list) else [r]

def _set_all(env: Dict[str, str], names: List[str], ty: str) -> None:
    for n in names:
        env[n] = ty

def _pairwise_set(env: Dict[str, str], dsts: List[str], srcs: List[str], default_ty: str) -> None:
    m = min(len(dsts), len(srcs))
    for i in range(m):
        src_name = srcs[i]
        env[dsts[i]] = env.get(src_name, default_ty)
    for j in range(m, len(dsts)):
        env[dsts[j]] = default_ty

def _pp_env_inline(env: Dict[str, str]) -> str:
    if not env:
        return "{}"
    return "{" + ", ".join(f"{k}: {v}" for k, v in sorted(env.items())) + "}"

@dataclass
class Program:
    stmts: List[object]
    context: Optional[Dict[str, str]] = None  # e.g. {"a":"pit", "q":"qpit"}

    def _compute_final_env(self) -> Dict[str, str]:
        env: Dict[str, str] = dict(self.context or {})
        for s in self.stmts:
            if isinstance(s, Init):
                _set_all(env, _names_of(s.reg), "pit")
            elif isinstance(s, QInit):
                _set_all(env, _names_of(s.reg), "qpit")
            elif isinstance(s, Meas):
                _set_all(env, _names_of(s.reg), "pit")
            elif isinstance(s, Discard):
                for n in _names_of(s.reg):
                    env.pop(n, None)
            elif isinstance(s, AffineAssign):
                _pairwise_set(env, _names_of(s.dst), _names_of(s.src), default_ty="pit")
            elif isinstance(s, (ApplyGate, Ctrl, Skip)):
                pass
        return env

    def pretty(self) -> str:
        lines: List[str] = []
        lines.append(f"{_pp_env_inline(self.context or {})} ⊢")
        lines.extend(str(s) for s in self.stmts)
        lines.append(f"▶ {_pp_env_inline(self._compute_final_env())}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.pretty()

    def __repr__(self) -> str:
        return self.pretty()

# ===================== TRANSFORMER =====================

@v_args(inline=True)
class ToAST(Transformer):
    def start(self, program):
        return program

    def program(self, *parts):
        ctx: Dict[str, str] = {}
        stmts: List[object] = []
        for part in parts:
            if isinstance(part, dict):
                ctx.update(part)
            elif isinstance(part, list):
                stmts.extend(part)
            else:
                stmts.append(part)
        return Program(stmts=stmts, context=(ctx if ctx else None))

    # context
    def context_block(self, *pairs):
        d: Dict[str, str] = {}
        for k, v in pairs:
            d[k] = v
        return d

    def ctx_pair(self, name_tok: Token, ty_tok: Token):
        return (str(name_tok), str(ty_tok))

    # statements
    def skip(self):
        return Skip()

    def init(self, r):
        return Init(r)

    def qinit(self, r):
        return QInit(r)

    def disc(self, r):
        return Discard(r)

    def meas(self, r):
        return Meas(r)

    # gate atoms
    def gate_bare(self, name_tok: Token):
        return str(name_tok)

    @v_args(inline=True)
    def mul_param(self, _mul_tok: Token, num_tok: Token):
        return f"MUL_{str(num_tok)}"

    @v_args(inline=True)
    def mul_param_noscore(self, name_tok: Token, num_tok: Token):
        # Accept IDENT SIGNED_INT when IDENT ends with 'MUL_' (lexer fused 'MUL_')
        name = str(name_tok)
        num  = str(num_tok)
        if name.upper().endswith("MUL_"):
            return f"MUL_{num}"
        return name  # fallback as bare gate

    @v_args(inline=True)
    def gate_pow(self, name_tok: Token, num_tok: Token):
        name = str(name_tok)
        if name.upper() == "MUL":
            raise ValueError("Use subscript for MUL (e.g., MUL_3), not superscript.")
        return f"{name}^{str(num_tok)}"

    def apply_gate(self, r, gate_atom_str):
        return ApplyGate(reg=r, gate=str(gate_atom_str))

    def affine_assign(self, dst, A_tok, src):
        return AffineAssign(dst=dst, transform=str(A_tok), src=src)

    def ctrl_generic(self, P_tok: Token, r_ctrl, r_tgt):
        return Ctrl(pauli=str(P_tok), ctrl=r_ctrl, target=r_tgt)

    def ctrl_x(self, r_ctrl, r_tgt):
        return Ctrl(pauli="X", ctrl=r_ctrl, target=r_tgt)

    def ctrl_z(self, r_ctrl, r_tgt):
        return Ctrl(pauli="Z", ctrl=r_ctrl, target=r_tgt)

    # registers
    def reg_single(self, name_tok: Token):
        return str(name_tok)

    def reg_tuple(self, idlist):
        return idlist

    def ident_list(self, first: Token, *rest: Token):
        return [str(first)] + [str(tok) for tok in rest]

# ===================== PARSER SETUP =====================

_parser = Lark(GRAMMAR, parser="lalr", start="start", maybe_placeholders=False)

def parse_spl(src: str) -> 'Program':
    """Parse SPL source into an AST Program with optional context."""
    tree = _parser.parse(src)
    return ToAST().transform(tree)

# ===================== PRETTY PRINT =====================

def pretty(stmt) -> str:
    if isinstance(stmt, Skip):
        return "skip"
    if isinstance(stmt, Init):
        return f"init {_pp_reg(stmt.reg)}"
    if isinstance(stmt, QInit):
        return f"qinit {_pp_reg(stmt.reg)}"
    if isinstance(stmt, Discard):
        return f"disc {_pp_reg(stmt.reg)}"
    if isinstance(stmt, Meas):
        return f"meas {_pp_reg(stmt.reg)}"
    if isinstance(stmt, ApplyGate):
        return f"{_pp_reg(stmt.reg)} *= {stmt.gate}"
    if isinstance(stmt, AffineAssign):
        return f"{_pp_reg(stmt.dst)} = {stmt.transform} * {_pp_reg(stmt.src)}"
    if isinstance(stmt, Ctrl):
        return f"ctrl{stmt.pauli} {_pp_reg(stmt.ctrl)} {_pp_reg(stmt.target)}"
    return repr(stmt)

def pretty_program(p: 'Program') -> str:
    lines: List[str] = []
    if p.context:
        lines.append("context {")
        for k, v in p.context.items():
            lines.append(f"  {k}: {v}")
        lines.append("}")
    lines.extend(pretty(s) for s in p.stmts)
    return ";\n".join(lines)

# ===================== DEMO =====================

if __name__ == "__main__":
    demo = r"""
        context {
          a: pit
          q: qpit
        }

        qinit in
        qinit x
        qinit out
        (x, out) *= CX^1
        (in, x) *= CX^1
        in *= F^1
        meas in
        meas x
        ctrlZ in out
        ctrlX x out
        discard in
        discard x

        % parameterized gates
        qinit r
        r *= X^{-3}
        r *= S^{-7}
        r *= T^12
        (q, r) *= CX^{-5}
        r *= MUL_-2
    """
    ast = parse_spl(demo)
    print("AST:", ast)
    print("\nPretty:\n", ast)

