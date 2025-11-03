import pytest
from spl.src.parser import parser as spl_parser
from spl.src.interpreter.interpret_spl import interpret as interpret_spl

# This program alternates affine assignments and classical function-like chunks
SRC = """
context { x: pit; y: pit }
init a; init b;    % function chunk seeds
qinit c;
b = sum * (a, y);    % sum(a,y) -> b
c *= X;            % quantum gate sits in affine/quantum chunk
b = plusone * b;   % function chunk op
disc a;            % drop temp
"""

def test_mixed_affine_sets_functions_runs():
    prog = spl_parser.parse_spl(SRC) if hasattr(spl_parser, 'parse_spl') else spl_parser.parse(SRC)
    env, rel = interpret_spl(3, prog, context={"x":"pit", "y":"qpit"})
    # Domain is context only -> n_in == 2, m_out equals live outs after program
    assert rel.p == 3
    assert rel.n_in == 2
