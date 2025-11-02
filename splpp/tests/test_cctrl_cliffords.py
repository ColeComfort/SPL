import pytest
from splpp import parse_splpp, compile_text_fn

SRC = r"""
dim 2;

// Treat Pauli and Clifford routines as @Pauli and @Clifford where relevant

@Pauli fn Xgate(t: Qdit) -> Qdit {
    apply X(t);
    return t;
}

@Clifford fn Hlike(t: Qdit) -> Qdit {
    apply F(t);   // Fourier as a Clifford analogue
    apply F(t);   // F^2 ~ X<->Z swap up to phase for qubits; ok as placeholder
    return t;
}

@controlledclifford fn cctrl_pauli_then_clifford() -> Qdit {
    qinit t;
    init b0;
    init b1;
    cctrl b0: apply Xgate(t);     // classical control over Pauli
    cctrl b1: apply Hlike(t);     // classical control over Clifford
    return t;
}

fn main() {
    print spl cctrl_pauli_then_clifford;
}
"""

def test_cctrl_pauli_and_clifford_compile_and_print():
    P = parse_splpp(SRC)
    # Non-main compile should succeed
    spl_txt = compile_text_fn(SRC, "cctrl_pauli_then_clifford")
    assert "apply" in spl_txt or "qinit" in spl_txt
    # main path prints SPL; this is exercised by splpp_rel CLI, not here
