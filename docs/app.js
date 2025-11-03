// app.js
// Robust Pyodide bootstrap + visible error reporting using existing DOM ids.

const $ = (id) => document.getElementById(id);
const state = { pyodide: null, ready: false, pyReadyPromise: null };

function append(pre, text) {
  pre.textContent += text;
  pre.scrollTop = pre.scrollHeight;
}
function clearPane(pre) {
  pre.textContent = "";
}
function setStatus(s) { $("status").textContent = s; }

async function loadPyodideAndSPL() {
  if (state.pyReadyPromise) return state.pyReadyPromise;
  state.pyReadyPromise = (async () => {
    setStatus("loading Pyodide…");
    const pyodide = await loadPyodide();
    state.pyodide = pyodide;

    // Wire stdout/stderr to panes
    pyodide.setStdout({ batched: (s) => append($("out"), s) });
    pyodide.setStderr({ batched: (s) => append($("log"), s) });

    // Small banner to confirm JS side is working
    append($("log"), "[JS] Pyodide loaded\n");

    // Load project files described by manifest.json into the VM FS
    setStatus("fetching manifest…");
    const manifest = await fetch("./manifest.json").then((r) => {
      if (!r.ok) throw new Error(`manifest.json HTTP ${r.status}`);
      return r.json();
    });

    setStatus("mounting files…");
    const FS = pyodide.FS;
    for (const { url, vm } of manifest.files || []) {
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`${url} HTTP ${resp.status}`);
        const buf = await resp.arrayBuffer();
        const path = vm.startsWith("/") ? vm : `/${vm}`;
        const dir = path.split("/").slice(0, -1).join("/") || "/";
        // ensure dir exists
        const parts = dir.split("/").filter(Boolean);
        let cur = "";
        for (const p of parts) {
          cur += "/" + p;
          try { FS.lookupPath(cur); } catch { FS.mkdir(cur); }
        }
        // write file
        FS.writeFile(path, new Uint8Array(buf));
      } catch (e) {
        append($("log"), `[JS] Failed to mount ${url} -> ${vm}: ${e.message}\n`);
      }
    }

    // Preload teleportation example if shipped alongside
    try {
      const tele = await fetch("./teleportation.spl");
      if (tele.ok) {
        const txt = await tele.text();
        $("load-teleport").addEventListener("click", () => {
          $("src").value = txt;
        });
        $("load-teleport").disabled = false;
      }
    } catch {
      // optional; ignore
    }

    // Define a stable Python entrypoint once. It only returns strings.
    setStatus("initializing entrypoint…");
    const py = `
import sys, traceback

# Lazy import to avoid import-time failures making Run a no-op.
def _run_once(src: str, p_value: int) -> str:
    try:
        # Prefer your canonical parser/interpreter modules.
        # These paths come from manifest.json that mounted /spl/src/...
        from spl.src.parser import parser as _parser
        from spl.src.interpreter import interpret_spl as _interp

        # Parse. Try signatures defensively and report exact errors.
        prog = None
        parse_errs = []
        for call in (
            lambda: _parser.parse_spl(src),                      # no p
            lambda: _parser.parse_spl(src, p=p_value),           # named p
            lambda: _parser.parse_spl(src, prime=p_value),       # named prime
        ):
            try:
                prog = call()
                break
            except TypeError as te:
                parse_errs.append(str(te))
        if prog is None:
            raise TypeError("parse_spl signature mismatch attempts: " + " | ".join(parse_errs))

        # Interpret. Try common signatures, surface full traceback on failure.
        rel = None
        interp_errs = []
        for call in (
            lambda: _interp.interpret(prog),                     # simple
            lambda: _interp.interpret(prog, p=p_value),          # named p
            lambda: _interp.interpret(prog, prime=p_value),      # named prime
        ):
            try:
                rel = call()
                break
            except TypeError as te:
                interp_errs.append(str(te))
        if rel is None:
            raise TypeError("interpret signature mismatch attempts: " + " | ".join(interp_errs))

        # Convert to text. Prefer pretty printer if present.
        if hasattr(rel, "to_kernel_str"):
            return rel.to_kernel_str()
        return str(rel)

    except Exception as e:
        return "[PYTHON ERROR]\\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__))
`;
    await pyodide.runPythonAsync(py);

    // Show versions
    const pyver = pyodide.runPython(`import sys; sys.version.split()[0]`);
    const pydver = pyodide.version;
    $("version").textContent = `Python ${pyver} • Pyodide ${pydver}`;
    setStatus("ready");
    $("run").disabled = false;
    state.ready = true;
    return true;
  })();
  return state.pyReadyPromise;
}

async function runOnce() {
  if (!state.ready) await loadPyodideAndSPL();
  clearPane($("out"));
  clearPane($("log"));
  setStatus("running…");
  $("run").disabled = true;
  try {
    const src = $("src").value;
    const p = parseInt($("odd prime").value, 10);
    if (!Number.isInteger(p) || p < 3) {
      append($("log"), "[JS] Invalid prime p (must be integer ≥ 3)\n");
    }

    // Feed code to Python and capture returned string. Never rely on implicit prints.
    const code = `
_src = ${JSON.stringify(src)}
_p = int(${Number.isFinite(p) ? p : 3})
_out_text = _run_once(_src, _p)
`;
    await state.pyodide.runPythonAsync(code);
    const out = state.pyodide.globals.get("_out_text");
    if (typeof out === "string" && out.startsWith("[PYTHON ERROR]")) {
      append($("log"), out + "\n");
    } else {
      append($("out"), String(out) + "\n");
    }
  } catch (err) {
    // Show JS-side or Pyodide-wrapped errors verbosely.
    const isPy = err && err.name === "PythonError";
    append($("log"), (isPy ? err.message : (err.stack || String(err))) + "\n");
  } finally {
    $("run").disabled = false;
    setStatus("idle");
  }
}

window.addEventListener("error", (e) => append($("log"), `[JS] ${e.message}\n`));
window.addEventListener("unhandledrejection", (e) => {
  const r = e.reason;
  append($("log"), `[JS] Unhandled rejection: ${r && r.stack ? r.stack : String(r)}\n`);
});

window.addEventListener("DOMContentLoaded", () => {
  void loadPyodideAndSPL();
  $("run").addEventListener("click", () => { void runOnce(); });
});

