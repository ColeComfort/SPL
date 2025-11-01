#!/usr/bin/env python3
import argparse, pathlib, sys
from splpp import parse_splpp, compile_text_fn
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl_affine import interpret

def main():
    ap = argparse.ArgumentParser(description="Compile an .spl++ file and interpret selected function as a relation via SPL affine interpreter")
    ap.add_argument("file", help="path to .spl++ file")
    ap.add_argument("--fn", default="main", help="function name to interpret (default: main)")
    args = ap.parse_args()
    src = pathlib.Path(args.file).read_text()
    # Compile SPL++ function to SPL text
    spl_src = compile_text_fn(src, args.fn)
    # Parse and interpret SPL as relation
    prog = spl_parser.parse_spl(spl_src) if hasattr(spl_parser, "parse_spl") else spl_parser.parse(spl_src)
    env, rel = interpret(prog)
    print(rel.to_kernel_str())
if __name__ == "__main__":
    main()
