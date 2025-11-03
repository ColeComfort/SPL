// placeholder
// app.js — SPL Online with robust error reporting
// Works with Pyodide 0.26.x. Adds UI error logs and Python traceback capture.

const $ = (sel) => document.querySelector(sel);
const outEl = $("#out");
const logEl = $("#log");
const statusEl = $("#status");
const versionEl = $("#version");
const btnRun = $("#run");
const btnLoadTeleport = $("#load-teleport");
const srcEl = $("#src");
const primeEl = document.getElementById("odd prime") || $("#prime");

function append(el, txt) {
  if (!txt) return;
  el.textContent += String(txt) + "\n";
  el.scrollTop = el.scrollHeight;
}

function clear(el) { el.textContent = ""; }

function toast(msg, ms = 3500) {
  const t = $("#toast");
  t.textContent = msg;
  t.style.display = "block";
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
    statusEl.textContent = "loading runtime…";
    pyodide = await loadPyodide();
    versionEl.textContent = `Pyodide ${pyodide.version}`;
    pyodide.setStdout({ batched: (s) => append(outEl, s) });
    pyodide.setStderr({ batched: (s) => append(logEl, s) });
    const havePyz = await urlExists("./spl-run.pyz");
    if (havePyz) {
      statusEl.textContent = "loading SPL zip…";
      const buf = await (await fetch("./spl-run.pyz")).arrayBuffer();
      pyodide.FS.writeFile("/spl-run.pyz", new Uint8Array(buf));
      await pyodide.runPythonAsync(`
import sys
if "/spl-run.pyz" not in sys.path:
    sys.path.insert(0, "/spl-run.pyz")
try:
    from spl_web import run_spl_web  # preferred
except Exception:
    run_spl_web = None
`);
      const hasRun = await pyodide.runPythonAsync("run_spl_web is not None");
      if (!hasRun) {
        append(logEl, "[setup] spl-run.pyz present but spl_web.run_spl_web not found. Falling back to manifest.");
        await mountFromManifest();
      }
    } else {
      await mountFromManifest();
    }

    const ok = await pyodide.runPythonAsync(`
try:
    from spl_web import run_spl_web as _runner
    assert callable(_runner)
    True
except Exception as e:
    print("Runner import failed:", e)
    False
`);
    if (!ok) throw new Error("run_spl_web entry point not available");

    await pyodide.runPythonAsync(`
def _run_wrapper(src: str, p: int):
    from spl_web import run_spl_web as _runner
    return _runner(src, p)
`);

    btnRun.disabled = false;
    btnLoadTeleport.disabled = false;
    statusEl.textContent = "ready";
    pyBooted = true;
  } catch (err) {
    pyBooted = false;
    statusEl.textContent = "failed";
    reportError(err, "Boot");
  }
}

async function urlExists(url) {
  try {
    const r = await fetch(url, { method: "HEAD" });
    return r.ok;
  } catch {
    return false;
  }
}

async function mountFromManifest() {
  statusEl.textContent = "mounting sources…";
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
  await pyodide.runPythonAsync(`
import sys
for p in ("/", "/spl", "/spl/src"):
    (p in sys.path) or sys.path.append(p)
try:
    from spl_web import run_spl_web
except Exception:
    def run_spl_web(src: str, p: int):
        from spl.src.parser import parser as spl_parser
        from spl.src.interpreter import interpret_spl as interp
        ast = spl_parser.parse(src)
        text_out, text_err = interp.run_program(ast, p=p)
        return text_out
`);
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
  statusEl.textContent = "running…";
  try {
    const p = parseInt(primeEl?.value || "3", 10) || 3;
    const src = srcEl.value;
    const pySrc = JSON.stringify(src);
    const result = await pyodide.runPythonAsync(`_run_wrapper(${pySrc}, int(${p}))`);
    append(outEl, result);
    statusEl.textContent = "done";
  } catch (err) {
    reportError(err, "Run");
    statusEl.textContent = "error";
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
