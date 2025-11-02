
import pytest
from splpp.src.compiler.compiler import compile_text_fn

def test_annotations_required():
    src = "dim 5; fn f(x: Qdit) -> Qdit { return x; }"
    with pytest.raises(TypeError):
        compile_text_fn(src, "f")

def test_caller_below_callee_forbidden():
    src = '''
    dim 5;
    @Linear fn L(a: Qdit) -> Qdit { return a; }
    @controlledclifford fn C(c: Dit, a: Qdit) -> Dit, Qdit { cctrl c: apply L(a); return c, a; }'''
    with pytest.raises(TypeError):
        compile_text_fn(src, "C")

def test_controlled_clifford_lowering():
    src = '''
    dim 5;
    @Clifford fn U(a: Qdit) -> Qdit { apply S(a); apply F(a); return a; }
    @controlledclifford fn C(c: Dit, a: Qdit) -> Dit, Qdit { cctrl c: apply U(a); return c, a; }'''
    spl = compile_text_fn(src, "C")
    assert "ctrl S" in spl and "ctrl F" in spl
