# -*- coding: utf-8 -*-
"""C1 最终版：清理 pyflakes 未用导入（支持括号多行块）。

判定口径：
- pyflakes 报告 = 文件内无绑定使用（跨文件使用必经 import 语句，pyflakes 已计入）
- 残余风险仅两个：①本文件字符串字面量含符号名（get_type_hints P2 场景）→ 跳过
  ②importlib/`__import__` 动态导入（已全仓扫描，与清单无交叉）
"""
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[4] / "backend"


def find_import_block(lines, start):
    """从 start 行向上找 from/import 块的开头，返回 (block_start, block_end)"""
    i = start
    while i >= 0:
        if re.search(r"from\s+[\w.]+\s+import\s*\(|^\s*import\s*\(", lines[i]):
            bs = i
            break
        if re.match(r"^\S", lines[i]) and "import" not in lines[i] and i != start:
            return start, start
        i -= 1
    else:
        return start, start
    be = bs
    while be < len(lines) and ")" not in lines[be]:
        be += 1
    return bs, min(be, len(lines) - 1)


def remove_symbol_in_line(line, base):
    """从单行移除符号，返回 (新行 or None=删行, 是否变化)"""
    m = re.match(r"^(\s*)from\s+([\w.]+)\s+import\s+(.+?)(\s*(#.*)?)\s*$", line)
    if m:
        indent, module, names, tail = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        parts = [p.strip() for p in names.split(",") if p.strip()]
        kept = [p for p in parts if p.split(" as ")[-1].strip() != base]
        if not kept:
            return None, True
        return f"{indent}from {module} import {', '.join(kept)}{tail}\n", True
    m = re.match(r"^(\s*)import\s+(.+?)(\s*(#.*)?)\s*$", line)
    if m:
        indent, names, tail = m.group(1), m.group(2), m.group(3) or ""
        parts = [p.strip() for p in names.split(",") if p.strip()]
        kept = [p for p in parts if p.split(" as ")[-1].strip() != base]
        if not kept:
            return None, True
        return f"{indent}import {', '.join(kept)}{tail}\n", True
    return line, False


def process(path_rel, sym, report_line):
    f = BACKEND / path_rel
    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
    base = sym.split(".")[-1].split(" as ")[-1]

    src = "".join(lines)
    if re.search(rf"[\"']{re.escape(base)}[\"']", src):
        return f"skipped:本文件字符串引用 {base}"

    # 定位符号所在行：优先报告行号附近，其次全文件搜
    cand = None
    for i in range(len(lines)):
        if re.search(rf"(?<![\w.]){re.escape(base)}\b", lines[i]) and (
            "import" in lines[i] or lines[i].strip().endswith(",") or lines[i].strip() == base
        ):
            cand = i
            if abs(i - (report_line - 1)) <= 6:
                break
    if cand is None:
        return "skipped:符号定位失败"

    line = lines[cand]
    # 括号块成员行（仅符号+逗号）
    if re.match(rf"^\s*{re.escape(base)}( as \w+)?,?\s*$", line.rstrip("\n")) and (
        "(" in "".join(lines[max(0, cand - 8):cand]) or "import" in "".join(lines[max(0, cand - 8):cand])
    ):
        del lines[cand]
        f.write_text("".join(lines), encoding="utf-8", newline="")
        return f"deleted block-line {cand+1}"

    new_line, changed = remove_symbol_in_line(line, base)
    if not changed:
        return f"skipped:行无法解析: {line.strip()[:50]}"
    if new_line is None:
        del lines[cand]
    else:
        lines[cand] = new_line
    f.write_text("".join(lines), encoding="utf-8", newline="")
    return f"deleted {cand+1}" if new_line is None else f"removed {cand+1}"


def collect():
    out = subprocess.run(
        [sys.executable, "-m", "pyflakes", "app"],
        cwd=BACKEND, capture_output=True, text=True,
    ).stdout
    entries = []
    for line in out.splitlines():
        if "imported but unused" not in line:
            continue
        p = line.split(":")[0].replace("\\", "/")
        if "tests" in p or p.endswith("database.py") or p.endswith("models.py"):
            continue
        ln = int(line.split(":")[1])
        sym = re.search(r"'(.+?)'", line).group(1)
        entries.append((p, ln, sym))
    return entries


def main():
    # 白名单文件（database.py / models.py 的保留原因）
    wl = BACKEND.parent / "docs" / "superpowers" / "plans" / "logs" / "pyflakes_whitelist.txt"
    if not wl.exists():
        wl.write_text(
            "# pyflakes 白名单：保留的未用导入（每条：文件 符号 —— 原因）\n"
            "# app/db/database.py 22 条模型导入 —— SQLAlchemy 模型注册副作用导入，"
            "删除会破坏 create_all 的表注册（被 database.py:66 的 import 显式触发）\n"
            "# app/db/models.py 2 条 Mapped/mapped_column —— 文件用 Column() 旧式风格，"
            "导入确实未用，但属公共底层文件，保守保留防未来注解式迁移时缺失\n",
            encoding="utf-8", newline="\n",
        )
        print("白名单已创建:", wl)

    deleted = removed = skipped = 0
    # 最多跑三轮（删行后行号变化，pyflakes 重收集）
    for round_no in range(3):
        entries = collect()
        if not entries:
            break
        progressed = False
        for p, ln, sym in entries:
            r = process(p, sym, ln)
            print(f"[{round_no+1}] {p}:{ln} {sym} -> {r}")
            if r.startswith("deleted") or r.startswith("removed"):
                progressed = True
                deleted += r.count("deleted")
                removed += r.count("removed")
            else:
                skipped += 1
        if not progressed:
            break
    print(f"== 汇总: deleted~{deleted} removed~{removed} skipped {skipped}")


if __name__ == "__main__":
    main()
