const statusEl  = document.getElementById("status");
const outEl     = document.getElementById("out");
const srcEl     = document.getElementById("src");
const versionEl = document.getElementById("version");
const runBtn    = document.getElementById("run");
const loadBtn   = document.getElementById("load-teleport");
const toastEl   = document.getElementById("toast");

// Example file in repo root relative to /web/
const EXAMPLE_PATH = "../spl/programs/teleportation.spl";

let pyodide;

function toast(msg, cls="warn", ms=4000){
  toastEl.className = cls;
  toastEl.textContent = msg;
  toastEl.style.display = "block";
  clearTimeout(toastEl._t);
  toastEl._t = setTimeout(()=>{ toastEl.style.display="none"; }, ms);
}

async function loadText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return await res.text();
}

async function safeRunPython(code){
  try {
    return await pyodide.runPythonAsync(code);
  } catch (e) {
    throw new Error(String(e));
  }
}

async function boot() {
  try {
    statusEl.textContent = "loading Python…";
    pyodide = await loadPyodide();

    versionEl.textContent = "SPL web • " + (new URL(location.href)).href;

    statusEl.textContent = "loading SPL modules…";
    const manifest = JSON.parse(await loadText("./manifest.json"));

    for (const f of manifest.files) {
      const code = await loadText(f.url);
      const dir = f.vm.split("/").slice(0, -1).join("/");
      if (dir) {
        try { pyodide.FS.mkdirTree(dir); } catch (_) {}
      }
      pyodide.FS.writeFile(f.vm, code);
    }

    // Ensure "/" is importable
    await safeRunPython(`
import sys
if "/" not in sys.path:
    sys.path.insert(0, "/")
`);

    // Runner glue
    await safeRunPython(await loadText("./runner.py"));

    // Default example
    try {
      srcEl.value = await loadText(EXAMPLE_PATH);
      toast("Loaded teleportation example.", "ok", 2500);
    } catch (e) {
      srcEl.placeholder = "Teleportation example missing: " + EXAMPLE_PATH;
      toast("Could not load teleportation example. " + e.message, "warn");
    }

    statusEl.textContent = "ready";
  } catch (e) {
    statusEl.textContent = "boot error";
    outEl.textContent = "Boot failed:\n" + e.message;
    toast("Boot failed. See Output for details.", "error", 6000);
  }
}

runBtn.onclick = async () => {
  if (!pyodide) return;
  statusEl.textContent = "running…";
  outEl.textContent = "";
  try {
    const codeJSON = JSON.stringify(srcEl.value);
    const result = await safeRunPython(`
from runner import run_spl
run_spl(${codeJSON})
`);
    outEl.textContent = String(result);
    statusEl.textContent = "done";
    toast("Program ran successfully.", "ok", 2000);
  } catch (e) {
    outEl.textContent = "Error running program:\n" + e.message;
    statusEl.textContent = "error";
    toast("Run failed. See Output for details.", "error", 6000);
  }
};

loadBtn.onclick = async () => {
  try {
    srcEl.value = await loadText(EXAMPLE_PATH);
    toast("Teleportation loaded.", "ok", 2000);
  } catch (e) {
    toast("Could not load teleportation. " + e.message, "error");
  }
};

boot();

