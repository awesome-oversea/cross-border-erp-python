import py_compile
import pathlib
import sys

errors = []
src = pathlib.Path("src/erp")
for f in src.rglob("*.py"):
    try:
        py_compile.compile(str(f), doraise=True)
    except py_compile.PyCompileError as e:
        errors.append((str(f), str(e)))

if errors:
    print(f"FAILED: {len(errors)} files with syntax errors")
    for path, err in errors:
        print(f"  {path}: {err}")
    sys.exit(1)
else:
    total = len(list(src.rglob("*.py")))
    print(f"OK: All {total} Python files passed syntax check")
