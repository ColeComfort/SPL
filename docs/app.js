// docs/app.js — self-contained: no external runner module needed

const outEl     = document.getElementById("out");
const srcEl     = document.getElementById("src");
const runBtn    = document.getElementById("run");
const loadBtn   = document.getElementById("load-teleport");
const versionEl = document.getElementById("version");
const toastEl   = document.getElementById("toast");

let pyodide;

function toast(msg, ms = 4000) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.style.display = "block";
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => { toastEl.style.display = "none"; }, ms);
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

    pyodide = await loadPyodide();

    // Load the zipapp and add to sys.path
    const zipBytes = await loadBinary("./spl-run.pyz");
    pyodide.FS.writeFile("/spl-run.pyz", zipBytes, { canOwn: true });
    await safePy(`
import sys
if "/spl-run.pyz" not in sys.path:
    sys.path.insert(0, "/spl-run.pyz")
`);

    // Ensure lark is importable (vendored OR install via micropip as fallback)
    await safePy(`
import importlib
try:
    importlib.import_module("lark")
except Exception:
    import micropip
    await micropip.install("lark>=1.1,<2")
`);

    // Define a small helper module in-session that resolves parser & interpreter dynamically
    await safePy(`
import types, importlib

def _first_callable(modname, names):
    try:
        m = importlib.import_module(modname)
    except Exception:
        return None, None
    for n in names:
        f = getattr(m, n, None)
        if callable(f):
            return f, f"{{modname}}.{{n}}"
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
        raise ImportError("Could not find parser among: " + "; ".join(f"{m}.{names}" for m,n in parser_candidates))

    interp_fn = where_i = None
    for mod, names in interp_candidates:
        interp_fn, where_i = _first_callable(mod, names)
        if interp_fn: break
    if not interp_fn:
        raise ImportError("Could not find interpreter among: " + "; ".join(f"{m}.{names}" for m,n in interp_candidates))

    return parser_fn, interp_fn, where_p, where_i

# cache on first import
try:
    _PARSER, _INTERP, _PW, _IW = _resolve_entries()
    _ERR = None
except Exception as e:
    _PARSER = _INTERP = None
    _PW = _IW = ""
    _ERR = e

def run_spl_web(src: str) -> str:
    if _ERR is not None:
        raise _ERR
    prog = _PARSER(src)
    out = _INTERP(prog)
    return out if isinstance(out, str) else str(out)
`);

    // Default example
    try {
      srcEl.value = await loadText("./teleportation.spl");
      toast("Loaded teleportation example.", 2000);
    } catch (e) {
      srcEl.placeholder = "Missing ./teleportation.spl";
      toast("Could not load teleportation example.", 5000);
    }
  } catch (e) {
    if (outEl) outEl.textContent = "Boot failed:\n" + e.message;
    toast("Boot failed. See Output.", 6000);
  }
}

runBtn.onclick = async () => {
  if (!pyodide) return;
  outEl.textContent = "";
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safePy(`
run_spl_web(${codeJSON})
`);
    outEl.textContent = String(result);
    toast("Program ran.", 2000);
  } catch (e) {
    outEl.textContent = "Error running program:\n" + e.message;
    toast("Run failed.", 6000);
  }
};

loadBtn.onclick = async () => {
  try {
    srcEl.value = await loadText("./teleportation.spl");
    toast("Teleportation loaded.", 2000);
  } catch (e) {
    toast("Could not load teleportation.", 6000);
  }
};

boot();

