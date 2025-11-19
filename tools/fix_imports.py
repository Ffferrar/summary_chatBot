import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

TOP_PACKAGES = set()
for p in SRC.iterdir():
    if p.is_dir():
        TOP_PACKAGES.add(p.name)

FROM_RE = re.compile(r'^(\s*)from\s+([A-Za-z_][\w\.]*)\s+import\b')
IMPORT_RE = re.compile(r'^(\s*)import\s+([A-Za-z_][\w\.]*)(\s+as\s+\w+)?\s*$')

def same_package_targets(curr_dir: Path):
    names = set()
    for item in curr_dir.iterdir():
        if item.is_file() and item.suffix == ".py":
            names.add(item.stem)
        elif item.is_dir() and (item / "__init__.py").exists():
            names.add(item.name)
    return names

def process_file(fp: Path):
    rel = fp.relative_to(SRC)
    curr_dir = fp.parent
    local_names = same_package_targets(curr_dir)
    lines = fp.read_text(encoding="utf-8").splitlines(True)
    changed = False

    def within_src(path: str) -> bool:
        head = path.split(".", 1)[0]
        return head in TOP_PACKAGES

    new = []
    for line in lines:
        m = FROM_RE.match(line)
        if m:
            indent, module = m.groups()
            # case 1: same-package module (no dot) -> relative
            base = module.split(".")[0]
            if "." not in module and base in local_names:
                line = line.replace(f"from {module} ", f"from .{module} ")
                changed = True
            # case 2: top-level package without src. -> add src.
            elif not module.startswith("src.") and within_src(module):
                line = line.replace(f"from {module} ", f"from src.{module} ")
                changed = True
            new.append(line)
            continue

        m = IMPORT_RE.match(line)
        if m:
            indent, module, alias = m.groups()
            base = module.split(".")[0]
            # case 1: same-package plain import -> make relative package import
            if "." not in module and base in local_names:
                # import foo -> from . import foo
                rest = alias or ""
                line = f"{indent}from . import {module}{rest}\n"
                changed = True
            # case 2: top-level package without src. -> add src.
            elif not module.startswith("src.") and within_src(module):
                rest = alias or ""
                line = f"{indent}import src.{module}{rest}\n"
                changed = True
            new.append(line)
            continue

        new.append(line)

    if changed:
        fp.write_text("".join(new), encoding="utf-8")
        return True
    return False

def main():
    touched = 0
    for py in SRC.rglob("*.py"):
        # Skip generated/migrations if you prefer; keep them if they use src.*
        if any(part in {"__pycache__", ".venv", "venv"} for part in py.parts):
            continue
        touched += 1 if process_file(py) else 0
    print(f"Updated {touched} files")

if __name__ == "__main__":
    main()