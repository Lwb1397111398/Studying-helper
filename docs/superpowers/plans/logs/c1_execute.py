# -*- coding: utf-8 -*-
"""C1 未用导入清理执行脚本（带三重防御）。

用法: python c1_execute.py <清单文件> <批1模块前缀...> -- <批2模块前缀...>
每条删除前判定：
  1. 目标行只含该符号 → 删整行；多符号行 → 只移除该符号
  2. 该文件内符号名是否出现在字符串字面量中（P2 教训：get_type_hints 场景）→ 命中跳过
  3. 全仓其他文件是否有引号包裹的符号名引用（跨文件动态引用）→ 命中跳过
"""
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"


def find_string_ref(base: str, search_root: Path, exclude_file: Path) -> str | None:
    """全仓查引号包裹的符号名（含相对 import 字符串场景），返回命中文件"""
    pat = re.compile(rf"[\"']({re.escape(base)})[\"']")
    for py in search_root.rglob("*.py"):
        if py.resolve() == exclude_file.resolve():
            continue
        try:
            if pat.search(py.read_text(encoding="utf-8")):
                return str(py.relative_to(BACKEND))
        except Exception:
            continue
    return None


def process_entry(rel_path: str, line_no: int, sym: str) -> str:
    """返回 'deleted' | 'removed_sym' | 'skipped:原因'"""
    f = BACKEND / rel_path
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    idx = line_no - 1
    if idx >= len(lines):
        return f"skipped:行号越界 {line_no}"
    line = lines[idx]
    base = sym.split(".")[-1].split(" as ")[-1]

    # 防御 2：文件内字符串字面量引用
    src = f.read_text(encoding="utf-8")
    if re.search(rf"[\"']{re.escape(base)}[\"']", src):
        return f"skipped:文件内字符串引用 {base}"

    # 防御 3：跨文件引号引用
    hit = find_string_ref(base, BACKEND / "app", f)
    if hit:
        return f"skipped:跨文件字符串引用 {hit}"

    # 解析并移除符号
    m = re.match(r"^(\s*)from\s+([\w.]+)\s+import\s+(.+?)(\s*(#.*)?)$", line)
    m2 = re.match(r"^(\s*)import\s+(.+?)(\s*(#.*)?)$", line)
    if m:
        g = m.groups()
        indent, module, names, tail = g[0], g[1], g[2], g[3]
        parts = [p.strip() for p in names.split(",")]
        kept = [p for p in parts if p.split(" as ")[-1] != base]
        if not kept:
            del lines[idx]
        else:
            lines[idx] = f"{indent}from {module} import {', '.join(kept)}{tail.rstrip()}\n"
        f.write_text("".join(lines), encoding="utf-8", newline="")
        return "deleted" if not kept else "removed_sym"
    if m2:
        g = m2.groups()
        indent, names, tail = g[0], g[1], g[2]
        parts = [p.strip() for p in names.split(",")]
        kept = [p for p in parts if p.split(" as ")[-1] != base]
        if not kept:
            del lines[idx]
        else:
            lines[idx] = f"{indent}import {', '.join(kept)}{tail.rstrip()}\n"
        f.write_text("".join(lines), encoding="utf-8", newline="")
        return "deleted" if not kept else "removed_sym"
    return f"skipped:无法解析行 {line.strip()[:60]}"


def main():
    list_file = Path(sys.argv[1])
    argv = sys.argv[2:]
    split = argv.index("--") if "--" in argv else len(argv)
    batch1 = argv[:split]
    batch2 = argv[split + 1:] if split < len(argv) else []
    which = sys.argv[-1] if sys.argv[-1] in ("1", "2") else None

    entries = []
    for line in list_file.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(.+?):(\d+):\d+: '(.+?)' imported but unused", line.replace("\\", "/"))
        if m:
            entries.append((m.group(1), int(m.group(2)), m.group(3)))

    prefixes = batch1 if which == "1" else batch2
    label = "C1-a" if which == "1" else "C1-b"
    deleted = removed = skipped = 0
    for rel_path, ln, sym in entries:
        if not any(rel_path.startswith(p) for p in prefixes):
            continue
        result = process_entry(rel_path, ln, sym)
        print(f"[{label}] {rel_path}:{ln} {sym} -> {result}")
        if result.startswith("deleted"):
            deleted += 1
        elif result.startswith("removed_sym"):
            removed += 1
        else:
            skipped += 1
    print(f"== {label} 汇总: 删行 {deleted} / 移除符号 {removed} / 跳过 {skipped}")


if __name__ == "__main__":
    main()
