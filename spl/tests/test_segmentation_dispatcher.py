import unittest
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl import interpret
from spl.src.relations.set_relations import SetRelation
from spl.src.relations.affine_relations import AffineRelation

class TestSegmentationDispatcher(unittest.TestCase):
    def _run(self, src, p=5):
        prog = parse_spl(src)
        env, rel = interpret(p, prog, context=None)
        return rel

    def test_pure_classical_and_is_set_function(self):
        rel = self._run("init a; init b; init t; init u; t = sum * (a, b); u = and * (t, b);")
        self.assertIsInstance(rel, SetRelation)

    def test_pure_affine_quantum_ctrlx_affine(self):
        rel = self._run("qinit q; init c; ctrlX c q;")
        self.assertIsInstance(rel, AffineRelation)


    def test_mixed_classical_then_affine_becomes_set(self):
        src = """
        init a; init b; init t; t = sum * (a, b);
        init c; init _x; (c, _x) = copy * t;
        qinit q; ctrlX c q;
        """
        rel = self._run(src)
        self.assertIsInstance(rel, AffineRelation)
