# Optional: desktop usage for the zipapp (not used by the browser)
import sys
from runner import run_spl
def _read(p): 
    return sys.stdin.read() if p == "-" else open(p, "r", encoding="utf-8").read()
if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run_spl(_read(sys.argv[1])))
    else:
        print("SPL zipapp. In the browser, Pyodide imports '/spl-run.pyz' and uses runner.run_spl(src).")
