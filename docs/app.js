// Robust SPL web frontend: waits for boot, resolves parser/interpreter, supports p

const outEl     = document.getElementById("out");
const srcEl     = document.getElementById("src");
const runBtn    = document.getElementById("run");
const loadBtn   = document.getElementById("load-teleport");
const versionEl = document.getElementById("version");
const toastEl   = document.getElementById("toast");
const primeEl   = document.getElementById("prime");
const statusEl  = document.getElementById("status");

let pyodide;
let bootDone = false;

function toast(msg, ms = 4000) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.style.display = "block";
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => { toastEl.style.display = "none"; }, ms);
}

function isPrime(n) {
  if (!Number.isInteger(n) || n < 2) return false;
  if (n % 2 === 0) return n === 2;
  const r = Math.floor(Math.sqrt(n));
  for (let d = 3; d <= r; d += 2) if (n % d === 0) return false;
  return true;
}

async function loadBinary(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return new Uint8Array(await res.arrayBuffer());
}

async function loadText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return await res.text();
}

async function safePy(code) {
  try { return await pyodide.runPythonAsync(code); }
  catch (e) { throw new Error(String(e)); }
}

async function boot() {
  try {
    if (location.protocol === "file:") {
      throw new Error("Serve via GitHub Pages or a local HTTP server.");
    }
    if (versionEl) versionEl.textContent = new URL(location.href).href;

    statusEl.textContent = "loading Python…";
    pyodide = await loadPyodide();

    statusEl.textContent = "mounting interpreter…";
    const zipBytes = await loadBinary("./spl-run.pyz");
    pyodide.FS.writeFile("/spl-run.pyz", zipBytes, { canOwn: true });
    await safePy(`
import sys
if "/spl-run.pyz" not in sys.path:
    sys.path.insert(0, "/spl-run.pyz")
`);

    statusEl.textContent = "checking deps…";
    await safePy(`
import importlib
try:
    importlib.import_module("lark")
except Exception:
    import micropip
    await micropip.install("lark>=1.1,<2")
`);

    statusEl.textContent = "initialising resolver…";
    // Define run_spl_web *before* enabling buttons
    await safePy(`
import importlib, inspect

def _first_callable(modname, names):
    try:
        m = importlib.import_module(modname)
    except Exception:
        return None, None
    for n in names:
        f = getattr(m, n, None)
        if callable(f):
            return f, f"{modname}.{n}"
    return None, None

def _resolve_entries():
    parser_candidates = [
        ("spl.src.parser.parser", ["parse_spl", "parse"]),
    ]
    interp_candidates = [
        ("spl.src.interpreter.interpret_spl", ["interpret_spl","interpret_program","interpret_to_text","interpret","run"]),
        ("spl.src.interpreter",               ["interpret_spl","interpret_program","interpret_to_text","interpret","run"]),
        ("spl.interpreter",                   ["interpret_spl","interpret_program","interpret_to_text","interpret","run"]),
    ]
    parser_fn = where_p = None
    for mod, names in parser_candidates:
        parser_fn, where_p = _first_callable(mod, names)
        if parser_fn: break
    if not parser_fn:
        raise ImportError("Could not find parser")

    interp_fn = where_i = None
    for mod, names in interp_candidates:
        interp_fn, where_i = _first_callable(mod, names)
        if interp_fn: break
    if not interp_fn:
        raise ImportError("Could not find interpreter")

    # Analyse interpreter signature
    sig = inspect.signature(interp_fn)
    params = list(sig.parameters.values())
    names = [p.name for p in params]

    # Heuristics for parameter names
    P_NAMES = {"p","prime","mod","q","char","field","prime_p"}
    G_NAMES = {"prog","program","ast","tree","parsed","ir"}

    callmode = None
    if len(params) == 1:
        # fn(prog)
        callmode = ("one",)
    elif len(params) == 2:
        # try to map by names first
        if names[0] in P_NAMES and names[1] in G_NAMES:
            callmode = ("kw", ("p","prog"))      # fn(p=?, prog=?)
        elif names[0] in G_NAMES and names[1] in P_NAMES:
            callmode = ("kw", ("prog","p"))      # fn(prog=?, p=?)
        else:
            callmode = ("pos2",)                 # unknown; try positional orders
    else:
        callmode = ("unsupported", len(params), names)

    return parser_fn, interp_fn, callmode

# cache
try:
    _PARSER, _INTERP, _CALLMODE = _resolve_entries()
    _ERR = None
except Exception as e:
    _PARSER = _INTERP = None
    _CALLMODE = None
    _ERR = e

def run_spl_web(src: str, p: int) -> str:
    if _ERR is not None:
        raise _ERR
    prog = _PARSER(src)
    cm = _CALLMODE
    if cm is None:
        raise RuntimeError("Interpreter not resolved")
    if cm[0] == "one":
        out = _INTERP(prog)
    elif cm[0] == "kw":
        order = cm[1]
        if order == ("p","prog"):
            out = _INTERP(p=p, prog=prog)
        else:
            out = _INTERP(prog=prog, p=p)
    elif cm[0] == "pos2":
        # try (p, prog) then (prog, p)
        ok = False
        try:
            out = _INTERP(p, prog); ok = True
        except TypeError:
            out = _INTERP(prog, p); ok = True
        if not ok:
            raise TypeError("Two-arg interpreter did not accept (p, prog) nor (prog, p).")
    else:
        kind, arity, names = cm
        raise TypeError(f"Unsupported interpreter arity {arity} with params {names}")
    return out if isinstance(out, str) else str(out)
`);

    // Load default example
    try {
      srcEl.value = await loadText("./teleportation.spl");
      toast("Loaded teleportation example.", 2000);
    } catch {
      srcEl.placeholder = "Missing ./teleportation.spl";
      toast("Could not load teleportation example.", 5000);
    }

    bootDone = true;
    statusEl.textContent = "ready";
    runBtn.disabled = false;
    loadBtn.disabled = false;
  } catch (e) {
    statusEl.textContent = "boot error";
    outEl.textContent = "Boot failed:\n" + e.message;
    toast("Boot failed. See Output.", 6000);
  }
}

runBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 2000); return; }
  outEl.textContent = "";
  let p = parseInt(primeEl.value, 10);
  if (!isPrime(p)) toast("Warning: p should be prime. Using entered value anyway.", 3000);
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safePy(`run_spl_web(${codeJSON}, ${p})`);
    outEl.textContent = String(result);
    toast("Program ran.", 2000);
  } catch (e) {
    outEl.textContent = "Error running program:\n" + e.message;
    toast("Run failed.", 6000);
  }
};

loadBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 2000); return; }
  try {
    srcEl.value = await loadText("./teleportation.spl");
    toast("Teleportation loaded.", 2000);
  } catch (e) {
    toast("Could not load teleportation.", 6000);
  }
};

boot();

