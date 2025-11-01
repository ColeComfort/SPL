# test_set_relations.py
import unittest

from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_affine
from spl.src.interpreter.interpret_spl import interpret as interpret_dispatch
from spl.src.interpreter.interpret_spl_sets import interpret_sets
from spl.src.relations.set_relations import SetRelation


class TestSetInterpreter(unittest.TestCase):
    def test_and_truth_table_mod2(self):
        p = 2
        src = """
            context {
              a: pit
              b: pit
            }
            init c
            c = and * (a, b)
        """
        prog = parse_spl(src)
        ctx = {"a": "pit", "b": "pit"}
        env, R = interpret_sets(p, prog, ctx)

        want = set()
        for a in (0, 1):
            for b in (0, 1):
                c = (a * b) % p
                want.add(((a, b), (a, b, c)))

        self.assertIsInstance(R, SetRelation)
        self.assertEqual(R.p, 2)
        self.assertEqual(R.n_in, 2)
        self.assertEqual(R.n_out, 3)
        self.assertEqual(R.pairs, want)

        self.assertEqual(R.input_names[0], "a")
        self.assertEqual(R.input_names[1], "b")
        self.assertEqual(R.output_names[0], "a")
        self.assertEqual(R.output_names[1], "b")
        self.assertEqual(R.output_names[2], "c")

        s = str(R)
        self.assertIn("SetRelation over F_2", s)
        self.assertIn("Type:", s)
        self.assertIn("F_p", s)

    def test_dispatcher_uses_sets_if_and_present(self):
        p = 5
        src = """
            context { x: pit; y: pit }
            init z
            z = and * (x, y)
        """
        prog = parse_spl(src)
        env, R = interpret_dispatch(p, prog)
        self.assertIsInstance(R, SetRelation)

        for x, y in [(0,0), (1,2), (3,4)]:
            z = (x*y) % p
            self.assertIn(((x,y), (x,y,z)), R.pairs)

    def test_dispatcher_keeps_affine_if_no_and(self):
        p = 3
        src = """
            context { x: pit; y: pit }
            init z
            z = sum * (x, y)
        """
        prog = parse_spl(src)
        env_aff, R_aff = interpret_affine(p, prog, {"x": "pit", "y": "pit"})
        env_dis, R_dis = interpret_dispatch(p, prog, {"x": "pit", "y": "pit"})
        self.assertEqual(R_aff.p, R_dis.p)
        self.assertEqual(R_aff.n_in, R_dis.n_in)
        self.assertEqual(R_aff.n_out, R_dis.n_out)
        self.assertEqual(str(R_aff), str(R_dis))

    def test_measure_then_and(self):
        p = 2
        src = """
            context { q: qpit; c: pit }
            init t
            meas q
            t = and * (q, c)
        """
        prog = parse_spl(src)
        env, R = interpret_sets(p, prog, {"q": "qpit", "c": "pit"})

        # Domain: c, q.x, q.z   (lexicographic order of context keys)
        self.assertEqual(R.n_in, 3)
        self.assertEqual(env.current.input_names[0], "c")
        self.assertEqual(env.current.input_names[1], "q.x")
        self.assertEqual(env.current.input_names[2], "q.z")

        # Output after init t, meas q, and: c, q, t
        self.assertEqual(R.n_out, 3)
        self.assertEqual(env.current.output_names[0], "c")
        self.assertEqual(env.current.output_names[1], "q")
        self.assertEqual(env.current.output_names[2], "t")

        # Relation pairs: (c, qx, qz) ↦ (c, q=qx, t=qx*c)
        want = set()
        for c in (0,1):
            for qx in (0,1):
                for qz in (0,1):
                    t = (qx * c) % 2
                    want.add(((c, qx, qz), (c, qx, t)))
        self.assertEqual(R.pairs, want)


    def test_set_relation_compose_bruteforce(self):
        p = 3
        R = SetRelation.from_graph_function(
            p, 1, 2,
            lambda v: [v[0], (v[0]*v[0]) % p],
            in_names={0: "x"},
            out_names={0: "x", 1: "u"}
        )
        S = SetRelation.from_graph_function(
            p, 2, 1,
            lambda v: [v[1]],
            in_names={0: "x", 1: "u"},
            out_names={0: "y"}
        )
        C = R.compose(S)
        self.assertIsInstance(C, SetRelation)
        self.assertEqual(C.n_in, 1)
        self.assertEqual(C.n_out, 1)
        want = set()
        for x in (0,1,2):
            want.add(((x,), ((x*x) % p,)))
        self.assertEqual(C.pairs, want)
        self.assertEqual(C.input_names[0], "x")
        self.assertEqual(C.output_names[0], "y")


if __name__ == "__main__":
    unittest.main()

