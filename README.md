# Stabiliser Quantum Programming Language (SPL)

SPL is an environment consuming assembly language for Clifford operations, with classically controlled Pauli operations, Pauli basis state preparation, and classical control.

Affine classical control is efficient, but nonlinear classical control is not.

When nonlinear operations are not used, this produces relation which uniquely determines a completely positive trace-preserving map between finite-dimensional C*-algebras.

> SPL++ is a separate high-level language with its own syntax. SPL++ compiles into SPL code. Experimental and not well-tested.

---

## SPL model

- Field: prime field F_p selected by the interpreter.
- Registers are strings with quantum or classical types, denoted  `string : type`. There are two types:
  - `pit`: classical type
  - `qpit`: quantum type
---

## SPL syntax

### Program
```spl
context { a: pit; q: qpit }   % optional
stmt;
stmt;
...
```

### Context
Context is optional and is declared by 
```spl
context { registers with types, delimited by semicolons }
```

### Quantum operations
```spl
qinit x                % Initialises quantum register in state |0>
x     *= G             % Applies single qupit quantum gate G to register x
(x,y) *= G             % Applies two qupit quantum gate G to registers x and y
```

Quantum operations act on quantum registers and do not produce new registers.

### Supported quantum gates
The quantum gates which are available generate the Clifford operations:

Single qupit quantum gates:
```
IDENT                  % X, Z, S, F, T (Pauli X, Pauli Z, phase shift gate S, Fourier transform F)
IDENT^k                % exponent k ∈ ℤ, supports exponents in brackets, ie. {-k} or {k}.
MUL_k                  % multiplies classical basis elements by k
```

Two qupit quantum gates:
```
CX                     % Classically ontrolled X gate
CX^k                   % Classically controlled X^k gate for k ∈ ℤ, supports exponents in brackets, ie. {-k} or {k}.
```

### Quantum-classical operations
```spl
meas q                 % measures quantum register q in Pauli basis and turns q into a classical register
ctrlX c t              % classically controlled Pauli X from classical register c onto quantum register t
ctrlZ c t              % classically controlled Pauli X from classical register c onto quantum register t
ctrl P c t             % classically controlled Pauli P from classical register c onto quantum register t, where P ∈ {Z, X}
```

Classically controlled operations do not consume the classical register.

Measurement consumes the quantum register and makes it classical.

### Experimental classical controlled clifford
```spl
ctrl G c t             % Classically controlled clifford where G ∈ {S, F, T, CX}. NONLINEAR and slow to interpret
```

### Classical operations
```spl
skip                      % nothing operation
init x                    % initialise classical register x with value 0
disc x                    % discard classical register x
(y,z)   = copy * x        % copies register x into registers y and z
z       = sum  * (x,y)    % sums registers x and y into register z
y       = plusone * x     % sets register y to x+1 mod p
z       = and * (x,y)     % sets register z to the product of registers x and y. NONLINEAR and slow to interpret
```

Classical operations consume classical input registers and produce new classical registers


## SPL example: Teleportation

```spl
context { in: qpit }

% ancillae
qinit x
qinit out

% prepare Bell pair
x *= F
(x, out) *= CX

% Bell measurement
(in, x) *= CX
in *= F

% measure
meas x       % outcome i
meas in      % outcome j

% corrections
ctrlX x  out
ctrlZ in out

% clean ancillae
disc in
disc x
```

This is interpreted as identity relation from `in` to `out`.

---

## Compilation pipeline

High level to low level to semantics:

1. **SPL++** source. High-level functions, types, and controls (EXPERIMENTAL AND NOT WELL-TESTED).
2. **Compiler** lowers **SPL++** to **SPL**.
3. **Interpreter** transforms SPL programs into relations. Needs to be provided with a prime number for the dimension.
   - Uses the **Affine** backend if every classical operation is affine.
   - If there are a mix of affine and nonlinear operations, the interpreter chunks SPL code into segments consisting of affine relations, and set functions. Then the chunks are interpreted separately. If there are affine chunks and nonlinear functions mixed together, they are cast into set relations then composed as set-relations. The goal is to minimize set relation composition to lower the computational complexity.

Outcome: an relation and a dictionary indexing the input and output registers.  Quantum registers `a` are split in two `a.x` and `a.z`. Classical registers names are unchanged. The domain is fixed by the SPL `context`. The range is inferred.

---

# SPL++

SPL++ is an **experimental**, not-well-tested,  **high-level** language with functions, kinds, control, and a compiler that lowers programs to SPL.

## SPL++ example: Teleportation

```spl++
dim 3;

// Prepare a Bell pair |Φ+> from |0,0>
@Linear fn prepare_bell() -> Qdit, Qdit {
    qinit qb;
    qinit qc;
    apply F(qb);
    apply CX(qb, qc);
    return qb, qc;
}

// Bell-basis measurement on (qa, qb); returns classical dits (m0, m1)
@Linear fn bell_measure(qa: Qdit, qb: Qdit) -> Dit, Dit {
    apply CX(qa, qb);
    apply F(qa);
    meas qa;
    meas qb;
    return qa, qb;
}

// Classically controlled Pauli corrections on target
@Linear fn pauli_correct(m0: Dit, m1: Dit, out: Qdit) -> Qdit {
    cctrl m0: apply X(out);
    cctrl m1: apply Z(out);
    return out;
}

// Teleport 'in' to 'out'
@Linear fn teleport(in: Qdit) -> Qdit {
    apply prepare_bell() -> qb, qc;
    apply bell_measure(in, qb) -> m0, m1;
    apply pauli_correct(m0, m1, qc) -> out;
    return out;
}

// Driver: print SPL for teleport
fn main() {
    print spl teleport;
}
```

## Build and run

```bash
make install

# Run SPL interpreter on a .spl file
make run-spl FILE=examples/teleportation.spl

# Or directly:
PYTHONPATH=. python -m spl.scripts.spl_rel path/to/program.spl
```

---

## Troubleshooting

- **SPL parse errors**: use only the primitives listed; `meas q` has no arrow.
- **Backend mismatch**: using `and` forces set semantics.
- **Gate parameters**: `MUL_k` uses `_k`, not exponent.
- **Do not mix syntaxes**: `.spl` uses SPL syntax only. `.spl++` uses SPL++ syntax only.


## Verbose tests

Run `make test-verbose` or `. .venv/bin/activate && python -m pytest -vv -s`.
