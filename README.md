# Stabiliser Quantum Programming Language (SPL & SPL++)

SPL is a low-level, Clifford-centric language for stabiliser circuits and affine classical wiring.
SPL++ is a higher-level language that compiles to SPL, adding structured control (classical and Pauli-quantum) and convenience syntax.

Both ultimately **evaluate to relations**:

- If a program uses only linear Clifford primitives and **no nonlinear classical control**, evaluation yields an **affine relation**.
- If a program uses **nonlinear** classical control, evaluation yields a **set relation**.

## Quick start

```bash
# Python 3.10+ recommended
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

# Run examples
spl-rel spl/programs/5_1_3.spl
splpp-rel splpp/programs/teleportation.spl++ --fn main

# Or without installing (module mode)
PYTHONPATH=. python -m spl.scripts.spl_rel spl/programs/5_1_3.spl
PYTHONPATH=. python -m splpp.scripts.splpp_rel splpp/programs/teleportation.spl++ --fn main
```

## Using `make`

A simple `Makefile` is included:

```bash
make venv       # create .venv
make install    # pip install -e .
make test       # run all tests (SPL and SPL++)
make test-spl   # SPL tests only
make test-splpp # SPL++ tests only
make run-spl    # run example SPL program via CLI
make run-splpp  # run example SPL++ program via CLI
make clean      # remove caches/build artifacts
```

> The Makefile targets assume `python3` is available and use it by default.

## Project layout

```
spl/
  src/
    parser/        # SPL grammar & parser
      parser.py
    interpreter/   # SPL interpreters
      interpret_spl_affine.py
      interpret_spl_sets.py
      interpret_spl.py        # dispatches if needed
    relations/
      affine_relations.py
      set_relations.py
  programs/        # example .spl programs
  tests/           # SPL tests
  scripts/
    spl_rel.py     # CLI entry: "spl-rel"

splpp/
  src/
    parser/
      ast.py       # SPL++ AST, grammar, transformer, parse_splpp
    compiler/
      compiler.py  # SPL++ -> SPL lowering (contains former typecheck / utils)
    interpreter/
      interp.py    # harness to compile & run via SPL interpreter
    __init__.py    # lazy public API
  programs/
  tests/
  scripts/
    splpp_rel.py   # CLI entry: "splpp-rel"

pyproject.toml     # package + console_scripts (spl-rel, splpp-rel)
Makefile
pytest.ini         # lets pytest run from repo root without install
```

---

## How the pipelines work

### SPL: direct interpretation
```
SPL source  --parse-->  SPL AST  --interpret_affine/sets-->  Relation
                                      |
                                      +-- affine (default) if no nonlinear control
                                      +-- sets if nonlinear constructs encountered
```

### SPL++: compile then interpret
```
SPL++ source  --parse_splpp-->  SPL++ AST  --compile-->  SPL text
SPL text      --parse_spl-----> SPL AST   --interpret_affine/sets--> Relation
```

- **Affine relation** backend is used when the resulting SPL uses only linear Clifford + affine classical wiring.
- **Set relation** backend is used when nonlinear classical control is exercised (e.g., branching by arbitrary classical predicates that don’t remain affine).

---

## Syntax cheat-sheet

### Global
- **Dimension**: `dim 2;` (or any prime power you support)
- **Types**: `Dit` (classical), `Qdit` (quantum)
- **Function kinds**:
  - `@Pauli`    — Pauli-only routines (no init/qinit/meas/prepare)
  - `@Clifford` — Clifford routines (no non-Clifford ops; same purity rules)
  - `@Linear`   — linear/affine classical functions
  - `@Linear fn`, `@Clifford fn`, `@Pauli fn` all use SPL statements with admissibility enforced by kind.

### SPL (core statements)

```
// Initialise / discard / measure
init x;                 // classical Dit register (default 0, or "init x = p;")
qinit q;                // quantum Qdit (default |0>, or "qinit q = |p>;")
discard x;  disc x;     // discard classical
meas q -> x;            // measure q into classical x

// Apply gates
q *= X;                 // unary gate
q *= Z;
x *= F;                 // classical linear op if defined
(a,b) *= CX;            // binary gate; tuple on LHS for multi-arg ops

// Affine classical assignment
y = A * x;              // linear/affine step (matrix A over F_p)

// Classical control
ctrl b: q *= X;         // run block if bit b==1

// Functions
@Clifford fn bell(a: Qdit, b: Qdit) -> Qdit, Qdit { ... }
@Linear   fn lin(a: Dit) -> Dit { ... }
@Pauli    fn y(t: Qdit) -> Qdit { ... }

return t;               // explicit returns allowed
```

Constraints:
- `init`, `qinit`, `meas`, `prepare` are **not** allowed inside `@Clifford` / `@Pauli` bodies if your purity rules forbid them (the compiler enforces).
- Non-unitary ops must specify explicit outputs; unitary ops may omit or use identical outs == ins.

### SPL++ (sugar + structured control)

```
@Clifford fn main() -> Qdit {
  qinit t;
  init b = 0;

  # classical control on b
  cctrl b: apply X(t);

  # Pauli quantum control
  @Pauli fn Y(u: Qdit) -> Qdit { apply Z(u); apply X(u); return u; }
  qctrl t: apply Y(t);

  return t;
}
```

Key constructs:
- `apply G(args...) -> outs...;` — uniform call form for gates/routines
- `cctrl b: <block>;`             — classical control (potentially nonlinear)
- `qctrl q: <Pauli-routine>;`     — quantum control, **only** over `@Pauli` routines
- Same `init/qinit/meas/discard` as SPL, with the same purity constraints by function kind.

---

## CLIs

After installation (`pip install -e .`) you get two entry points:

```bash
# Interpret an .spl program (prints a kernel-view of the relation)
spl-rel spl/programs/5_1_3.spl

# Compile an .spl++ file, select function, then interpret as a relation
splpp-rel splpp/programs/teleportation.spl++ --fn main
```

Without installing, use module mode:

```bash
PYTHONPATH=. python -m spl.scripts.spl_rel spl/programs/5_1_3.spl
PYTHONPATH=. python -m splpp.scripts.splpp_rel splpp/programs/teleportation.spl++ --fn main
```

---

## Testing

```bash
# All tests
make test

# Separate
make test-spl
make test-splpp
```

> If a test references an optional external package (e.g. `qdsl`) it is guarded and will be **skipped** when the dependency is missing.

---

## Troubleshooting

- **“No module named spl” / “No module named splpp”**
  Either install (`pip install -e .`) or run with `PYTHONPATH=. python -m ...` as shown above.

- **`Stmt` not defined (SPL++ parser)**
  Ensure `splpp/src/parser/ast.py` defines `class Stmt` **before** any subclasses and the Lark `_ToAST` transformer appears **after** the AST classes; keep `from __future__ import annotations` at the very top.

- **Interpretation call**
  All SPL interpreters expect an SPL **program AST**: call `interpret(prog)` (not just `interpret()`).

---

## License

TBD.

---

# SPL++ (high-level language)

SPL++ adds functions, types, control, and a compiler that **lowers to SPL**.

## Core ideas

- **Types**: `Dit`, `Qdit`, `Bool`.
- **Dimension**: `dim p;` sets the prime field \(\mathbb{F}_p\) for both classical and quantum arithmetic.
- **Functions**:
  - `fn main(args) { ... }` is the entry point. No return types.
  - `@Kind fn Name(args) -> outs { ... }` declares a reusable routine.
    - `Kind ∈ {Pauli, Cliffod, Linear, Nonlinear}` is a **capability** bound. The compiler checks it.
    - Outputs are a comma list of `Dit`/`Qdit` types.
- **Statements**:
  - State: `init x;`, `init x = k;`, `qinit q;`, `qinit q = k;`, `qinit q = mixed;`, `meas q;`, `prep q;`
  - Apply: `apply G(a, b, ...)` or with explicit outs `->`
  - Quantum control: `qctrl c: apply X(t)` where `c: Qdit` is the quantum control. Target must be **Pauli**.
  - Classical control: `cctrl c: apply X(t)` where `c: Dit` is the control. Target must be **Pauli**.
  - Boolean and arithmetic: `let b: Bool = (a < 3 and not z); if b { ... } else { ... }`
  - Utilities: `assert equal F G;`, `assert included F G;`, `print spl Teleport;`, `dagger U as U_d;`, `return vars;`
- **Gates**:
  - Unitary: `X, Z, S, F, T, CX, SWAP, MUL_k` (with integer parameter `k` for `MUL`).
  - Classical transforms: `copy, sum, plusone, and`.
- **Outs rule**: For **unitaries**, either omit outputs or set `outs == ins` in the same order. Non-unitaries must specify outputs.
- **Measurement and preparation**: Use `meas q;` and `prep q;` statements, not as `apply`.

## Kind and control constraints

- `qctrl` only over **Pauli** targets. It yields a Clifford. Attempting `qctrl` over `@Clifford` rejects at compile time. fileciteturn1file0
- `cctrl` over **Pauli** is Linear. `cctrl` over **Clifford** is marked Nonlinear for future work. fileciteturn1file0
- Branching and `and` make a function **Nonlinear** by inference. fileciteturn1file0

## Lowering to SPL

The compiler expands:
- Booleans via `init/copy/sum/plusone/and` only.
- Gate applications directly into SPL `*= ...` or classical `= TRANSFORM * ...` with names preserved. fileciteturn1file2

---

## Examples: Teleportation in SPL and SPL++

### Teleportation in **SPL**

```spl
context { in: qpit }

% initialize registers
qinit x
qinit out

% prepare Bell pair
x *= F
(x, out) *= CX

% Bell measurement
(in, x) *= CX
in *= F

% measure outcomes
meas x       % i
meas in      % j

% corrections
ctrlX x  out
ctrlZ in out

% clean ancillae
disc in
disc x
```

This denotes the **identity** relation from input `in` to output `out` over \(\mathbb{F}_p\) (tested in `test_spl_affine.py`). fileciteturn1file3

### Teleportation in **SPL++**

```spl
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
    // Example: compile or assert against other specs
    print spl Teleport;
}
```

The compiler lowers `Teleport` to SPL equivalent to the SPL program above, subject to the outs rule and control constraints. fileciteturn1file1 fileciteturn1file2

---

## Using the compiler

```python
from splpp.parser.ast import parse_splpp
from splpp.compiler.compiler import Compiler

P = parse_splpp(open("teleportation.spl++").read())
fns = {d.name: d for d in P.decls}
comp = Compiler(P.dim or 5, fns=fns)
spl_text = comp.compile_function_to_spl(fns["Teleport"])
print(spl_text)
```
This emits SPL with a `context` block and body lines ready for the SPL interpreter. fileciteturn1file2
