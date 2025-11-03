// app.js — loads spl-run.pyz then overlays /spl/src/... from manifest.json if present.
// Directly binds to spl.src.interpreter.interpret_spl.interpret(p, prog). Sends errors to #log.

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

async function maybeOverlayFromManifest() {
  try {
    const res = await fetch("./manifest.json", { cache: "no-store" });
    if (!res.ok) return false;
    const manifest = await res.json();
    if (!manifest.files || !Array.isArray(manifest.files)) return false;
    for (const f of manifest.files) {
      const url = f.url;
      const vm  = f.vm;
      const txt = await (await fetch(url, { cache: "no-store" })).text();
      // ensure dirs
      const parts = vm.split("/").filter(Boolean);
      let cur = "";
      for (let i = 0; i < parts.length - 1; i++) {
        cur += "/" + parts[i];
        try { pyodide.FS.mkdir(cur); } catch {}
      }
      pyodide.FS.writeFile(vm, txt);
    }
    // put root paths
    await safePy(`import sys\nfor p in ("/", "/spl", "/spl/src"): (p in sys.path) or sys.path.append(p)`);
    append(logEl, "[overlay] manifest.json applied over zipapp");
    return true;
  } catch (e) {
    append(logEl, "[overlay] manifest overlay failed: " + (e && e.message ? e.message : String(e)));
    return false;
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
    pyodide.setStdout({ batched: (s) => append(outEl, s) });
    pyodide.setStderr({ batched: (s) => append(logEl, s) });

    statusEl && (statusEl.textContent = "mounting zipapp…");
    const zipBytes = await loadBinary("./spl-run.pyz");
    pyodide.FS.writeFile("/spl-run.pyz", zipBytes, { canOwn: true });
    await safePy(`import sys\nsys.path.insert(0, "/spl-run.pyz")`);

    statusEl && (statusEl.textContent = "verifying deps…");
    await safePy(`
import importlib
try:
    importlib.import_module("lark")
except Exception:
    import micropip
    await micropip.install("lark>=1.1,<2")
`);

    // Try to import now; if missing modules, apply overlay then retry.
    statusEl && (statusEl.textContent = "binding runner…");
    let bound = false;
    try {
      await bindRunner();
      bound = true;
    } catch (e) {
      append(logEl, "[bind] initial import failed, trying manifest overlay… " + (e && e.message ? e.message : String(e)));
      const ok = await maybeOverlayFromManifest();
      if (ok) {
        await bindRunner();
        bound = true;
      } else {
        throw e;
      }
    }

    // Load example
    try {
      srcEl.value = await loadText("./teleportation.spl");
      toast("Loaded teleportation example.", 1600);
    } catch {}

    bootDone = bound;
    statusEl && (statusEl.textContent = bound ? "ready" : "error");
    if (runBtn)  runBtn.disabled = !bound;
    if (loadBtn) loadBtn.disabled = !bound;
  } catch (e) {
    statusEl && (statusEl.textContent = "boot error");
    append(logEl, "[Boot Error] " + (e && e.message ? e.message : String(e)));
    outEl && (outEl.textContent = "Boot failed:\n" + (e && e.message ? e.message : String(e)));
    toast("Boot failed. See Errors.", 4000);
  }
}

async function bindRunner() {
  await safePy(`
from spl.src.parser import parser as _parser
from spl.src.interpreter.interpret_spl import interpret as _interpret
import io, sys, contextlib, traceback
def _run_wrapper(src: str, p: int) -> str:
    prog = _parser.parse(src)
    out = io.StringIO(); err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            ret = _interpret(p, prog)
        except Exception:
            traceback.print_exc()
            raise
    sys.stderr.write(err.getvalue())
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
}

runBtn && (runBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 1400); return; }
  clear(outEl);
  let p = parseInt((primeEl && primeEl.value) || "3", 10);
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safePy(`_run_wrapper(${codeJSON}, int(${p}))`);
    outEl.textContent = String(result);
    toast("Program ran.", 1400);
  } catch (e) {
    append(logEl, "[Run Error] " + (e && e.message ? e.message : String(e)));
    outEl.textContent = "Error running program:\n" + (e && e.message ? e.message : String(e));
    toast("Run failed. See Errors.", 3000);
  }
});

loadBtn && (loadBtn.onclick = async () => {
  if (!bootDone) { toast("Still booting…", 1400); return; }
  try {
    srcEl.value = await loadText("./teleportation.spl");
    toast("Teleportation loaded.", 1400);
  } catch (e) {
    append(logEl, "[Load Error] " + (e && e.message ? e.message : String(e)));
    toast("Could not load teleportation.", 2800);
  }
});

boot();
