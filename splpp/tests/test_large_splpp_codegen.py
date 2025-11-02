import pytest
from splpp import compile_text_fn

def test_large_codegen_runs():
    # generate a long body by repetition
    body = []
    body.append("@Linear fn big(x: Qdit) -> Qdit {")
    body.append("  qinit t;")
    for i in range(200):
        body.append("  apply F(x);")
        body.append("  apply CX(x, t);")
    body.append("  return x;")
    body.append("}")
    src = "dim 2;\n" + "\n".join(body) + "\n"
    txt = compile_text_fn(src, "big")
    assert len(txt) > 1000
