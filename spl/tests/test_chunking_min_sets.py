
import unittest
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl import interpret, _segment_program
from spl.src.relations.set_relations import SetRelation
from spl.src.relations.affine_relations import AffineRelation

def kinds_for(src: str):
    prog = parse_spl(src)
    chunks = _segment_program(prog.stmts)
    return [k for (k,_) in chunks]

def run_rel(src: str, p: int = 3):
    prog = parse_spl(src)
    _env, rel = interpret(p, prog, context=None)
    return rel

class TestChunkingMinimizeSets(unittest.TestCase):
    def test_classical_with_multiple_ands_is_single_FUNC_chunk_and_set_function(self):
        src = """
        init a; init b; init c;
        init t; init u; init v;
        t = and * (a, b);
        u = sum * (t, c);
        v = and * (u, a);
        """
        self.assertEqual(kinds_for(src), ["FUNC"])
        rel = run_rel(src)
        self.assertIsInstance(rel, SetRelation)

    def test_affine_sequence_single_AFFINE_chunk(self):
        src = "qinit q; q *= X; q *= Z; init c; ctrlX c q;"
        ks = kinds_for(src)
        self.assertIn("AFFINE", ks)
        self.assertNotIn("SETS", ks)
        rel = run_rel(src)
        self.assertIsInstance(rel, AffineRelation)

    def test_affine_only_across_classical_affine_ops_prefers_whole_program_affine(self):
        # Classical affine-only then affine quantum. Should not force set relations.
        src = "init a; init x; x = sum * (a,a); qinit q; ctrlZ x q;"
        # Segmentation may show FUNC + AFFINE, but interpreter should choose affine overall
        self.assertEqual(kinds_for(src), ["FUNC","AFFINE"])
        rel = run_rel(src)
        self.assertIsInstance(rel, AffineRelation)

    def test_func_with_and_then_affine_then_func_results_sets(self):
        src = """
        init a; init b; init t; t = and * (a,b);
        qinit q; ctrlX t q;
        init y; y = sum * (a,b);
        """
        self.assertEqual(kinds_for(src), ["FUNC","AFFINE","FUNC"])
        rel = run_rel(src)
        self.assertIsInstance(rel, SetRelation)

    def test_no_sets_features_never_uses_sets(self):
        # Mixed classical without 'and' and quantum affine: result should be affine
        src = "init a; a = plusone * a; qinit q; ctrlX a q; init y; y = sum * (a,a);"
        self.assertEqual(kinds_for(src), ["FUNC","AFFINE","FUNC"])
        rel = run_rel(src)
        self.assertIsInstance(rel, AffineRelation)


if __name__ == "__main__":
    unittest.main()
