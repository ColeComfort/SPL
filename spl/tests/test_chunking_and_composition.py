
import unittest
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl import interpret
from spl.src.relations.set_relations import SetRelation
from spl.src.relations.affine_relations import AffineRelation

def run_rel(src: str, p: int = 3):
    prog = parse_spl(src)
    _env, rel = interpret(p, prog, context=None)
    return rel

class TestChunkingAndComposition(unittest.TestCase):
    def test_affine_only_prefers_affine(self):
        rel = run_rel("qinit q; q *= X; init c; ctrlX c q;")
        self.assertIsInstance(rel, AffineRelation)

    def test_classical_only_sum_plusone_affine(self):
        rel = run_rel("init a; init b; init t; t = sum * (a,b); t = plusone * t;")
        self.assertIsInstance(rel, AffineRelation)

    def test_classical_with_and_is_set_function(self):
        rel = run_rel("init a; init b; init u; u = and * (a,b);")
        self.assertIsInstance(rel, SetRelation)

    def test_qctrl_pauli_affine(self):
        rel = run_rel("qinit t; init c; ctrlX c t;")
        self.assertIsInstance(rel, AffineRelation)

    def test_meas_affine(self):
        rel = run_rel("qinit q; meas q;")
        self.assertIsInstance(rel, AffineRelation)

    def test_cctrl_pauli_affine(self):
        rel = run_rel("qinit t; init c; ctrlX c t;")
        self.assertIsInstance(rel, AffineRelation)
