#!/usr/bin/env python3
import argparse, pathlib, sys
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl_affine import interpret
# interpret returns (env, relation) in your codebase
def main():
    ap = argparse.ArgumentParser(description="Interpret an .spl file as an affine relation")
    ap.add_argument("file", help="path to .spl file")
    ap.add_argument("--p", type=int, default=3, help="prime dimension p (default: 2)")
    args = ap.parse_args()
    src = pathlib.Path(args.file).read_text()
    prog = spl_parser.parse_spl(src) if hasattr(spl_parser, "parse_spl") else spl_parser.parse(src)
    env, rel = interpret(args.p, prog)
    print(rel.to_kernel_str())
if __name__ == "__main__":
    main()
