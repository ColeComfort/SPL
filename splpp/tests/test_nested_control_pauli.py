import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import splpp
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_aff

SRC = (ROOT.parent / "programs" / "nested_control_pauli_test.spl++").read_text(encoding="utf-8")

def _compile(name: str, p: int = 5) -> str:
    prog = splpp.parse_splpp(SRC)
    comp = splpp.Compiler(dim=p, fns={d.name: d for d in prog.decls})
    return comp.compile_function_to_spl(comp.fns[name])

class TestNestedControlledPauli(unittest.TestCase):

    def test_classical_control_nested_unrolls_in_order(self):
        code = _compile("test_cctrl_nested", p=5)
        # Expect exactly: ctrlX, ctrlZ, ctrlX on (b,t) in this order
        self.assertIn("init b", code)
        self.assertIn("qinit t", code)
        ix1 = code.find("ctrlX b t")
        iz  = code.find("ctrlZ b t")
        ix2 = code.find("ctrlX b t", ix1 + 1)
        self.assertTrue(ix1 != -1 and iz != -1 and ix2 != -1, msg=code)
        self.assertTrue(ix1 < iz < ix2, msg=code)

        # Run through interpreter to ensure no runtime type errors
        spl_ast = parse_spl(code)
        env, rel = interpret_aff(5, spl_ast, context=(spl_ast.context or {}))
        self.assertEqual(rel.p, 5)
        self.assertEqual(rel.n_out, 2)  # Qdit target → 2 coords (x,z)

    def test_quantum_control_nested_lowers_via_CX_and_F_CX_Finv(self):
        code = _compile("test_qctrl_nested", p=5)
        # Expect:
        # 1) CX(c,t)      for first X in P2
        # 2) F on t; CX(c,t); F F F   for Z in P1
        # 3) CX(c,t)      for last X in P2
        # and in the right order
        cx1 = code.find("(c, t) *= CX")
        f1  = code.find("t *= F", cx1 + 1)
        cx2 = code.find("(c, t) *= CX", f1 + 1)
        f2a = code.find("t *= F", cx2 + 1)
        f2b = code.find("t *= F", f2a + 1)
        f2c = code.find("t *= F", f2b + 1)
        cx3 = code.find("(c, t) *= CX", f2c + 1)

        self.assertTrue(all(i != -1 for i in [cx1, f1, cx2, f2a, f2b, f2c, cx3]), msg=code)
        self.assertTrue(cx1 < f1 < cx2 < f2a < f2b < f2c < cx3, msg=code)

        # Execute to ensure interpreter accepts it
        spl_ast = parse_spl(code)
        env, rel = interpret_aff(5, spl_ast, context=(spl_ast.context or {}))
        self.assertEqual(rel.p, 5)
        self.assertEqual(rel.n_out, 2)

    def test_no_state_ops_allowed_inside_pauli(self):
        # Compile P2 directly to ensure no state ops leaked into @Pauli
        prog = splpp.parse_splpp(SRC)
        comp = splpp.Compiler(dim=5, fns={d.name: d for d in prog.decls})
        # Directly compiling P2 should succeed (no init/qinit/meas/prep inside)
        code = comp.compile_function_to_spl(comp.fns["P2"])
        # P2's body only expands when controlled; compiled SPL should be context-only or skip
        self.assertIn("context", code)

if __name__ == "__main__":
    unittest.main()

