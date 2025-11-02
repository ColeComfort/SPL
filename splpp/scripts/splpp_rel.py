#!/usr/bin/env python3
import argparse, pathlib, sys
from splpp import parse_splpp, compile_text_fn
from splpp.src.parser.ast import run_assertions_via_spl, Program, PrintSPL, functions_by_name, Compiler
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine

def _print_reports_for_main(prog: Program):
    reports = []
    # 1) assertions
    reports.extend(run_assertions_via_spl(prog))
    # 2) print spl directives
    fns = functions_by_name(prog)
    comp = Compiler(prog.dim or 2, fns=fns)
    main = fns.get("main")
    if main:
        for s in main.body:
            if isinstance(s, PrintSPL):
                fn = fns.get(s.fn_name)
                if not fn:
                    reports.append(f"[PRINT] unknown function {s.fn_name}")
                    continue
                spl_txt = comp.compile_function_to_spl(fn)
                reports.append(f"[PRINT] SPL for {s.fn_name}:")
                reports.append(spl_txt.rstrip())
    return reports

def main():
    ap = argparse.ArgumentParser(description="Compile an .spl++ program and either print SPL or interpret selected function as a relation")
    ap.add_argument("file", help="path to .spl++ file")
    ap.add_argument("--fn", default="main", help="function name to interpret (default: main)")
    ap.add_argument("--p", type=int, default=2, help="prime p for F_p")
    args = ap.parse_args()
    src = pathlib.Path(args.file).read_text()
    P = parse_splpp(src)
    if args.fn == 'main':
        for line in _print_reports_for_main(P):
            print(line)
        return
    # Compile one function to SPL then interpret affine
    spl_src = compile_text_fn(src, args.fn)
    prog = spl_parser.parse_spl(spl_src) if hasattr(spl_parser, "parse_spl") else spl_parser.parse(spl_src)
    env, rel = interpret_affine(args.p, prog)
    print(rel.to_kernel_str())

if __name__ == "__main__":
    main()
