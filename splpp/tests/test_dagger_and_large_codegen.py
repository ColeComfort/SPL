import pytest
from splpp import compile_text_fn, parse_splpp

SRC = """
dim 3;

// simple linear function
@Linear fn inc(x: Dit) -> Dit {
    init y;
    apply PlusOne(x) -> y;
    return y;
}

// use dagger syntax; here we only test that the parser accepts it
fn main() {
    dagger inc as inc_dag;
    print spl inc;
}
"""

def test_dagger_parses_and_printspl_generates_spl():
    P = parse_splpp(SRC)
    # compile_text_fn on non-main should produce SPL text
    spl_inc = compile_text_fn(SRC, "inc")
    assert "apply" in spl_inc or "init" in spl_inc
