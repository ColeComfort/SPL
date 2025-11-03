// Robust SPL web frontend: waits for boot, imports fixed parser/interpreter, requires explicit p

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
    // Deterministic wiring: no guessing. Import exact entry points and call with (p, ast, context=ast.context or {}).
    await safePy(`
from spl.src.parser.parser import parse_spl
from spl.src.interpreter.interpret_spl_affine import interpret as interpret_aff

def _summarize(env, rel):
    head = f"p={rel.p}  n_in={rel.n_in}  n_out={rel.n_out}"
    try:
        body = rel.to_kernel_str()
    except Exception:
        body = str(rel)
    return head + "\\n" + body

def run_spl_web(src: str, p: int) -> str:
    ast = parse_spl(src)
    ctx = getattr(ast, "context", None) or {}
    env, rel = interpret_aff(p, ast, context=ctx)
    return _summarize(env, rel)
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

