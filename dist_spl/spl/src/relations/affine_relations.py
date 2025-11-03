# affine_relations.py
# Affine relations over F_p, represented as affine subspaces in parametric form:
#   S = shift + basis * t,  t ∈ F_p^k
# A relation n -> m is an affine subspace of F_p^(n+m).
# Composition (n->m) ; (m->ℓ) is implemented as relational composition:
#   {(x,z) | ∃y. (x,y)∈R and (y,z)∈S}
# by intersecting embeddings in F_p^(n+m+ℓ) and projecting away y.

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# ---------- finite field utilities ----------
def modp(a: int, p: int) -> int:
    return a % p

def invp(a: int, p: int) -> int:
    # p is an odd prime; assume a != 0 mod p
    return pow(a, -1, p)

def mat_mod(A: List[List[int]], p: int) -> List[List[int]]:
    return [[modp(x, p) for x in row] for row in A]

def vec_mod(v: List[int], p: int) -> List[int]:
    return [modp(x, p) for x in v]

def zeros(r: int, c: int) -> List[List[int]]:
    return [[0]*c for _ in range(r)]

def eye(n: int) -> List[List[int]]:
    M = zeros(n, n)
    for i in range(n):
        M[i][i] = 1
    return M

def vcat(A: List[List[int]], B: List[List[int]]) -> List[List[int]]:
    if A and B: assert len(A[0]) == len(B[0])
    return (A or []) + (B or [])

def hcat(A: List[List[int]], B: List[List[int]]) -> List[List[int]]:
    if not A: return [row[:] for row in B]
    if not B: return [row[:] for row in A]
    assert len(A) == len(B)
    return [ra + rb for ra, rb in zip(A, B)]

def mv_mul(A: List[List[int]], v: List[int], p: int) -> List[int]:
    r = len(A)
    c = len(A[0]) if A else 0
    assert len(v) == c
    out = [0]*r
    for i in range(r):
        s = 0
        row = A[i]
        for j in range(c):
            s += row[j] * v[j]
        out[i] = s % p
    return out

def mm_mul(A: List[List[int]], B: List[List[int]], p: int) -> List[List[int]]:
    r, k = len(A), (len(A[0]) if A else 0)
    assert k == (len(B) if B else 0)
    c = len(B[0]) if B else 0
    C = zeros(r, c)
    for i in range(r):
        for j in range(c):
            s = 0
            ai = A[i]
            for t in range(k):
                s += ai[t] * B[t][j]
            C[i][j] = s % p
    return C

# RREF over F_p, returns (R, pivots) where R is row-reduced and pivots are pivot column indices
def rref(A: List[List[int]], p: int) -> Tuple[List[List[int]], List[int]]:
    A = [row[:] for row in A]
    m = len(A)
    n = len(A[0]) if A else 0
    pivots: List[int] = []
    r = 0
    for c in range(n):
        # find pivot
        pivot = None
        for i in range(r, m):
            if A[i][c] % p != 0:
                pivot = i; break
        if pivot is None:
            continue
        A[r], A[pivot] = A[pivot], A[r]
        inv = invp(A[r][c] % p, p)
        # normalize row r
        for j in range(c, n):
            A[r][j] = (A[r][j] * inv) % p
        # eliminate other rows
        for i in range(m):
            if i == r: continue
            factor = A[i][c] % p
            if factor != 0:
                for j in range(c, n):
                    A[i][j] = (A[i][j] - factor*A[r][j]) % p
        pivots.append(c)
        r += 1
        if r == m: break
    return A, pivots

# Solve A x = b over F_p. Returns (x0, N) where general solution is x = x0 + N * t.
# N has shape (n x r), columns span the nullspace.
def solve_affine(A: List[List[int]], b: List[int], p: int) -> Tuple[List[int], List[List[int]]]:
    m = len(A); n = len(A[0]) if A else 0
    Aug = [A[i][:] + [b[i] % p] for i in range(m)]
    R, piv = rref(Aug, p)
    for i in range(m):
        if all(R[i][j] == 0 for j in range(n)) and (R[i][n] % p != 0):
            raise ValueError("No solution")
    is_pivot = [False]*n
    for c in piv: is_pivot[c] = True
    free_cols = [j for j in range(n) if not is_pivot[j]]
    # particular solution
    x0 = [0]*n
    pivot_row_for = [-1]*n
    ri = 0
    for c in range(n):
        if ri < len(piv) and piv[ri] == c:
            pivot_row_for[c] = ri
            ri += 1
    for c in range(n):
        i = pivot_row_for[c]
        if i != -1:
            x0[c] = R[i][n] % p
    # nullspace basis
    N_cols = []
    for f in free_cols:
        v = [0]*n
        v[f] = 1
        for idx, c in enumerate(piv):
            v[c] = (-R[idx][f]) % p
        N_cols.append(v)
    # convert list of column vectors into an n x r matrix
    if N_cols:
        N = [ [N_cols[j][i] for j in range(len(N_cols))] for i in range(n) ]
    else:
        N = [ [] for _ in range(n) ]
    return x0, N

# Choose a column basis from V (d x k) by pivot columns of RREF(V^T)
def column_basis(V: List[List[int]], p: int) -> List[List[int]]:
    """
    Return a column-independent basis of V (d x k) by keeping pivot columns of RREF(V).
    Robust to ragged rows: pads rows with zeros to the max row length.
    Output has shape d x r, where r = rank(V) (could be 0).
    """
    if not V:
        return V
    d = len(V)
    k = max((len(row) for row in V), default=0)
    if k == 0:
        return [ [] for _ in range(d) ]

    # Pad rows to make V rectangular d x k
    Vr = [ (row + [0]*(k - len(row))) if len(row) < k else row[:] for row in V ]

    # RREF on V (not V^T) to get pivot columns among 0..k-1
    R, piv = rref(Vr, p)   # piv ⊆ {0,…,k-1}

    if not piv:
        return [ [] for _ in range(d) ]

    # Select those columns from Vr
    return [ [Vr[i][j] for j in piv] for i in range(d) ]



# ---------- affine subspace in parametric form ----------
@dataclass
class AffineSubspace:
    p: int                 # prime
    dim: int               # ambient dimension
    shift: List[int]       # length dim
    basis: List[List[int]] # (dim x k) matrix; columns span the linear part

    def __post_init__(self):
        assert self.p >= 3 and all(0 <= x % self.p < self.p for x in self.shift)
        assert len(self.shift) == self.dim
        if self.basis:
            assert len(self.basis) == self.dim
            self.basis = mat_mod(self.basis, self.p)
        self.shift = vec_mod(self.shift, self.p)

    def canonicalize(self):
        self.basis = column_basis(self.basis, self.p)

    # Apply projection: keep coordinates in 'keep' (indices)
    def project(self, keep: List[int]) -> "AffineSubspace":
        k = len(keep)
        if k == 0:
            return AffineSubspace(self.p, 0, [], [])
        P = zeros(len(keep), self.dim)
        for i, idx in enumerate(keep):
            P[i][idx] = 1
        new_shift = mv_mul(P, self.shift, self.p)
        new_basis = mm_mul(P, self.basis, self.p) if self.basis else zeros(k, 0)
        out = AffineSubspace(self.p, k, new_shift, new_basis)
        out.canonicalize()
        return out

    # Intersection of two affine subspaces in the same ambient space
    def intersect(self, other: "AffineSubspace") -> "AffineSubspace":
        assert self.p == other.p and self.dim == other.dim
        p = self.p
        B1 = self.basis
        B2 = other.basis
        d = self.dim
        k1 = len(B1[0]) if B1 else 0
        k2 = len(B2[0]) if B2 else 0
        # Build block matrix [B1 | -B2] of size d x (k1+k2)
        if k2 > 0:
            negB2 = [[(-B2[i][j]) % p for j in range(k2)] for i in range(d)]
            M = hcat(B1, negB2) if k1 > 0 else negB2
        else:
            M = B1
        b = [(other.shift[i] - self.shift[i]) % p for i in range(d)]
        x0, N = solve_affine(M, b, p)     # theta = x0 + N * u, theta ∈ F_p^(k1+k2)
        # take t1 part (first k1 rows of N)
        t1_0 = x0[:k1] if (k1 > 0) else []
        N_top = N[:k1] if (k1 > 0 and N) else [ [] for _ in range(0) ]
        inter_shift = [(self.shift[i] + sum(B1[i][j]*t1_0[j] for j in range(k1))) % p for i in range(d)]
        inter_basis = mm_mul(B1, N_top, p) if (k1 > 0 and N_top and len(N_top[0]) > 0) else zeros(d, 0)
        out = AffineSubspace(p, d, inter_shift, inter_basis)
        out.canonicalize()
        return out

# ---------- affine relations ----------
@dataclass
class AffineRelation:
    p: int
    n_in: int
    n_out: int
    subspace: AffineSubspace  # ambient_dim == n_in + n_out, coords = (x,z)
    # Optional printed names for inputs and outputs. Keys are 0-based indices.
    input_names: Dict[int, str]
    output_names: Dict[int, str]

    @staticmethod
    def from_shift_basis(
        p: int,
        n: int,
        m: int,
        shift: List[int],
        basis: List[List[int]],
        input_names: Optional[Dict[int, str]] = None,
        output_names: Optional[Dict[int, str]] = None,
    ) -> "AffineRelation":
        d = n + m
        assert len(shift) == d and (not basis or len(basis) == d)
        sub = AffineSubspace(p, d, shift, basis)
        in_names = ({j: "" for j in range(n)} if input_names is None else {j: input_names.get(j, "") for j in range(n)})
        out_names = ({j: "" for j in range(m)} if output_names is None else {j: output_names.get(j, "") for j in range(m)})
        return AffineRelation(p, n, m, sub, in_names, out_names)

    # Compose: (n->m) ; (m->ℓ) -> (n->ℓ)
    def compose(self, other: "AffineRelation") -> "AffineRelation":
        assert self.p == other.p and self.n_out == other.n_in
        p = self.p
        n, m, ell = self.n_in, self.n_out, other.n_out
        d_all = n + m + ell

        # Lift R (x,y) into (x,y,z) with z free
        R = self.subspace
        kR = len(R.basis[0]) if R.basis else 0
        shift_R_lift = R.shift[:] + [0]*ell
        basis_R_lift = [row[:] for row in R.basis] if kR > 0 else zeros(n+m, 0)
        if ell > 0:
            basis_R_lift = vcat(basis_R_lift, zeros(ell, kR))
            Zfree = zeros(d_all, ell)
            for j in range(ell):
                Zfree[n + m + j][j] = 1
            basis_R_lift = hcat(basis_R_lift, Zfree)
        R_lift = AffineSubspace(p, d_all, shift_R_lift, basis_R_lift)

        # Lift S (y,z) into (x,y,z) with x free
        S = other.subspace
        kS = len(S.basis[0]) if S.basis else 0
        shift_S_lift = [0]*n + S.shift[:]
        basis_S_lift = zeros(d_all, 0)
        if n > 0:
            Xfree = zeros(d_all, n)
            for j in range(n):
                Xfree[j][j] = 1
            basis_S_lift = hcat(basis_S_lift, Xfree)
        if kS > 0:
            YZ = zeros(d_all, kS)
            for i in range(m + ell):
                for j in range(kS):
                    YZ[n + i][j] = S.basis[i][j]
            basis_S_lift = hcat(basis_S_lift, YZ)
        S_lift = AffineSubspace(p, d_all, shift_S_lift, basis_S_lift)

        # Intersection in (x,y,z)
        I = R_lift.intersect(S_lift)

        # Project to (x,z): keep indices [0..n-1] ∪ [n+m .. n+m+ell-1]
        keep = list(range(0, n)) + list(range(n + m, n + m + ell))
        P = I.project(keep)

        # Propagate names: inputs from self, outputs from other.
        out = AffineRelation(
            p, n, ell, P,
            input_names={j: self.input_names.get(j, "") for j in range(n)},
            output_names={j: other.output_names.get(j, "") for j in range(ell)}
        )
        return out

    def with_names(self, input_names: Dict[int, str], output_names: Dict[int, str]) -> "AffineRelation":
        """Return a copy with updated names (values copied)."""
        return AffineRelation(
            self.p, self.n_in, self.n_out, self.subspace,
            {j: input_names.get(j, "") for j in range(self.n_in)},
            {j: output_names.get(j, "") for j in range(self.n_out)}
        )

    def __str__(self) -> str:
        """
        Image-form show with labels centered above numeric columns.
        - Labels: comma-delimited, no pipe; each label centered over its column.
        - Numbers: spaces with ' | ' between inputs and outputs.
        - One blank line between s^T and B^T.
        - Type uses ⊕ of F_p and Q(F_p^2); empty side is {*}.
        """
        p = self.p
        n, m = self.n_in, self.n_out
        d = n + m

        in_headers  = [self.input_names.get(j, "") for j in range(n)]
        out_headers = [self.output_names.get(j, "") for j in range(m)]

        s = [x % p for x in self.subspace.shift]   # length d
        B = self.subspace.basis                    # d x r (columns = generators)
        r = (len(B[0]) if B else 0)

        # --- numeric column widths from s^T and B^T rows ---
        col_vals = [[] for _ in range(d)]
        for j in range(d): col_vals[j].append(s[j])
        if r > 0:
            for i in range(d):
                for j in range(r):
                    col_vals[i].append(B[i][j] % p)

        def numw(vals): return max(1, *(len(str(v % p)) for v in vals)) if vals else 1
        in_w  = [max(1, len(in_headers[j]),  numw(col_vals[j]))       for j in range(n)]
        out_w = [max(1, len(out_headers[j]), numw(col_vals[n + j]))   for j in range(m)]

        # --- inner numeric strings (spaces; keep ' | ') ---
        def inner_nums(vec):
            left  = " ".join(str(vec[j] % p).rjust(in_w[j])      for j in range(n)) if n>0 else ""
            right = " ".join(str(vec[n + j] % p).rjust(out_w[j]) for j in range(m)) if m>0 else ""
            if n>0 and m>0: return left + " | " + right
            if n>0: return left
            if m>0: return right
            return ""

        # --- centered, comma-delimited labels (no pipe), fixed inner width ---
        LEFT_W  = (sum(in_w)  + max(n-1, 0))
        RIGHT_W = (sum(out_w) + max(m-1, 0))
        SEP_W   = 3 if (n>0 and m>0) else 0  # width of " | " in numeric rows
        INNER_W = LEFT_W + SEP_W + RIGHT_W

        def centered_label_line():
            # Build left buffer
            def build_side(headers, widths):
                L = len(headers)
                side_w = sum(widths) + max(L-1, 0)
                buf = [" "] * side_w
                pos = 0
                for j in range(L):
                    w = widths[j]
                    h = headers[j]
                    k = min(len(h), w)
                    start = pos + (w - k) // 2
                    # place centered label (truncate if needed)
                    for t in range(k):
                        buf[start + t] = h[t]
                    # place comma as delimiter exactly in the 1-space separator slot
                    pos += w
                    if j < L-1:
                        buf[pos] = ","  # replace the single separator space with a comma
                        pos += 1
                return "".join(buf)

            left_lbl  = build_side(in_headers,  in_w)  if n>0 else ""
            right_lbl = build_side(out_headers, out_w) if m>0 else ""
            # pad each side to its numeric width so total equals INNER_W
            left_lbl  = left_lbl.ljust(LEFT_W)
            right_lbl = right_lbl.ljust(RIGHT_W)
            return left_lbl + (" " * SEP_W) + right_lbl

        # --- fixed bracket column so rows line up ---
        LABEL_COL = max(len("s^T ="), len("B^T =")) + 1
        def emit_row(label, inner):
            return f"{label}{' ' * max(1, LABEL_COL - len(label))}[{inner}]"

        # --- modality types from headers ---
        def modality(headers):
            ty, i = [], 0
            while i < len(headers):
                h = headers[i]
                if h.endswith(".x"):
                    base = h[:-2]
                    if i+1 < len(headers) and headers[i+1] == base + ".z":
                        ty.append("Q(F_p^2)"); i += 2; continue
                ty.append("F_p"); i += 1
            return " ⊕ ".join(ty) if ty else "{*}"

        dom_ty = modality(in_headers)
        cod_ty = modality(out_headers)

        # --- assemble ---
        lines = [f"AffineRelation over F_{p}: {n}->{m}"]

        lbl = centered_label_line()
        if lbl.strip() != "":
            lines.append(" " * (LABEL_COL + 1) + lbl[:INNER_W])

        lines.append(emit_row("s^T =", inner_nums(s)))
        lines.append("")  # blank line

        if r == 0:
            lines.append("B^T = ∅")
        else:
            for j in range(r):
                row = [B[i][j] % p for i in range(d)]
                label = "B^T =" if j == 0 else ""
                lines.append(emit_row(label, inner_nums(row)))

        lines.append("")
        lines.append(f"R = s + Im(B)  ⊆  F_p^{{{n}+{m}}}")
        lines.append(f"Type: {dom_ty}  ->  {cod_ty}")
        return "\n".join(lines)


    def to_kernel_str(self) -> str:
        """
        Kernel (constraint) view with centered labels above numeric columns.
          prints rows as: [ Cx  |  Cy  ||  b ]
        - Labels: comma-delimited, no pipe, centered per column; never overshoot numeric block.
        - Numbers: spaces, keep ' | ' between inputs/outputs and ' || ' before RHS.
        - Types: F_p for classical, Q(F_p^2) for consecutive .x/.z; empty side is {*}.
        """
        p = self.p
        n, m = self.n_in, self.n_out
        d = n + m

        in_headers  = [self.input_names.get(j, "") for j in range(n)]
        out_headers = [self.output_names.get(j, "") for j in range(m)]

        s = [x % p for x in self.subspace.shift]
        B = self.subspace.basis
        r = (len(B[0]) if B else 0)

        # ---- Build C: row-basis of ker(B^T) ----
        if not B or r == 0:
            C = [[1 if i == j else 0 for j in range(d)] for i in range(d)]
        else:
            BT = [[B[i][j] for i in range(d)] for j in range(r)]  # r x d
            RBT, piv = rref(BT, p)
            piv_set = set(piv)
            free_cols = [j for j in range(d) if j not in piv_set]
            C = []
            for f in free_cols:
                v = [0]*d
                v[f] = 1
                for i, pc in enumerate(piv):
                    row_i = RBT[i]
                    ssum = 0
                    for j in range(d):
                        if j == pc: continue
                        ssum = (ssum + row_i[j]*v[j]) % p
                    v[pc] = (-ssum) % p
                C.append(v)

        b = mv_mul(C, s, p) if C else []
        Aug = [C[i][:] + [b[i] % p] for i in range(len(C))]
        R2, _ = rref(Aug, p) if Aug else ([], [])

        # ---- widths from numeric table ----
        def numw(vals): return max(1, *(len(str(int(v) % p)) for v in vals)) if vals else 1
        in_cols  = list(zip(*[row[:n]    for row in R2])) if n>0 and R2 else [[] for _ in range(n)]
        out_cols = list(zip(*[row[n:n+m] for row in R2])) if m>0 and R2 else [[] for _ in range(m)]
        rhs_col  = [row[n+m] for row in R2] if R2 else []

        in_w  = [max(1, len(in_headers[j]),  numw(list(in_cols[j]) )) for j in range(n)]
        out_w = [max(1, len(out_headers[j]), numw(list(out_cols[j]))) for j in range(m)]
        rhs_w = max(1, len("b"), numw(rhs_col))

        LEFT_W  = (sum(in_w)  + max(n-1, 0))
        RIGHT_W = (sum(out_w) + max(m-1, 0))
        SEP_W   = 3 if (n>0 and m>0) else 0            # width of " | "
        INNER_W = LEFT_W + SEP_W + RIGHT_W             # width inside brackets, excluding RHS
        RHS_SEP = " || " if (n+m)>0 else "|| "

        # ---- numeric row builder ----
        def inner_nums(row):
            left  = " ".join(str(row[j] % p).rjust(in_w[j])      for j in range(n)) if n>0 else ""
            right = " ".join(str(row[n+j] % p).rjust(out_w[j])   for j in range(m)) if m>0 else ""
            core  = left + (" | " if n>0 and m>0 else "") + right
            rhs   = str(row[n+m] % p).rjust(rhs_w)
            return core + RHS_SEP + rhs

        # ---- centered, comma-delimited label line (no pipe), exact INNER_W width ----
        def centered_label_line():
            def build_side(headers, widths):
                L = len(headers)
                side_w = sum(widths) + max(L-1, 0)    # spaces between columns
                buf = [" "] * side_w
                pos = 0
                for j in range(L):
                    w = widths[j]
                    h = headers[j]
                    k = min(len(h), w)                # truncate within column width
                    start = pos + (w - k)//2          # center
                    for t in range(k):
                        buf[start + t] = h[t]
                    pos += w
                    if j < L-1:
                        buf[pos] = ","                # place comma in the single separator slot
                        pos += 1
                return "".join(buf).ljust(side_w)

            left_lbl  = build_side(in_headers,  in_w)  if n>0 else ""
            right_lbl = build_side(out_headers, out_w) if m>0 else ""
            return (left_lbl.ljust(LEFT_W)
                    + (" " * SEP_W)
                    + right_lbl.ljust(RIGHT_W))

        # ---- fixed bracket column so rows line up ----
        LABEL_COL = max(len("C ="), len("row")) + 1
        def emit_row(prefix, inner):
            pad = " " * max(1, LABEL_COL - len(prefix))
            return f"{prefix}{pad}[{inner}]"

        # ---- modality types ----
        def modality(headers):
            ty, i = [], 0
            while i < len(headers):
                h = headers[i]
                if h.endswith(".x"):
                    base = h[:-2]
                    if i+1 < len(headers) and headers[i+1] == base + ".z":
                        ty.append("Q(F_p^2)"); i += 2; continue
                ty.append("F_p"); i += 1
            return " ⊕ ".join(ty) if ty else "{*}"

        dom_ty = modality(in_headers)
        cod_ty = modality(out_headers)

        # ---- assemble ----
        lines = [f"AffineRelation (kernel view) over F_{p}: {n}->{m}"]

        if n>0 or m>0:
            lines.append(" " * (LABEL_COL + 1) + centered_label_line())

        if not R2:
            lines.append("constraints: ⊤")
        else:
            for i, row in enumerate(R2):
                prefix = "C =" if i == 0 else ""
                lines.append(emit_row(prefix, inner_nums(row)))

        lines.append("")
        lines.append(f"Type: {dom_ty}  ->  {cod_ty}")
        return "\n".join(lines)


    # identity and equality based on __str__()
    def __eq__(self, other) -> bool:
        if not isinstance(other, AffineRelation):
            return NotImplemented
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))



# ---------- minimal demo ----------
    def to_set_relation(self) -> "SetRelation":
        """
        Enumerate this affine relation as a SetRelation, preserving names.
        """
        from spl.src.relations.set_relations import SetRelation  # local import to avoid cycles
        p = self.p
        n = self.n_in
        m = self.n_out
        B = self.subspace.basis
        d = n + m
        r = len(B[0]) if B else 0
        cols = [[B[i][j] % p for i in range(d)] for j in range(r)] if r>0 else []
        shift = [v % p for v in self.subspace.shift]
        pairs = set()
        # iterate parameters
        def prod(pv, rdim):
            if rdim == 0:
                yield []
                return
            from itertools import product
            for t in product(range(pv), repeat=rdim):
                yield list(t)
        for t in prod(p, r):
            vec = shift[:]
            for j in range(r):
                for i in range(d):
                    vec[i] = (vec[i] + t[j]*cols[j][i]) % p
            x = tuple(vec[:n]); y = tuple(vec[n:])
            pairs.add((x,y))
        return SetRelation(p, n, m, pairs, dict(self.input_names), dict(self.output_names))

if __name__ == "__main__":
    # Example over p=5: relation R: x->y defined as y = x + 1  (as an affine subspace in F_5^2)
    p = 5
    # R subset of F_5^(1+1): {(x,y) | y - x = 1}
    # Parametric form: choose parameter t = x. Then (x,y) = (0,1) + t*(1,1)
    R_shift = [0, 1]
    R_basis = [[1], [1]]
    R = AffineRelation.from_shift_basis(p, 1, 1, R_shift, R_basis,
                                        input_names={0: "in"},
                                        output_names={0: "out"})

    # S: y->z defined as z = y + 2
    S_shift = [0, 2]
    S_basis = [[1], [1]]
    S = AffineRelation.from_shift_basis(p, 1, 1, S_shift, S_basis,
                                        input_names={0: "out"},
                                        output_names={0: "z"})

    # Compose: T = R ; S  is x -> z with z = x + 3
    T = R.compose(S)
    print(T)

