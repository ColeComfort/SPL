import pytest
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl import interpret as interpret_spl

SRC = """
context { u: pit; v: pit }
init a; init b;
b = sum * (a, v);
qinit c;
c *= Z;           % quantum chunk
b = plusone * b;  % function chunk
a = sum * (a, b);   % affine chunk again
disc b;
"""

def test_alternating_chunks_runs_fp3():
    prog = spl_parser.parse_spl(SRC) if hasattr(spl_parser, 'parse_spl') else spl_parser.parse(SRC)
    env, rel = interpret_spl(3, prog, context={"u":1, "v":2})
    assert rel.p == 3
    assert rel.n_in == 2
