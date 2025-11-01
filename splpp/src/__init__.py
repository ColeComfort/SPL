
# Public API

def __getattr__(name):
    if name in {"Program","FnDecl","Stmt","VarDecl","InitStmt","QInitStmt","MeasStmt","PrepStmt","Apply","QCtrlApply","CCtrlApply","IfStmt","AssertRel","PrintSPL","Return","parse_splpp"}:
        from .parser import ast as _ast
        return getattr(_ast, name)
    if name in {"Compiler","compile_program_fn","compile_text_fn"}:
        from .compiler import compiler as _comp
        return getattr(_comp, name)
    if name in {"run_assertions_via_spl","functions_by_name"}:
        from .interpreter import interp as _interp
        return getattr(_interp, name)
    raise AttributeError(name)

__all__ = [
  "Compiler",
  "Program","FnDecl","Stmt","VarDecl","InitStmt","QInitStmt","MeasStmt","PrepStmt","Apply","QCtrlApply","CCtrlApply","IfStmt","AssertRel","PrintSPL","Return","parse_splpp",
  "compile_program_fn","compile_text_fn",
  "run_assertions_via_spl","functions_by_name",
]
