// app-plain.js — no spl_web. Calls SPL interpreter directly.
// Pyodide 0.26.x

const $ = (sel) => document.querySelector(sel);
const outEl = $("#out");
const logEl = $("#log");
const statusEl = $("#status");
const versionEl = $("#version");
const btnRun = $("#run");
const btnLoadTeleport = $("#load-teleport");
const srcEl = $("#src");
const primeEl = document.getElementById("prime") || document.getElementById("odd prime");

function append(el, txt) {
  if (!txt) return;
  el.textContent += String(txt) + "\n";
  el.scrollTop = el.scrollHeight;
}
function clear(el) { el.textContent = ""; }
function toast(msg, ms = 3500) {
  const t = $("#toast"); if (!t) return;
  t.textContent = msg; t.style.display = "block";
  setTimeout(() => (t.style.display = "none"), ms);
}
function installGlobalErrorHandlers() {
  window.addEventListener("error", (ev) => {
    append(logEl, `[JS Error] ${ev.message}\n${ev.filename}:${ev.lineno}:${ev.colno}`);
    if (ev.error && ev.error.stack) append(logEl, ev.error.stack);
  });
  window.addEventListener("unhandledrejection", (ev) => {
    append(logEl, `[Promise Rejection] ${ev.reason}`);
    try { append(logEl, ev.reason && ev.reason.stack); } catch {}
  });
  const orig = { log: console.log, warn: console.warn, error: console.error };
  console.log = (...args) => { orig.log(...args); append(logEl, args.join(" ")); };
  console.warn = (...args) => { orig.warn(...args); append(logEl, "[warn] " + args.join(" ")); };
  console.error = (...args) => { orig.error(...args); append(logEl, "[error] " + args.join(" ")); };
}
installGlobalErrorHandlers();

let pyodide = null;
let pyBooted = false;

async function boot() {
  try {
    statusEl && (statusEl.textContent = "loading runtime…");
    pyodide = await loadPyodide();
    versionEl && (versionEl.textContent = `Pyodide ${pyodide.version}`);
    pyodide.setStdout({ batched: (s) => append(outEl, s) });
    pyodide.setStderr({ batched: (s) => append(logEl, s) });

    // Mount from manifest.json only
    await mountFromManifest();

    // Define a universal _run_wrapper that imports parser+interpreter and runs it.
    await pyodide.runPythonAsync(`
import sys, io, contextlib, traceback
def _import_parser():
    try:
        from spl.src.parser import parser as spl_parser
        return spl_parser
    except Exception:
        from spl.parser import parser as spl_parser
        return spl_parser
def _import_interp():
    try:
        import spl.src.interpreter.interpret_spl as interp
    except Exception:
        import spl.interpreter.interpret_spl as interp
    return interp
def _find_runner(imod):
    for fname in ("run_program","run","interpret"):
        if hasattr(imod, fname):
            return getattr(imod, fname)
    raise RuntimeError("No interpreter entry point found in interpret_spl")
def _run_wrapper(src: str, p: int):
    if not isinstance(src, str):
        raise TypeError("src must be str")
    if not isinstance(p, int) or p <= 1:
        raise ValueError("p must be an odd prime integer")
    spl_parser = _import_parser()
    interp = _import_interp()
    runner = _find_runner(interp)
    ast = spl_parser.parse(src)
    out = io.StringIO(); err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            try:
                ret = runner(ast, p=p)
            except TypeError:
                ret = runner(ast, p)
        except Exception:
            traceback.print_exc()
            raise
    txt = out.getvalue()
    if isinstance(ret, tuple) and len(ret)==2:
        ro, re = ret
        txt = (ro if isinstance(ro,str) else str(ro)) + txt
        err.write(re if isinstance(re,str) else str(re))
    elif isinstance(ret, str):
        txt = ret + txt
    elif ret is not None:
        txt = str(ret) + txt
    sys.stderr.write(err.getvalue())
    return txt
`);
    btnRun && (btnRun.disabled = false);
    btnLoadTeleport && (btnLoadTeleport.disabled = false);
    statusEl && (statusEl.textContent = "ready");
    pyBooted = true;
  } catch (err) {
    pyBooted = false;
    statusEl && (statusEl.textContent = "failed");
    reportError(err, "Boot");
  }
}

async function mountFromManifest() {
  const res = await fetch("./manifest.json");
  if (!res.ok) throw new Error(`manifest.json not found (${res.status})`);
  const manifest = await res.json();
  if (!manifest.files || !Array.isArray(manifest.files)) throw new Error("manifest missing files[]");
  for (const f of manifest.files) {
    const url = f.url;
    const vm = f.vm;
    const txt = await (await fetch(url)).text();
    ensureDirs(vm);
    pyodide.FS.writeFile(vm, txt);
  }
  await pyodide.runPythonAsync(`import sys\nfor p in ("/", "/spl", "/spl/src"): (p in sys.path) or sys.path.append(p)`);
}

function ensureDirs(path) {
  const parts = path.split("/").filter(Boolean);
  let cur = "";
  for (let i = 0; i < parts.length - 1; i++) {
    cur += "/" + parts[i];
    try { pyodide.FS.mkdir(cur); } catch {}
  }
}

function reportError(err, phase = "Run") {
  const header = `[${phase} Error]`;
  if (err && err.message) append(logEl, `${header} ${err.message}`);
  if (err && err.stack) append(logEl, err.stack);
  try { append(logEl, String(err)); } catch {}
  toast(`${phase} error. See Errors panel.`);
}

btnRun?.addEventListener("click", async () => {
  if (!pyBooted) return;
  clear(outEl);
  btnRun.disabled = true;
  statusEl && (statusEl.textContent = "running…");
  try {
    const p = parseInt((primeEl && primeEl.value) || "3", 10) || 3;
    const src = srcEl.value;
    const pySrc = JSON.stringify(src);
    const result = await pyodide.runPythonAsync(`_run_wrapper(${pySrc}, int(${p}))`);
    append(outEl, result);
    statusEl && (statusEl.textContent = "done");
  } catch (err) {
    reportError(err, "Run");
    statusEl && (statusEl.textContent = "error");
  } finally {
    btnRun.disabled = false;
  }
});

btnLoadTeleport?.addEventListener("click", async () => {
  try {
    const res = await fetch("./teleportation.spl");
    if (!res.ok) throw new Error(`teleportation.spl ${res.status}`);
    srcEl.value = await res.text();
    toast("Loaded teleportation.spl");
  } catch (err) {
    reportError(err, "Load example");
  }
});

boot();
