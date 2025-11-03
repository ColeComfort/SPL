
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from spl.src.parser.parser import (
    Program, Init, QInit, Discard, Meas, ApplyGate, AffineAssign, Ctrl, Skip, _names_of
)

# Internal register typing used in Program.context
C_TY = "pit"
Q_TY = "qpit"

@dataclass
class Chunk:
    kind: str                    # "AFFINE" or "CLASSICAL"
    stmts: List[object]
    live_in: Dict[str, str]      # ordered by stable global order snapshot

def _stmt_tag(s: object) -> str:
    """
    Classify a single statement:
      - 'AFFINE_ONLY' for q/quantum or non-classical transforms.
      - 'CLASSICAL_AND' for z = and * (x,y).
      - 'CLASSICAL_AFF' for classical affine ops: init, disc, copy, sum, plusone, skip.
    """
    if isinstance(s, (QInit, Meas, ApplyGate, Ctrl)):
        return "AFFINE_ONLY"
    if isinstance(s, Skip):
        return "CLASSICAL_AFF"
    if isinstance(s, Init) or isinstance(s, Discard):
        return "CLASSICAL_AFF"
    if isinstance(s, AffineAssign):
        t = str(getattr(s, "transform", "")).strip().lower()
        if t == "and":
            return "CLASSICAL_AND"
        if t in {"copy", "sum", "plusone"}:
            return "CLASSICAL_AFF"
        # All other transforms are treated as affine-only
        return "AFFINE_ONLY"
    # Fallback: treat unknown nodes as affine-only to be safe
    return "AFFINE_ONLY"

def _live_snapshot_ordered(env: "OrderedDict[str,str]") -> Dict[str,str]:
    return OrderedDict((k, env[k]) for k in env.keys())

def _scan_classical_run(tags: List[str], i: int) -> Tuple[int, int, List[int]]:
    """
    Given tags list and index i at a classical tag, scan forward while tags are classical.
    Return (start, end_exclusive, indices_of_AND_within_run).
    """
    n = len(tags)
    j = i
    and_idxs: List[int] = []
    while j < n and tags[j] in {"CLASSICAL_AFF", "CLASSICAL_AND"}:
        if tags[j] == "CLASSICAL_AND":
            and_idxs.append(j)
        j += 1
    return i, j, and_idxs


def chunk_program(prog: Program) -> List[Chunk]:
    """
    Build maximal alternating chunks per spec:
      - Classical chunks are maximal segments starting at the first 'and' and covering the entire contiguous classical run.
      - Segments with only classical-affine ops and no 'and' are treated as affine chunks.
      - Affine chunks contain any mix of AFFINE_ONLY and CLASSICAL_AFF but no CLASSICAL_AND.
    Each chunk carries a live-in context snapshot containing all live variables.
    """
    stmts = list(prog.stmts)
    tags = [_stmt_tag(s) for s in stmts]

    # Build stable global order and live types
    from collections import OrderedDict as OD
    live = OD()  # name -> type
    ctx = getattr(prog, "context", None) or {}
    for name in sorted(ctx.keys()):
        ty = str(ctx[name]).strip().lower()
        live[name] = ty

    chunks: List[Chunk] = []
    i = 0
    n = len(stmts)
    while i < n:
        tag = tags[i]
        if tag in {"CLASSICAL_AFF", "CLASSICAL_AND"}:
            # scan the whole classical run
            run_i, run_j, and_idxs = _scan_classical_run(tags, i)
            if not and_idxs:
                # Entire run is an affine chunk
                live_in = _live_snapshot_ordered(live)
                chunks.append(Chunk("AFFINE", stmts[run_i:run_j], live_in))
                for s in stmts[run_i:run_j]:
                    _update_liveness(live, s)
                i = run_j
                continue
            # Classical run containing at least one 'and' becomes one CLASSICAL chunk
            live_in = _live_snapshot_ordered(live)
            chunks.append(Chunk("CLASSICAL", stmts[run_i:run_j], live_in))
            for s in stmts[run_i:run_j]:
                _update_liveness(live, s)
            i = run_j
            continue
        else:
            # Build affine chunk as contiguous AFFINE_ONLY statements
            start = i
            j = i
            while j < n and tags[j] == "AFFINE_ONLY":
                j += 1
            if j == start:
                # Current statement is neither AFFINE_ONLY nor CLASSICAL_* (shouldn't happen), advance
                j += 1
            live_in = _live_snapshot_ordered(live)
            chunks.append(Chunk("AFFINE", stmts[start:j], live_in))
            for s in stmts[start:j]:
                _update_liveness(live, s)
            i = j
            continue
    return chunks
def _update_liveness(live: "OrderedDict[str,str]", s: object) -> None:
    """
    Maintain live variable set and types across statements.
    """
    if isinstance(s, Init):
        for n in _names_of(s.reg):
            if n in live:
                raise ValueError(f"re-init of live variable {n}")
            live[n] = C_TY
        return
    if isinstance(s, QInit):
        for n in _names_of(s.reg):
            if n in live:
                raise ValueError(f"re-qinit of live variable {n}")
            live[n] = Q_TY
        return
    if isinstance(s, Discard):
        for n in _names_of(s.reg):
            if n not in live:
                raise ValueError(f"discard of non-live variable {n}")
            del live[n]
        return
    if isinstance(s, Meas):
        for n in _names_of(s.reg):
            if n not in live or live[n] != Q_TY:
                raise ValueError(f"meas requires live quantum var {n}")
            live[n] = C_TY
        return
    if isinstance(s, AffineAssign):
        # ensure sources are live
        for n in _names_of(s.src):
            if n not in live:
                raise ValueError(f"use of uninitialized variable {n}")
        # destination names become live if not present; type follows sources if present, else classical by default
        for n in _names_of(s.dst):
            if n not in live:
                live[n] = C_TY
        return
    if isinstance(s, ApplyGate):
        for n in _names_of(s.reg):
            if n not in live or live[n] != Q_TY:
                raise ValueError(f"quantum gate requires live quantum var {n}")
        return
    if isinstance(s, Ctrl):
        # control reg must be classical
        for n in _names_of(s.ctrl):
            if n not in live or live[n] != C_TY:
                raise ValueError(f"classical control requires live classical var {n}")
        for n in _names_of(s.target):
            if n not in live or live[n] != Q_TY:
                raise ValueError(f"classical control requires live quantum target {n}")
        return
    if isinstance(s, Skip):
        return
    # Unknown node: no effect
    return
