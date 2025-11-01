#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#WIP

import argparse, ast, random
from typing import List, Tuple

from spl.src.parser.parser import parse_spl
from interpret_spl import interpret                 # dispatcher
from spl.src.relations.affine_relations import rref                   # used for affine detectability only

# ---------- Encoder / Decoder / Measurement ----------
ENCODER_SPL = r"""
qinit a
qinit b
qinit c
qinit d

a *= F ; a *= F ; a *= F
b *= F ; b *= F ; b *= F
c *= F ; c *= F ; c *= F
d *= F ; d *= F ; d *= F

(d, x) *= CX
d *= S ; d *= S
x *= F ; x *= F ; x *= F
(c, d) *= CX
(c, x) *= CX

c *= S ; c *= S
d *= S ; d *= S
x *= S ; x *= S
(b, x) *= CX
(b, d) *= CX

b *= S ; b *= S
c *= F ; c *= F ; c *= F
d *= F ; d *= F ; d *= F
(a, b) *= CX
(a, c) *= CX

(a, x) *= CX
b *= S ; b *= S
c *= F ; c *= F ; c *= F
x *= S ; x *= S
a *= F ; a *= F ; a *= F
"""

DECODER_SPL = r"""
a *= F ; a *= F ; a *= F
x *= S ; x *= S
c *= F ; c *= F ; c *= F
b *= S ; b *= S
(a, x) *= CX ; (a, x) *= CX

(a, c) *= CX ; (a, c) *= CX
(a, b) *= CX ; (a, b) *= CX
d *= F ; d *= F ; d *= F
c *= F ; c *= F ; c *= F
b *= S ; b *= S

(b, d) *= CX ; (b, d) *= CX
(b, x) *= CX ; (b, x) *= CX
x *= S ; x *= S
d *= S ; d *= S
c *= S ; c *= S

(c, x) *= CX ; (c, x) *= CX
(c, d) *= CX ; (c, d) *= CX
x *= F ; x *= F ; x *= F
d *= S ; d *= S
(d, x) *= CX ; (d, x) *= CX
"""

SYNDROME_SPL = r"""
meas a
meas b
meas c
meas d
"""

# ---------- Helpers ----------
PHYS_ORDER = ["x", "a", "b", "c", "d"]

def pauli_error_spl(p: int, paulis: List[Tuple[int,int]]) -> str:
    lines: List[str] = []
    for name, (xe, ze) in zip(PHYS_ORDER, paulis):
        kx = int(xe) % p
        kz = int(ze) % p
        for _ in range(kx): lines.append(f"{name} *= X")
        for _ in range(kz): lines.append(f"{name} *= Z")
    return ("\n".join(lines) + "\n") if lines else ""

def parse_pauli_arg(arg: str, p: int) -> List[Tuple[int,int]]:
    if not arg: return [(random.randrange(p), random.randrange(p)) for _ in range(5)]
    t = ast.literal_eval(arg)
    if not isinstance(t, (list, tuple)): raise ValueError("Pauli must be list/tuple of pairs")
    out: List[Tuple[int,int]] = []
    for it in t:
        if not (isinstance(it, (list, tuple)) and len(it)==2): raise ValueError(f"Bad pair {it}")
        out.append((int(it[0])%p, int(it[1])%p))
        if len(out)==5: break
    while len(out)<5: out.append((0,0))
    return out

def detectable_from_affine_relation(rel) -> bool:
    # 0 ∉ s_out + Im(B_out)  ⟺  [B_out | -s_out] inconsistent
    p = rel.p
    n, m = rel.n_in, rel.n_out
    if m == 0: return False
    s = [v % p for v in rel.subspace.shift]
    s_out = [s[n+i] for i in range(m)]
    B = rel.subspace.basis
    if not B or len(B[0])==0: return any(v % p != 0 for v in s_out)
    r = len(B[0])
    B_out = [[B[n+i][j] % p for j in range(r)] for i in range(m)]
    Aug = [B_out[i][:] + [(-s_out[i]) % p] for i in range(m)]
    R, _ = rref(Aug, p)
    return any(all(R[i][j]%p==0 for j in range(r)) and (R[i][r]%p!=0) for i in range(len(R)))

# ---------- Programs ----------
def compose_detection_program(p: int, paulis: List[Tuple[int,int]]) -> str:
    # Context with a single input qudit
    ctx = "context { x: qpit }\n\n"
    return ctx + ENCODER_SPL + "\n% --- Pauli error ---\n" + pauli_error_spl(p, paulis) \
           + "% --- decoder ---\n" + DECODER_SPL + "\n% --- syndrome extraction ---\n" + SYNDROME_SPL

def nonlinear_correction_block() -> str:
    return r"""
        % --- nonlinear flags on the measured syndrome (a,b,c,d are classical now) ---
        init s_ab
        init s_cd
        s_ab = mul * (a, b)
        s_cd = mul * (c, d)

        init f1
        init f2
        f1 = sum * (a, b)
        f2 = sum * (c, d)

        init g
        g = mul * (f1, f2)

        % --- classically-controlled Pauli corrections on the data qudit x ---
        ctrlX s_ab x
        ctrlZ s_cd x
        ctrlX g x
        
        disc a
        disc b
        disc c
        disc d
        disc s_ab
        disc s_cd
        disc f1
        disc f2
        disc g
        """


def compose_correction_program(p: int, paulis: List[Tuple[int,int]]) -> str:
    # Same pipeline plus nonlinear correction after measuring syndrome
    ctx = "context { x: qpit }\n\n"
    return ctx + ENCODER_SPL + "\n% --- Pauli error ---\n" + pauli_error_spl(p, paulis) \
           + "% --- decoder ---\n" + DECODER_SPL + "\n% --- syndrome extraction ---\n" + SYNDROME_SPL \
           + "\n% --- nonlinear correction using mul and control ---\n" + nonlinear_correction_block()

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="[[5,1,3]]_p: detection only, then detection + nonlinear correction.")
    ap.add_argument("pauli", nargs="?", default="", help="Python literal like '((1,2),(2,0),(1,1))'; pads to 5 wires")
    ap.add_argument("--p", type=int, default=3, help="prime p for F_p (default 3)")
    ap.add_argument("--print-spl", action="store_true")
    args = ap.parse_args()

    p = int(args.p)
    paulis = parse_pauli_arg(args.pauli, p)

    # 1) Detection-only (affine)
    spl_det = compose_detection_program(p, paulis)
    prog_det = parse_spl(spl_det)
    env_det, rel_det = interpret(p, prog_det)   # dispatcher stays affine (no mul)

    if args.print_spl:
        print("=== DETECTION-ONLY SPL ===")
        print(spl_det)

    print("=== DETECTION-ONLY RELATION (affine) ===")
    print(rel_det)
    if hasattr(rel_det, "to_kernel_str"):
        print("\n--- kernel view ---")
        print(rel_det.to_kernel_str())
    print(f"\nDetectable? {detectable_from_affine_relation(rel_det)}")

    # 2) Detection + nonlinear correction (sets)
    spl_fix = compose_correction_program(p, paulis)
    prog_fix = parse_spl(spl_fix)
    env_fix, rel_fix = interpret(p, prog_fix)   # dispatcher switches to sets (mul present)

    if args.print_spl:
        print("\n=== DETECTION+CORRECTION SPL ===")
        print(spl_fix)

    print("\n=== DETECTION+CORRECTION RELATION (sets backend) ===")
    print(rel_fix)
    print(f"\nSummary: p={p}, detection domain={rel_det.n_in}, detection codomain={rel_det.n_out}; "
          f"corrected domain={rel_fix.n_in}, corrected codomain={rel_fix.n_out}")
    print("Detectability skipped on corrected relation (nonlinear).")

if __name__ == "__main__":
    main()

