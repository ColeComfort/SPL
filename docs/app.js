// Minimal SPL web frontend using embedded runner inside spl-run.pyz

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

    await safePy(`
    import importlib
    try:
        importlib.import_module("lark")
    except Exception:
        import micropip
        await micropip.install("lark>=1.1,<2")
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
    if (outEl) outEl.textContent = "Boot failed:\\n" + e.message;
    toast("Boot failed. See Output.", 6000);
  }
}

runBtn.onclick = async () => {
  if (!pyodide) return;
  outEl.textContent = "";
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safePy(`
from runner import run_spl
run_spl(${codeJSON})
`);
    outEl.textContent = String(result);
    toast("Program ran.", 2000);
  } catch (e) {
    outEl.textContent = "Error running program:\\n" + e.message;
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

