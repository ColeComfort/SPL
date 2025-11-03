def run_spl(src: str) -> str:
    from spl.src.parser.parser import parse_spl
    from spl.src.interpreter.interpret_spl import interpret_spl
    prog = parse_spl(src)
    out = interpret_spl(prog)
    return out if isinstance(out, str) else str(out)
