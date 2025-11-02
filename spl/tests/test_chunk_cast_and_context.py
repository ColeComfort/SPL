
import unittest
from spl.src.parser.parser import parse_spl, Program
from spl.src.interpreter.interpret_spl import interpret
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine
from spl.src.relations.set_relations import SetRelation
from spl.src.relations.affine_relations import AffineRelation

P = 3  # prime

def cast_affine(A: AffineRelation) -> SetRelation:
    return A.to_set_relation()

class TestChunkCastingAndComposition(unittest.TestCase):
    def _affine_chunk(self, src: str, ctx=None):
        prog = parse_spl(src)
        env, R = interpret_affine(P, prog if ctx is None else Program(stmts=prog.stmts, context=ctx), context=ctx or {})
        self.assertIsInstance(R, AffineRelation)
        return R

    def test_affine_compose_then_cast_equals_cast_then_compose(self):
        ctx = {"a":"pit","q":"qpit"}
        r1 = self._affine_chunk("ctrlX a q;", ctx=ctx)
        r2 = self._affine_chunk("ctrlZ a q;", ctx=ctx)
        comp_affine = r2.compose(r1)
        comp_then_cast = comp_affine.to_set_relation()
        cast_then_comp = cast_affine(r2).compose(cast_affine(r1))
        self.assertEqual(comp_then_cast.p, cast_then_comp.p)
        self.assertEqual(comp_then_cast.n_in, cast_then_comp.n_in)
        self.assertEqual(comp_then_cast.n_out, cast_then_comp.n_out)
        self.assertEqual(comp_then_cast.pairs, cast_then_comp.pairs)
        self.assertEqual(comp_then_cast.input_names, cast_then_comp.input_names)
        self.assertEqual(comp_then_cast.output_names, cast_then_comp.output_names)

    def test_function_compose_then_cast_equals_cast_then_compose(self):
        # Two simple set functions: f(a,b)=a*b, g(t)=t+1
        def f1(x): return [ (x[0]*x[1]) % P ]
        def f2(x): return [ (x[0]+1) % P ]
        R1 = SetRelation.from_graph_function(P, 2, 1, f1, in_names={0:'a',1:'b'}, out_names={0:'t'})
        R2 = SetRelation.from_graph_function(P, 1, 1, f2, in_names={0:'t'}, out_names={0:'u'})
        comp_then_cast = R1.compose(R2)
        cast_then_comp = R1.compose(R2)
        self.assertEqual(comp_then_cast.pairs, cast_then_comp.pairs)

class TestNamesAndContextAcrossChunks(unittest.TestCase):
    def test_names_aligned_affine_only_equals_whole_affine(self):
        src = "init a; qinit q; ctrlX a q; q *= Z;"
        prog = parse_spl(src)
        _E, R_via = interpret(P, prog, context={})
        _Ea, R_aff = interpret_affine(P, prog, context={})
        R1 = R_via if isinstance(R_via, SetRelation) else R_via.to_set_relation()
        R2 = R_aff.to_set_relation()
        self.assertEqual(R1.pairs, R2.pairs)
        self.assertEqual(R1.input_names, R2.input_names)
        self.assertEqual(R1.output_names, R2.output_names)
