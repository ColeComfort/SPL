# run_teleportation.py
# Compile teleportation.spl++ with SPL++ (qdsl) → SPL, pretty-print SPL AST,
# then interpret as an affine relation over F_p.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

P = 5  # prime dimension for both compilation and affine interpretation

def compile_splpp_to_spl(qsrc: str, p: int) -> str:
    import splpp  # your SPL++ compiler module (provides parse_qdsl, Compiler)
    prog = splpp.parse_splpp(qsrc)              # -> Program(dim, decls)
    fns = {d.name: d for d in prog.decls}     # name -> FnDecl
    if "teleport" not in fns:
        raise ValueError("teleportation.spl++ must define fn teleport(...)")
    # IMPORTANT: pass the full function map so user-defined calls inline correctly.
    comp = splpp.Compiler(dim=p, fns=fns)
    return comp.compile_function_to_spl(fns["teleport"])

def main():
    src_path = ROOT / "teleportation.spl++"
    splpp = src_path.read_text(encoding="utf-8")

    # Compile SPL++ → SPL
    spl_code = compile_splpp_to_spl(splpp, P)

    # Pretty-print SPL via its AST
    from spl.src.parser.parser import parse_spl
    spl_ast = parse_spl(spl_code)
    print("=== SPL (compiled) ===")
    print(spl_ast)

    # Interpret as an affine relation over F_P
    from interpret_spl_affine import interpret as interpret_aff
    env, rel = interpret_aff(P, spl_ast, context=(spl_ast.context or {}))

    print("=== Affine relation summary ===")
    print(f"p={rel.p}  n_in={rel.n_in}  n_out={rel.n_out}")
    try:
        print(rel.to_kernel_str())
    except Exception:
        print(rel)

if __name__ == "__main__":
    main()

