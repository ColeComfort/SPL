// SPL Online frontend — exact wiring to spl.src.interpreter.interpret_spl.interpret(p, prog, context=None)
// Sends JS and Python errors to #log. Sends Python stdout to #out.

const outEl     = document.getElementById("out");
const logEl     = document.getElementById("log");
const srcEl     = document.getElementById("src");
const runBtn    = document.getElementById("run");
const loadBtn   = document.getElementById("load-teleport");
const versionEl = document.getElementById("version");
const toastEl   = document.getElementById("toast");
const primeEl   = document.getElementById("prime") || document.getElementById("odd prime");
const statusEl  = document.getElementById("status");

let pyodide = null;
let bootDone = false;

function append(el, txt) {
  if (!el || txt == null) return;
  el.textContent += String(txt) + "\n";
  el.scrollTop = el.scrollHeight;
}
function clear(el) { if (el) el.textContent = ""; }
function toast(msg, ms = 3500) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.style.display = "block";
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(() => { toastEl.style.display = "none"; }, ms);
}

// Mirror JS errors and console into #log
(function installGlobalErrorHandlers(){
  window.addEventListener("error", (ev) => {
    append(logEl, `[JS Error] ${ev.message}\n${ev.filename}:${ev.lineno}:${ev.colno}`);
    if (ev.error && ev.error.stack) append(logEl, ev.error.stack);
  });
  window.addEventListener("unhandledrejection", (ev) => {
    append(logEl, `[Promise Rejection] ${ev.reason}`);
    try { append(logEl, ev.reason && ev.reason.stack); } catch {}
  });
  const orig = { log: console.log, warn: console.warn, error: console.error };
  console.log  = (...a) => { orig.log(...a);  append(logEl, a.join(" ")); };
  console.warn = (...a) => { orig.warn(...a); append(logEl, "[warn] " + a.join(" ")); };
  console.error= (...a) => { orig.error(...a);append(logEl, "[error] " + a.join(" ")); };
})();

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
  catch (e) {
    append(logEl, "[Python Error] " + String(e));
    throw new Error(String(e));
  }
}

async function boot() {
  try {
    if (location.protocol === "file:") {
      throw new Error("Serve via HTTP (e.g., GitHub Pages).");
    }
    if (versionEl) versionEl.textContent = new URL(location.href).href;

    statusEl && (statusEl.textContent = "loading Python…");
    pyodide = await loadPyodide();

    // Route Python stdout/stderr
    pyodide.setStdout({ batched: (s) => append(outEl, s) });
    pyodide.setStderr({ batched: (s) => append(logEl, s) });

    statusEl && (statusEl.textContent = "mounting zipapp…");
    const zipBytes = await loadBinary("./spl-run.pyz");
    pyodide.FS.writeFile("/spl-run.pyz", zipBytes, { canOwn: true });
    await safePy(`
import sys
if "/spl-run.pyz" not in sys.path:
    sys.path.insert(0, "/spl-run.pyz")
`);

    statusEl && (statusEl.textContent = "verifying deps…");
    await safePy(`
import importlib
try:
    importlib.import_module("lark")
except Exception:
    import micropip
    await micropip.install("lark>=1.1,<2")
`);

    statusEl && (statusEl.textContent = "binding runner…");
    // Exact import and call shape provided by user:
    //   from spl.src.parser import parser; parser.parse(src) -> Program
    //   from spl.src.interpreter.interpret_spl import interpret
    //   interpret(p: int, prog: Program, context: Optional[Dict[str,str]] = None)
    await safePy(`
from spl.src.parser import parser as _parser
from spl.src.interpreter.interpret_spl import interpret as _interpret
import io, sys, contextlib, traceback

def _run_wrapper(src: str, p: int) -> str:
    if not isinstance(src, str): raise TypeError("src must be str")
    if not isinstance(p, int):  raise TypeError("p must be int")
    prog = _parser.parse(src)
    out = io.StringIO(); err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            # exact signature: interpret(p, prog, context=None)
            ret = _interpret(p, prog)
        except Exception:
            traceback.print_exc()
            raise
    # flush captured stderr so JS sees it
    sys.stderr.write(err.getvalue())
    # normalize return to string + printed stdout
    if isinstance(ret, tuple) and len(ret)==2:
        ro, re = ret
        txt = (ro if isinstance(ro,str) else str(ro)) + out.getvalue()
    elif isinstance(ret, str):
        txt = ret + out.getvalue()
    elif ret is None:
        txt = out.getvalue()
    else:
        txt = str(ret) + out.getvalue()
    return txt
`);

    // Load example if present
    try {
      srcEl.value = await loadText("./teleportation.spl");
      toast("Loaded teleportation example.", 1800);
    } catch {
      if (srcEl) srcEl.placeholder = "Missing ./teleportation.spl";
    }

    bootDone = true;
    statusEl && (statusEl.textContent = "ready");
    if (runBtn)  runBtn.disabled = false;
    if (loadBtn) loadBtn.disabled = false;
  } catch (e) {
    statusEl && (statusEl.textContent = "boot error");
    append(logEl, "[Boot Error] " + (e && e.message ? e.message : String(e)));
    outEl && (outEl.textContent = "Boot failed:\n" + (e && e.message ? e.message : String(e)));
    toast("Boot failed. See Errors.", 5000);
  }
}

runBtn && (runBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 1500); return; }
  clear(outEl);
  let p = parseInt((primeEl && primeEl.value) || "3", 10);
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safePy(`_run_wrapper(${codeJSON}, int(${p}))`);
    outEl.textContent = String(result);
    toast("Program ran.", 1500);
  } catch (e) {
    append(logEl, "[Run Error] " + (e && e.message ? e.message : String(e)));
    outEl.textContent = "Error running program:\n" + (e && e.message ? e.message : String(e));
    toast("Run failed. See Errors.", 4000);
  }
});

loadBtn && (loadBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 1500); return; }
  try {
    srcEl.value = await loadText("./teleportation.spl");
    toast("Teleportation loaded.", 1500);
  } catch (e) {
    append(logEl, "[Load Error] " + (e && e.message ? e.message : String(e)));
    toast("Could not load teleportation.", 3000);
  }
});

boot();
