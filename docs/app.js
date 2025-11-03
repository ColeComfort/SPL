// app.js — robust loader with cache-bust, overlay, namespace merge, and sys.modules purge
// Assumes: dist zip has no spl/__init__.py or spl/src/__init__.py

const outEl     = document.getElementById("out");
const logEl     = document.getElementById("log");
const srcEl     = document.getElementById("src");
const runBtn    = document.getElementById("run");
const loadBtn   = document.getElementById("load-teleport");
const versionEl = document.getElementById("version");
const toastEl   = document.getElementById("toast");
const primeEl   = document.getElementById("prime") || document.getElementById("odd prime");
const statusEl  = document.getElementById("status");

function append(el, txt){ if(el && txt!=null){ el.textContent += String(txt)+"\n"; el.scrollTop = el.scrollHeight; } }
function clear(el){ if(el) el.textContent=""; }
function toast(msg, ms=3000){ if(!toastEl) return; toastEl.textContent=msg; toastEl.style.display="block"; clearTimeout(toastEl._t); toastEl._t=setTimeout(()=>toastEl.style.display="none",ms); }
(function(){ const o={log:console.log,warn:console.warn,error:console.error};
  console.log=(...a)=>{o.log(...a);append(logEl,a.join(" "));};
  console.warn=(...a)=>{o.warn(...a);append(logEl,"[warn] "+a.join(" "));};
  console.error=(...a)=>{o.error(...a);append(logEl,"[error] "+a.join(" "));};
  window.addEventListener("error",e=>append(logEl,`[JS Error] ${e.message}\n${e.filename}:${e.lineno}:${e.colno}`));
  window.addEventListener("unhandledrejection",e=>append(logEl,`[Promise Rejection] ${e.reason}`));
})();

let pyodide=null, bootDone=false;
async function safePy(code){ try{ return await pyodide.runPythonAsync(code); }catch(e){ append(logEl,"[Python Error] "+String(e)); throw e; } }
async function loadBinary(u){ const r=await fetch(u,{cache:"no-store"}); if(!r.ok) throw new Error(`HTTP ${r.status} for ${u}`); return new Uint8Array(await r.arrayBuffer()); }
async function loadText(u){ const r=await fetch(u,{cache:"no-store"}); if(!r.ok) throw new Error(`HTTP ${r.status} for ${u}`); return r.text(); }

async function overlayFromManifest(){
  const r = await fetch("./manifest.json",{cache:"no-store"}); if(!r.ok) return false;
  const m = await r.json(); if(!m.files || !Array.isArray(m.files)) return false;
  for(const f of m.files){
    const t = await (await fetch(f.url,{cache:"no-store"})).text();
    const parts = f.vm.split("/").filter(Boolean); let cur="";
    for(let i=0;i<parts.length-1;i++){ cur+="/"+parts[i]; try{ pyodide.FS.mkdir(cur);}catch{} }
    pyodide.FS.writeFile(f.vm, t);
  }
  await safePy(`import sys\nfor p in ("/","/spl","/spl/src"): sys.path.insert(0,p) if p not in sys.path else None`);
  append(logEl,"[overlay] manifest applied");
  return true;
}

async function boot(){
  try{
    pyodide = await loadPyodide();
    pyodide.setStdout({batched:s=>append(outEl,s)});
    pyodide.setStderr({batched:s=>append(logEl,s)});
    versionEl && (versionEl.textContent = `Pyodide ${pyodide.version}`);

    statusEl && (statusEl.textContent="mounting zip…");
    const zip = await loadBinary("./spl-run.pyz?v="+Date.now());
    pyodide.FS.writeFile("/spl-run.pyz", zip, {canOwn:true});
    await safePy(`import sys\nsys.path.insert(0,"/spl-run.pyz")`);

    statusEl && (statusEl.textContent="binding…");
    let bound=false;
    try{
      await bindRunner(false);
      bound=true;
    }catch(e){
      append(logEl,"[bind] failed, applying overlay and purging… "+(e.message||e));
      await overlayFromManifest();
      await bindRunner(true);
      bound=true;
    }

    try{ srcEl.value = await loadText("./teleportation.spl"); }catch{}
    bootDone = bound;
    statusEl && (statusEl.textContent = bound ? "ready" : "error");
    if(runBtn) runBtn.disabled=!bound;
    if(loadBtn) loadBtn.disabled=!bound;
  }catch(e){
    statusEl && (statusEl.textContent="boot error");
    append(logEl,"[Boot Error] "+(e && e.message? e.message:String(e)));
    outEl && (outEl.textContent = "Boot failed:\n"+(e && e.message? e.message:String(e)));
  }
}

async function bindRunner(purge){
  const code = `
import sys, importlib.util, io, contextlib, traceback

def _purge_spl():
    for k in list(sys.modules.keys()):
        if k == "spl" or k.startswith("spl."):
            del sys.modules[k]

if ${purge ? "True" : "False"}:
    for p in ("/spl/src","/spl","/"):
        try:
            idx = sys.path.index(p); sys.path.pop(idx)
        except ValueError:
            pass
        sys.path.insert(0, p)
    _purge_spl()

from spl.src.parser import parser as _parser
from spl.src.interpreter.interpret_spl import interpret as _interpret

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
`;
  await safePy(code);
}

runBtn && (runBtn.onclick = async ()=>{
  if(!bootDone){ toast("Still booting…",1500); return; }
  clear(outEl);
  const p = parseInt((primeEl && primeEl.value) || "3", 10);
  try{
    const pySrc = JSON.stringify(srcEl.value);
    const result = await safePy(`_run_wrapper(${pySrc}, int(${p}))`);
    outEl.textContent = String(result);
    toast("Program ran.", 1400);
  }catch(e){
    append(logEl,"[Run Error] "+String(e));
    outEl.textContent = "Error running program:\n"+String(e);
  }
});

loadBtn && (loadBtn.onclick = async ()=>{
  try{ srcEl.value = await loadText("./teleportation.spl?v="+Date.now()); toast("Teleportation loaded.",1400); }
  catch(e){ append(logEl,"[Load Error] "+String(e)); }
});

boot();

