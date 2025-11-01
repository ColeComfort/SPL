# run_controlled_pauli_test.py
# Compile controlled_pauli_test.spl++ with SPL++ (splpp) → SPL,
# pretty-print SPL AST, then interpret as an affine relation over F_p.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

P = 5  # prime dimension

TARGET_FUNS = [
    "test_cctrl_paulis",
    "test_cctrl_Y",
    "test_qctrl_paulis",
    "test_qctrl_Y",
]

def compile_fn(qsrc: str, p: int, fn_name: str) -> str:
    import splpp
    prog = splpp.parse_splpp(qsrc)
    fns = {d.name: d for d in prog.decls}
    if fn_name not in fns:
        raise ValueError(f"{fn_name} not found in controlled_pauli_test.spl++")
    comp = splpp.Compiler(dim=p, fns=fns)
    return comp.compile_function_to_spl(fns[fn_name])

def interpret_spl(p: int, spl_code: str):
    from spl.src.parser.parser import parse_spl
    from interpret_spl_affine import interpret as interpret_aff
    spl_ast = parse_spl(spl_code)
    print("=== SPL (compiled) ===")
    print(spl_ast)
    env, rel = interpret_aff(p, spl_ast, context=(spl_ast.context or {}))
    print("=== Affine relation summary ===")
    print(f"p={rel.p}  n_in={rel.n_in}  n_out={rel.n_out}")
    try:
        print(rel.to_kernel_str())
    except Exception:
        print(rel)

def main():
    src_path = ROOT / "controlled_pauli_test.spl++"
    qsrc = src_path.read_text(encoding="utf-8")
    for name in TARGET_FUNS:
        print("\n" + "="*80)
        print(f"## Function: {name}")
        print("="*80)
        spl_code = compile_fn(qsrc, P, name)
        interpret_spl(P, spl_code)

if __name__ == "__main__":
    main()

