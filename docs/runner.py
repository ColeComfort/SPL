# Connects the in-browser UI to your SPL interpreter.

def run_spl(src: str) -> str:
    # Import inside function so errors surface in the UI.
    import sys
    if "/" not in sys.path:
        sys.path.insert(0, "/")

    from spl.src.parser.parser import parse_spl
    from spl.src.interpreter.interpret_spl import interpret_spl

    prog = parse_spl(src)
    out = interpret_spl(prog)
    return out if isinstance(out, str) else str(out)

