# Stabiliser Programming Language (SPL & SPL++)

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
