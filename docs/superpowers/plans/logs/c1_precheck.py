# -*- coding: utf-8 -*-
"""C1 预检：列出未用导入中符号全仓出现 >1 处的条目（需人工核对动态引用）"""
import re
import subprocess

items = []
with open(r"C:\Users\李文彬\AppData\Local\Temp\c1_list.txt", encoding="utf-8") as f:
    for line in f:
        m = re.match(r"(.+?):(\d+):\d+: '(.+?)' imported but unused", line)
        if m:
            items.append((m.group(1).replace("\\", "/"), int(m.group(2)), m.group(3)))

print(f"共 {len(items)} 条")
multi = []
for path, ln, sym in items:
    base = sym.split(".")[-1].split(" as ")[-1]
    r = subprocess.run(["rg", "-c", base, "app"], capture_output=True, text=True)
    count = sum(int(x.split(":")[1]) for x in r.stdout.strip().splitlines() if x) if r.stdout.strip() else 0
    if count > 1:
        multi.append((path, ln, sym, count))

print(f"符号出现 >1 处的（需人工核对）: {len(multi)} 条")
for p, l, s, c in multi:
    print(f"  {p}:{l} {s} (rg {c} 处)")
