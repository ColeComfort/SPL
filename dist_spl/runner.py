# Auto-discover parser & interpreter entry points at runtime.

from __future__ import annotations
import importlib
from types import ModuleType
from typing import Callable, Optional, Tuple

_PARSER_CANDIDATES = [
    ("spl.src.parser.parser",         ["parse_spl", "parse"]),
]

_INTERP_CANDIDATES = [
    # most likely
    ("spl.src.interpreter.interpret_spl",        ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
    # fallbacks
    ("spl.src.interpreter",                      ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
    ("spl.interpreter",                          ["interpret_spl", "interpret_program", "interpret_to_text", "interpret", "run"]),
]

def _first_callable(modname: str, names: list[str]) -> Optional[Tuple[ModuleType, str, Callable]]:
    try:
        m = importlib.import_module(modname)
    except Exception:
        return None
    for n in names:
        fn = getattr(m, n, None)
        if callable(fn):
            return (m, n, fn)
    return None

def _resolve() -> Tuple[Callable[[str], object], Callable[[object], object], str, str]:
    parser_fn = None
    parser_where = ""
    for mod, names in _PARSER_CANDIDATES:
        hit = _first_callable(mod, names)
        if hit:
            _, n, fn = hit
            parser_fn = fn
            parser_where = f"{mod}.{n}"
            break
    if parser_fn is None:
        raise ImportError(f"Could not find parser; tried: " + "; ".join(f"{m}.{names}" for m,names in _PARSER_CANDIDATES))

    interp_fn = None
    interp_where = ""
    for mod, names in _INTERP_CANDIDATES:
        hit = _first_callable(mod, names)
        if hit:
            _, n, fn = hit
            interp_fn = fn
            interp_where = f"{mod}.{n}"
            break
    if interp_fn is None:
        raise ImportError(f"Could not find interpreter; tried: " + "; ".join(f"{m}.{names}" for m,names in _INTERP_CANDIDATES))

    return parser_fn, interp_fn, parser_where, interp_where

# Resolve once and cache
try:
    _PARSER, _INTERP, _PW, _IW = _resolve()
except Exception as e:
    _PARSER = _INTERP = None
    _ERR = e
else:
    _ERR = None

def run_spl(src: str) -> str:
    if _ERR is not None:
        raise _ERR
    prog = _PARSER(src)
    out = _INTERP(prog)
    return out if isinstance(out, str) else str(out)
