# SPL++ negative tests: reject bad control, return mismatches, non-Pauli qctrl via a @Clifford callee, unitary outs mismatch.

import unittest
from splpp import parse_splpp, run_assertions_via_spl


def run_splpp(src: str):
    prog = parse_splpp(src)
    return run_assertions_via_spl(prog)


def _expect_raises(src: str, exc_type, substr_or_list):
    """substr_or_list may be a string or a list/tuple of required substrings."""
    try:
        run_splpp(src)
    except Exception as e:
        if not isinstance(e, exc_type):
            raise AssertionError(f"expected {exc_type.__name__}, got {type(e).__name__}: {e}") from e
        msg = str(e)
        if isinstance(substr_or_list, (list, tuple)):
            missing = [s for s in substr_or_list if s and s not in msg]
            if missing:
                raise AssertionError(f"error message missing substring(s): {missing}\nActual: {msg}")
        else:
            s = substr_or_list
            if s and s not in msg:
                raise AssertionError(f"error message missing substring: {s}\nActual: {msg}")
        return
    raise AssertionError("expected exception, got success")


class TestSPLppControlNegative(unittest.TestCase):
    # Unitary must either omit outs or use identical outs == ins
    def test_unitary_bad_outs(self):
        prog = r"""
        dim 3;
        @Clifford fn bad(a: Qdit, b: Qdit) -> Qdit, Qdit {
          apply CX(a,b) -> a;   # illegal outs
        }
        fn main() { assert equal bad bad; }
        """
        _expect_raises(prog, TypeError, "unitary must either omit outputs or use identical outs == ins")

    # qctrl with a @Clifford callee should be rejected by compiler lowering
    def test_qctrl_rejects_nonpauli(self):
        prog = r"""
        dim 3;

        @Clifford fn C(b: Qdit) -> Qdit { return b; }

        @Pauli fn bad(a: Qdit, b: Qdit) -> Qdit, Qdit {
          qctrl a: apply C(b);   # not Pauli: should be rejected during lowering
          return a, b;
        }

        fn main() { assert equal bad bad; }
        """
        # Be tolerant to current error wording from the compiler.
        _expect_raises(prog, TypeError, ["quantum control over @", "not supported"])

    # Non-unitary must specify outs
    def test_nonunitary_requires_outs(self):
        prog = r"""
        dim 3;
        @Linear fn bad(x: Dit) -> Dit {
          apply sum(x);   # missing output
        }
        fn main() { assert equal bad bad; }
        """
        _expect_raises(prog, TypeError, "non-unitary must specify outputs")

    # Return arity mismatch when nothing returned
    def test_return_arity_mismatch(self):
        prog = r"""
        dim 3;
        @Clifford fn rbad(a: Qdit, b: Qdit) -> Qdit, Qdit {
          # no body; no inits; implicit return []
        }
        fn main() { assert equal rbad rbad; }
        """
        _expect_raises(prog, TypeError, "implicit/explicit return arity 0 != declared 2")

    # Return type mismatch (declare Qdit, actually return Dit)
    def test_return_type_mismatch(self):
        prog = r"""
        dim 3;
        @Linear fn tbad(y: Dit) -> Qdit {
          init z;
          return z;  # z is Dit, expected Qdit
        }
        fn main() { assert equal tbad tbad; }
        """
        _expect_raises(prog, TypeError, "expected Qdit")


if __name__ == "__main__":
    unittest.main()

