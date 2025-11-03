# Stabiliser Quantum Programming Language (SPL)

SPL is a **flat assembly** for stabiliser-style circuits and classical affine wiring. No functions. No branching. A program is an optional `context` followed by statements. The **domain** is fixed by the context and never changes; statements only append or transform **outputs**.

> SPL++ is a separate high-level language with its own syntax and compiler. Experimental and not well-tested

---

## SPL model

- Field: prime field \(\mathbb{F}_p\) selected by the interpreter.
- Context: names and kinds of **open inputs**.
  - `pit`: classical wire, contributes 1 coordinate.
  - `qpit`: quantum wire, contributes 2 coordinates `.x` and `.z`.
- Statements operate on outputs only. Context fixes the input size.

The interpreter selects backend:
- **Affine** backend if only affine classical primitives are used.
- **Set** backend if any non-affine primitive is used, e.g. `and`.

---

## SPL syntax

### Program
```spl
context { a: pit; q: qpit }   % optional
stmt;
stmt;
...
```

Context is optional and is used to generate relations with inputs, rather than states.

### Gate atoms
```
IDENT                  % X, Z, S, F, T, CX
IDENT^k                % exponent k ∈ ℤ, supports exponents in brackets, ie. {-k} or {k}.r
MUL_k                  % multiplies classical basis elements by k
```


### Quantum operations
```spl
qinit q                % Initialises quantum register in state |0>
meas q                 % 
(x,y) *= CX^k          % apply controlled X gate from register x to register y
ctrlX c t              % classical control: add c into t.x
ctrlZ c t              % classical control: add c into t.z
ctrl P c t             % generic token; interpreter accepts P in {X,Z}
```

Quantum operations act on quantum registers and do not produce new registers

### Quantum-classical operations
```spl
meas q                 % measures quantum register q in Pauli basis and turns q into a classical register
ctrlX c t              % classically controlled Pauli X from classical register c onto quantum register t
ctrlZ c t              % classically controlled Pauli X from classical register c onto quantum register t
ctrl P c t             % classically controlled Pauli P from classical register c onto quantum register t, where P in {Z, X}
```

Classically controlled operations do not consume the classical register.
Measurement consumes the quantum register and makes it classical

### Experimental classical controlled clifford
```spl
ctrl G c t             % generic token; interpreter also accepts G in {S, F, T, CX}
```


### Classical operations
```spl
skip                   % nothing operation
init x                 % add classical output x := 0
disc x                 % discard classical register x
(y1,y2) = copy * x     % copies register x into registers y1 and y2
z    = sum  * (u,v)    % sums registers u and v into register x
y    = plusone * x     % sets register y to x+1 mod p
t    = and * (u,v)     % sets register t to the product of registers u and v. NONLINEAR and slow to interpret
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
This denotes the identity relation from `in` to `out` over \(\mathbb{F}_p\).

---

## Compilation pipeline

High level to low level to semantics:

1. **SPL++** source. High-level functions, types, and controls (EXPERIMENTAL AND NOT WELL-TESTED).
2. **Compiler** lowers **SPL++** to **SPL**.
3. **Interpreter** evaluates SPL as a relation over \(\mathbb{F}_p\):
   - Uses the **Affine** backend if every classical operation is affine.
   - If there are a mix of affine and nonlinear operations, the interpreter chunks SPL code into segments consisting of affine relations, and set functions. Then the chunks are interpreted separately. If there are affine chunks and nonlinear functions mixed together, they are cast into set relations then composed as set-relations. The goal is to minimize set relation composition to lower the computational complexity.

Outcome: an relation and a dictionary indexing the input and output registers.  Quantum registers `a` are split in two `a.x` and `a.z`. Classical registers names are unchanged. The domain is fixed by the SPL `context`. The range is inferred.

---

# SPL++ (separate language)

SPL++ is an **experimental**, not-well-tested,  **high-level** language with functions, kinds, control, and a compiler that lowers programs to SPL.

## SPL++ essentials

### Detailed syntax
- **Dimension**: `dim p;` sets the prime field.
- **Kinds (capabilities)** on functions restrict allowed constructs inside the body:
  - `@Pauli` targets Pauli-only operations and Pauli subroutines.
  - `@Clifford` allows Clifford unitaries and Pauli controls.
  - `@Linear` allows affine classical transforms (`copy`, `sum`, `plusone`) and Pauli controls.
  - `@Nonlinear` permits `and`, boolean branching, or other non-affine constructs.
- **Types**:
  - `Qdit` for quantum registers.
  - `Dit`  for classical registers in \(\mathbb{F}_p\).
  - `Bool` for boolean guards; booleans lower to the classical primitives.
- **Function forms**:
  - `@Kind fn Name(args) -> out_list { stmts }` returns an ordered list of variables.
  - `fn main() { stmts }` is the entry point. No return list.
- **State statements**:
  - `init x;` or `init x = k;` with `k ∈ \mathbb{F}_p`.
  - `qinit q;` or `qinit q = k;` or `qinit q = mixed;`.
  - `meas q;` converts `q: Qdit` to a classical `Dit`.
  - `prep q;` replaces a classical `Dit` by a fresh `Qdit` at the same name.
- **Unitary application**:
  - `apply G(a, b, ...);` with `G ∈ {X,Z,S, F, T, CX, SWAP, MUL_k}` as implemented.
  - **Outs rule**: unitaries either omit outs or specify outs equal to ins in the same order; non-unitaries must specify outs.
- **Classical transforms**: `copy`, `sum`, `plusone`, `and` occur via helper lowering.
- **Control**:
  - Classical control: `cctrl c: apply P(t);` where `c: Dit`, `P ∈ {X,Z}`. Compiles to `ctrlX/ctrlZ`.
  - Quantum control: `qctrl q: apply P(t);` where `q: Qdit`, `P ∈ {X,Z}`. Compiles via `CX` and `F` as needed.
- **Booleans and branching**:
  - `let b: Bool = ...; if b { ... } else { ... }` allowed in SPL++; the compiler lowers boolean ops to the classical primitives. Using `and` or branching forces Nonlinear kind.
- **Utilities**:
  - `assert equal F G;`, `assert included F G;`, `print spl Name;`, `dagger U as U_d;`, `return ...;`

---

## SPL++ example: Teleportation

```spl++
dim 2;

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

The compiler lowers `teleport` to SPL statements equivalent to the SPL program above.

---

## Implementation status

### SPL
- **Implemented**: `context`, `skip`, `init`, `qinit`, `meas`, `disc`/`discard`, gate application `*=`, classical transforms `copy/sum/plusone`, classical control `ctrlX/ctrlZ/ctrl P` (with `P∈{X,Z}`), affine interpreter, set interpreter.
- **Not implemented**: non-Pauli `ctrl P`, multi-arity gates beyond `CX`, non-listed transforms.
- **Notes**: `and` is rejected by the affine interpreter and triggers the set interpreter when present.

### SPL++
- **Implemented**: parsing of kinds/types, `init/qinit/meas/prep`, `apply` with or without outs, `cctrl` and `qctrl` over Pauli targets, `if` with boolean expressions, `assert`, `print spl`, `dagger as`, `return`, compiler lowering to SPL, assertions checked by interpreting the lowered SPL.
- **Partially implemented / constraints**: `qctrl` and `cctrl` only over Pauli targets; attempting to control a non-Pauli or non-@Pauli function raises a compile-time error. Outs rule is enforced for unitaries by construction. Some library gates beyond those in the interpreters may not lower.
- **Testing**: SPL++ is **not fully tested**. Use the provided examples and tests; report mismatches. The SPL level and affine tests are the current source of truth.

---

## Build and run

```bash
make venv
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
