# Stabiliser Quantum Programming Language (SPL)

SPL is a **flat assembly** for stabiliser-style circuits and classical affine wiring. No functions. No branching. A program is an optional `context` followed by statements. The **domain** is fixed by the context and never changes; statements only append or transform **outputs**.

> SPL++ is a separate high-level language with its own syntax and compiler. Do not mix syntax.

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

- Without a context the domain is `0` and the program builds outputs only.

### Statements
```spl
skip
init x                 % add classical output x := 0
qinit q                % add quantum outputs q.x := 0, q.z := 0
disc x                 % remove outputs (alias: discard)
discard x
meas q                 % keep q.x, drop q.z, q becomes classical
(x,y) *= CX^k          % apply gate
t = sum * (x,y)        % classical transforms (see below)
ctrlX c t              % classical control: add c into t.x
ctrlZ c t              % classical control: add c into t.z
ctrl P c t             % generic token; interpreter accepts P in {X,Z}
```

Notes:
- `meas q` converts `q` in place. No arrow.
- Register position is a name or a pair `(r1, r2)` for binary gates.
- `disc` and `discard` are synonyms.

### Gate atoms
```
IDENT                  % X, Z, S, F, T, CX
IDENT^k                % exponent k ∈ ℤ
MUL_k                  % parameter k for dilation (k in 𝔽_p^×)
```

### Classical transforms
```
y1,y2 = copy * x       % 1→2
z    = sum  * (u,v)    % 2→1
x    = plusone * x     % in-place increment mod p
t    = and * (u,v)     % 2→1, non-affine → set backend
```
All named wires must already exist and be classical. Arity checks are strict.

---

## SPL operational semantics

The environment maps variable names to **output coordinates**.

- `init x`: append 1 coordinate, bind `x`.
- `qinit q`: append 2 coordinates, bind `q.x`, `q.z`.
- `meas q`: keep `q.x`, drop `q.z`, bind `q` to the remaining classical coordinate.
- `disc x`: delete bound coordinates and reindex remaining outputs.
- `ctrlX c q`: add classical `c` into `q.x` mod `p`.
- `ctrlZ c q`: add classical `c` into `q.z` mod `p`.
- Gates compose on outputs; inputs are those fixed by `context`.

Affine backend composes affine relations. Set backend composes relations extensionally over tuples.

---

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
meas x       % i
meas in      % j

% corrections
ctrlX x  out
ctrlZ in out

% clean ancillae
disc in
disc x
```
This denotes the identity relation from `in` to `out` over \(\mathbb{F}_p\).

---
---

## Compilation pipeline

High level to low level to semantics:

1. **SPL++** source. High-level functions, types, and controls.
2. **Compiler** lowers to **SPL**. The result is a flat sequence with an optional `context`.
3. **Interpreter** evaluates SPL as a relation over \(\mathbb{F}_p\):
   - Uses the **Affine** backend if every classical operation is affine.
   - Uses the **Set** backend only if a non-affine primitive occurs (e.g., `and` or explicit nonlinear branching). The set backend is slower and is avoided when affine suffices.

Outcome: an explicitly printed relation with named coordinates. The domain is fixed by the SPL `context`. The range is built by SPL statements.


# SPL++ (separate language)

SPL++ is a **high-level** language with functions, kinds, control, and a compiler that lowers programs to SPL. Its syntax is **different** from SPL.

## SPL++ essentials

### Detailed syntax
- **Dimension**: `dim p;` sets the prime field.
- **Kinds (capabilities)** on functions restrict allowed constructs inside the body:
  - `@Pauli` targets Pauli-only operations.
  - `@Clifford` allows Clifford unitaries and Pauli controls.
  - `@Linear` allows affine classical transforms (`copy`, `sum`, `plusone`) and Pauli controls.
  - `@Nonlinear` permits `and`, boolean branching, or other non-affine constructs.
- **Types**:
  - `Qdit` for quantum registers.
  - `Dit`  for classical registers in \(\mathbb{F}_p\).
  - `Bool` for boolean guards; Booleans are implemented over dits using `init/copy/sum/plusone/and` when lowered.
- **Function forms**:
  - `@Kind fn Name(args) -> out_list { stmts }` returns an ordered list of variables.
  - `fn main() { stmts }` is the entry point. No return list.
- **State statements**:
  - `init x;` or `init x = k;` with `k ∈ \mathbb{F}_p`.
  - `qinit q;` or `qinit q = k;` or `qinit q = mixed;`.
  - `meas q;` converts `q: Qdit` to a classical `Dit`.
  - `prep q;` prepares a fresh `Qdit` from classical data if supported.
- **Unitary application**:
  - `apply G(t1, ..., tn);` with `G ∈ {X,Z,S,F,T,CX,SWAP,MUL_k}`.
  - **Outs rule**: unitaries either omit outs or specify outs equal to ins in the same order; non-unitaries must specify explicit outs.
- **Classical transforms**: `copy`, `sum`, `plusone`, `and` used via helper lowering for booleans and arithmetic.
- **Control**:
  - Classical control: `cctrl c: apply P(t);` where `c: Dit`, `P ∈ {X,Z}`. Target must be Pauli-compatible.
  - Quantum control: `qctrl q: apply P(t);` where `q: Qdit`, `P ∈ {X,Z}` only. Rejects controls over non-Pauli targets.
- **Booleans and branching**:
  - `let b: Bool = ...; if b { ... } else { ... }` allowed in SPL++; the compiler lowers boolean ops to the classical primitives. Using `and` or branching forces Nonlinear kind.
- **Assertions and utilities**:
  - `assert ...;`, `print spl Name;`, `dagger U as U_d;`, `return ...;` as provided by the implementation.


- Set dimension: `dim p;` for the prime field.
- Kinds: `@Pauli`, `@Clifford`, `@Linear`, `@Nonlinear` annotate function capabilities checked by the compiler.
- Types: `Dit`, `Qdit`, `Bool`.
- Functions:
  - `@Kind fn Name(args) -> outs { ... }`
  - `fn main() { ... }` as entry point.
- Statements:
  - State: `init x;`, `qinit q;`, `meas q;`, `prep q;`
  - Apply: `apply G(a, b, ...)` (with or without explicit outs for unitaries)
  - Control: `cctrl c: apply X(t);`, `qctrl c: apply X(t);`
  - Classical ops and booleans with `let`, arithmetic, and `if`.
- Gates: `X, Z, S, F, T, CX, SWAP, MUL_k` and classical `copy, sum, plusone, and`.
- **Outs rule**: Unitaries either omit outs or set `outs == ins`. Non-unitaries must specify outs.

### Kind rules summary
- `qctrl` is allowed only with **Pauli** targets. Attempts over `@Clifford` are rejected.
- `cctrl` over Pauli is Linear. Using branching or `and` classifies a function as Nonlinear.

## SPL++ example: Teleportation

```splpp
dim 5;

@Linear fn BellPair(a: Qdit, b: Qdit) -> Qdit, Qdit {
    apply F(a);
    apply CX(a, b);
    return a, b;
}

@Linear fn Teleport(in: Qdit) -> Qdit {
    qinit x;
    qinit out;
    apply BellPair(x, out);

    apply CX(in, x);
    apply F(in);

    meas x;          // i
    meas in;         // j

    cctrl x:  apply X(out);
    cctrl in: apply Z(out);

    return out;
}

fn main() {
    // compile or print SPL
    // print spl Teleport;
}
```

The compiler lowers `Teleport` to SPL statements equivalent to the SPL program above.

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

- **SPL parse errors**: check that you use `meas q` (no arrow), and only the listed primitives.
- **Backend mismatch**: using `and` forces set semantics.
- **Gate parameters**: `MUL_k` uses `_k`, not exponent.
- **Do not mix syntaxes**: `.spl` uses SPL syntax only. `.spl++` uses SPL++ syntax only.
