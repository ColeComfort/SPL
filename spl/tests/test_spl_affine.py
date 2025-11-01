# test_spl_affine.py
import unittest
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl_affine import interpret
from spl.src.relations.affine_relations import AffineRelation

P = 5  # odd prime



    
# ---------- linear algebra over F_p ----------
def _rref(A, p):
    A = [row[:] for row in A]
    m = len(A)
    n = len(A[0]) if A else 0
    piv = []
    r = 0
    for c in range(n):
        piv_row = None
        for i in range(r, m):
            if A[i][c] % p != 0:
                piv_row = i
                break
        if piv_row is None:
            continue
        A[r], A[piv_row] = A[piv_row], A[r]
        inv = pow(A[r][c] % p, -1, p)
        for j in range(c, n):
            A[r][j] = (A[r][j] * inv) % p
        for i in range(m):
            if i == r:
                continue
            f = A[i][c] % p
            if f:
                for j in range(c, n):
                    A[i][j] = (A[i][j] - f * A[r][j]) % p
        piv.append(c)
        r += 1
        if r == m:
            break
    return A, piv

def _in_span(p, cols, v):
    """True iff v ∈ span(cols) over F_p. cols is list of column vectors (each length d)."""
    d = len(v)
    k = len(cols)
    if k == 0:
        # only the zero vector is in the span of the empty set
        return all((vi % p) == 0 for vi in v)
    M = [[cols[j][i] % p for j in range(k)] for i in range(d)]  # d x k
    Aug = [M[i][:] + [v[i] % p] for i in range(d)]
    R, _ = _rref(Aug, p)
    for i in range(d):
        if all(R[i][j] == 0 for j in range(k)) and (R[i][k] % p != 0):
            return False
    return True

def _columns_from_basis_rows(rows):
    """rows is a matrix given row-wise; return list of column vectors."""
    if not rows:
        return []
    d = len(rows)
    k = len(rows[0])
    return [[rows[i][j] for i in range(d)] for j in range(k)]

def affine_equal(rel1: AffineRelation, rel2: AffineRelation) -> bool:
    """Equality of affine subspaces (same p, same type, same shift, mutually spanning bases)."""
    if rel1.p != rel2.p or rel1.n_in != rel2.n_in or rel1.n_out != rel2.n_out:
        return False
    p = rel1.p
    # shifts must match (our constructions use 0 shifts)
    s1 = [x % p for x in rel1.subspace.shift]
    s2 = [x % p for x in rel2.subspace.shift]
    if s1 != s2:
        return False
    # mutual span of bases
    rows1 = rel1.subspace.basis
    rows2 = rel2.subspace.basis
    if len(rows1) != len(rows2):
        return False
    cols1 = _columns_from_basis_rows(rows1)
    cols2 = _columns_from_basis_rows(rows2)
    # each column of 1 in span of 2
    for v in cols1:
        if not _in_span(p, cols2, v):
            return False
    # and each column of 2 in span of 1
    for v in cols2:
        if not _in_span(p, cols1, v):
            return False
    return True

# ---------- tests ----------


class TestSingleQudit(unittest.TestCase):
    def test_F_four_preserves_qinit_denotation(self):
        # Baseline: after qinit, we get a particular affine relation (not identity on the enlarged store).
        base = parse_spl("qinit q")
        env0, rel0 = interpret(P, base)
        # Now apply F^4; denotation should be unchanged.
        src = r"""
            qinit q
            q *= F
            q *= F
            q *= F
            q *= F
        """
        env, rel = interpret(P, parse_spl(src))
        self.assertTrue(affine_equal(rel0, rel), "F^4 should not change the qinit denotation")

    def test_S_pow_p_preserves_qinit_denotation(self):
        base = parse_spl("qinit q")
        env0, rel0 = interpret(P, base)
        src = "qinit q\n" + "\n".join(["q *= S"] * P)
        env, rel = interpret(P, parse_spl(src))
        self.assertTrue(affine_equal(rel0, rel), "S^p should not change the qinit denotation")


class TestTeleportation(unittest.TestCase):
    def _rel_of(self, src: str):
        prog = parse_spl(src)
        env, rel = interpret(P, prog, context=(prog.context or {}))
        return rel

    def test_teleportation_identity_open_in(self):
        progA = r"""
            context { in: qpit }

            % initialize registers
            qinit x
            qinit out

            % prepare Bell pair
            x *= F
            (x, out) *= CX

            % Bell measurement (SUM then F^{-1} on 'in')
            (in, x) *= CX
            in *= F
            % in *= F
            % in *= F      % F^{-1} since F^4 = I

            % measure in Z basis
            meas x       % outcome i  (shift)
            meas in      % outcome j  (clock)

            % phase correction: apply X^i then Z^j
            ctrlX x  out
            ctrlZ in out

            % discard ancillae
            disc in
            disc x

        """
        relA = self._rel_of(progA)
        print(relA)

        from spl.src.interpreter.interpret_spl_affine import graph_identity
        relId = graph_identity(P, 2)
        self.assertTrue(
            affine_equal(relA, relId),
            msg=f"\n--- Program ---\n{progA}\nExpected: identity from 'in' to 'out'\n"
        )


# ---------- totality helper ----------
def rank_mod_p(M, p):
    R, _ = _rref([row[:] for row in M], p)
    # count nonzero rows
    return sum(any(x % p != 0 for x in row) for row in R)

def is_total(rel: AffineRelation) -> bool:
    """
    Relation rel : n -> m (as an affine subspace in F_p^{n+m}) is total
    iff its projection to the input coordinates is all of F_p^n.
    In our parametric form (shift, basis), this holds iff the input-half
    of the basis has rank n (shift doesn't matter for surjectivity).
    """
    n = rel.n_in
    if n == 0:
        return True
    B = rel.subspace.basis            # (n+m) x k
    if not B:
        return False
    Bin = [row[:] for row in B[:n]]   # take the first n rows
    return rank_mod_p(Bin, rel.p) == n

# ---------- totality tests ----------
class TestTotality(unittest.TestCase):
    def test_total_after_classical_program(self):
        src = r"""
            init a; init b
            (a, b) = copy * a
            a = plusone * a
            b = sum * (a, b)
        """
        env, rel = interpret(P, parse_spl(src))
        self.assertTrue(is_total(rel))

    def test_total_after_qinit_and_gates(self):
        src = r"""
            qinit q
            q *= F
            q *= S
            q *= Z
            q *= X
        """
        env, rel = interpret(P, parse_spl(src))
        self.assertTrue(is_total(rel))

    def test_not_total_manual_counterexample(self):
        # Build a relation 1->1 that forces input = 0 (not total).
        # Subspace columns: only vary output; input row is always 0.
        shift = [0, 0]                 # length n+m = 2
        basis = [[0],                  # input row (n=1): 0
                 [1]]                  # output row (m=1): free
        rel = AffineRelation.from_shift_basis(P, 1, 1, shift, basis)
        self.assertFalse(is_total(rel))
import unittest
# assumes interpret, parse_spl, P, affine_equal, is_total are imported

# ---------- helpers ----------
def _ok_len_shift(t, rel):
    t.assertEqual(len(rel.subspace.shift), rel.n_in + rel.n_out)

# ---------- tests ----------
class TestAffineFromGenerators(unittest.TestCase):
    def test_build_upper_triangular_map_x_y_to_xplusy_y(self):
        srcA = r"""
            context { x: pit; y: pit }
            init t
            t = sum * (x, y)
            init z0
            x = sum * (t, z0)
            disc t
            disc z0
        """
        srcB = r"""
            context { x: pit; y: pit }
            init u
            init v
            (u, v) = copy * x
            x = sum * (u, y)
            disc u
            disc v
        """
        _, relA = interpret(P, parse_spl(srcA))
        _, relB = interpret(P, parse_spl(srcB))
        self.assertTrue(affine_equal(relA, relB))
        _ok_len_shift(self, relA)

class TestDiscardProperties(unittest.TestCase):
    def test_zero_fill_construct_two_ways(self):
        srcA = r"""
            init y
            init z0
            y = sum * (z0, z0)
            disc z0
        """
        srcB = "init y\n" + "\n".join(["y = plusone * y" for _ in range(P)])
        _, relA = interpret(P, parse_spl(srcA))
        _, relB = interpret(P, parse_spl(srcB))
        self.assertTrue(affine_equal(relA, relB))
        _ok_len_shift(self, relA)

    def test_discard_reduces_output_dim_and_keeps_shift_size(self):
        src = r"""
            init a
            init b
            init c
            init d
            (c, d) = copy * a
            disc c
        """
        _, rel = interpret(P, parse_spl(src))
        _ok_len_shift(self, rel)

        src2 = r"""
            init a
            init b
            init c
            init d
            (c, d) = copy * a
            disc c
            disc c
        """
        with self.assertRaises(ValueError):
            interpret(P, parse_spl(src2))

    def test_discard_after_copy_equivalent_to_not_producing_temp(self):
        src1 = r"""
            init x
            init t
            init u
            (t, u) = copy * x
            disc t
            disc u
        """
        src2 = r"""
            init x
        """
        _, rel1 = interpret(P, parse_spl(src1))
        _, rel2 = interpret(P, parse_spl(src2))
        self.assertTrue(affine_equal(rel1, rel2))
        _ok_len_shift(self, rel1)

class TestQuantumClassicalInterplay(unittest.TestCase):
    def test_measure_then_classical_flow_total(self):
        src = r"""
            context { cctx: pit }
            qinit q
            meas q
            init c0
            init c1
            (c0, c1) = copy * q
            c0 = sum * (c0, c1)
            disc c1
        """
        _, rel = interpret(P, parse_spl(src))
        self.assertTrue(is_total(rel))
        _ok_len_shift(self, rel)

    def test_cliffords_do_not_change_shift_size(self):
        src = r"""
            context { cctx: pit }
            qinit q1
            q1 *= F
            q1 *= S
            q1 *= Z
            q1 *= X
            qinit q2
            (q1, q2) *= CX
            meas q1
            init c
            init z0
            c = sum * (c, z0)
        """
        _, rel = interpret(P, parse_spl(src))
        _ok_len_shift(self, rel)


class TestAffineQuantumExtensions(unittest.TestCase):
    def _rel(self, p, src, ctx=None):
        env, rel = interpret(p, parse_spl(src), context=ctx)
        return rel

    def test_X_negative_param_mod_p(self):
        p = 7
        srcA = "qinit q; q *= X^{-3};"
        srcB = f"qinit q; q *= X^{p-3};"
        relA = self._rel(p, srcA)
        relB = self._rel(p, srcB)
        self.assertTrue(affine_equal(relA, relB))

    def test_Z_large_param_mod_p(self):
        p = 5
        # 12 ≡ 2 (mod 5)
        srcA = "qinit q; q *= Z^{12};"
        srcB = "qinit q; q *= Z^{2};"
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_S_k_shear(self):
        p = 11
        # S^k then S^m equals S^{k+m} mod p
        srcA = "qinit q; q *= S^4; q *= S^7;"
        srcB = "qinit q; q *= S^0;"  # 4+7=11 ≡ 0
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_T_definition_matches_FSF_inv(self):
        p = 13
        srcT = "qinit q; q *= T^1;"
        srcFSFinv = "qinit q; q *= F^1; q *= S^1; q *= F^3;"  # F^{-1} = F^3
        self.assertTrue(affine_equal(self._rel(p, srcT), self._rel(p, srcFSFinv)))

    def test_T_k_adds_up(self):
        p = 13
        # T^k then T^m equals T^{k+m} mod p since T is a shear
        srcA = "qinit q; q *= T^5; q *= T^9;"
        srcB = "qinit q; q *= T^1;"  # 5+9=14 ≡ 1 mod 13
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_F_repetition_mod_4(self):
        p = 17
        srcA = "qinit q; q *= F^5;"
        srcB = "qinit q; q *= F^1;"
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_CX_k_scaling(self):
        p = 7
        # CX^k composed with CX^m equals CX^{k+m} mod p on same wires
        srcA = "qinit a; qinit b; (a,b) *= CX^3; (a,b) *= CX^6;"
        srcB = "qinit a; qinit b; (a,b) *= CX^2;"  # 3+6=9 ≡ 2 mod 7
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_MUL_k_inverse_action(self):
        p = 11
        # MUL_k then MUL_{k^{-1}} equals identity
        k = 7
        # 7^{-1} mod 11 is 8 since 7*8=56 ≡ 1
        srcA = "qinit q; q *= MUL_7; q *= MUL_8;"
        srcB = "qinit q;"  # identity on one qupit
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_MUL_negative_and_large_k(self):
        p = 13
        # -2 ≡ 11; 27 ≡ 1
        srcA = "qinit q; q *= MUL_-2;"
        srcB = "qinit q; q *= MUL_11;"
        srcC = "qinit q; q *= MUL_27;"  # should be identity
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))
        self.assertTrue(affine_equal(self._rel(p, srcC), self._rel(p, 'qinit q;')))

    def test_MUL_zero_raises(self):
        p = 5
        with self.assertRaises(Exception):
            self._rel(p, "qinit q; q *= MUL_0;")

    def test_mix_S_T_F_commutation_identity_sample(self):
        p = 19
        # Check: F T^k F^{-1} = S^k
        srcA = "qinit q; q *= F^1; q *= T^7; q *= F^3;"
        srcB = "qinit q; q *= S^7;"
        self.assertTrue(affine_equal(self._rel(p, srcA), self._rel(p, srcB)))

    def test_context_domain_unchanged(self):
        p = 7
        ctx = {"c": "pit", "q": "qpit"}
        src = "qinit r; r *= X^3; q *= S^2; q *= MUL_5; discard r;"
        _ = self._rel(p, src, ctx=ctx)


if __name__ == "__main__":
    unittest.main()

