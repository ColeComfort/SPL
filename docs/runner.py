# Browser glue. Uses the interpreter packaged inside /spl-run.pyz.

def run_spl(src: str) -> str:
    import sys
    if "/spl-run.pyz" not in sys.path:
        sys.path.insert(0, "/spl-run.pyz")

    # Import from modules inside the zipapp
    from spl.src.parser.parser import parse_spl
    from spl.src.interpreter.interpret_spl import interpret_spl

    prog = parse_spl(src)
    out = interpret_spl(prog)
    return out if isinstance(out, str) else str(out)

