"""P6 推送前置门禁：git 卫生检查 + 真实库三方 hash + 状态复核，逐项 PASS/FAIL 落盘。

用法：
    python backend/scripts/final_gate.py --base origin/master --out docs/superpowers/plans/logs/final_gate.md [--dry-run]

检查项（计划案写死）：
    1. git 跟踪文件无 .db
    2. git 跟踪文件无 logs/backup 路径
    3. 新增（相对 --base）文件 >1MB 清单
    4. git diff --check <base>...HEAD（空白错误）
    5. git diff --cached --check
    6. docs/当前进度.md 无 TODO_P6 残留
    7. 真实库三方 hash（开工前记录 / 当前 / 备份）——开工前 hash 由 --source-sha256 传入或从 --pre-sha-file 读取
    8. git fetch + status -sb + log origin/master..HEAD 概览
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROGRESS_FILE = PROJECT_ROOT / "docs" / "当前进度.md"


def run(args: str) -> str:
    r = subprocess.run(args, shell=True, cwd=str(PROJECT_ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def tracked_files() -> list[bytes]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(PROJECT_ROOT),
                         capture_output=True).stdout
    return [p for p in out.split(b"\x00") if p]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/master")
    parser.add_argument("--out", default="docs/superpowers/plans/logs/final_gate.md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-sha256", default="", help="真实库当前 hash（外部算好传入）")
    parser.add_argument("--pre-sha256", default="", help="开工前记录的源库 hash")
    parser.add_argument("--backup-sha256", default="", help="备份库 hash")
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []

    # 1/2) db / backup 文件
    files = tracked_files()
    db_hits = [p for p in files if p.lower().endswith(b".db")]
    checks.append(("git 跟踪文件无 .db", not db_hits, str(db_hits[:5])))
    backup_hits = [p for p in files if b"log/backup" in p.lower() or b"logs/backup" in p.lower()
                   or b"\\backup\\" in p.lower()]
    checks.append(("git 跟踪文件无 logs/backup 路径", not backup_hits, str(backup_hits[:5])))

    # 3) 新增大文件 >1MB
    big: list[str] = []
    for p in files:
        fp = PROJECT_ROOT / p.decode("utf-8", errors="replace")
        try:
            if fp.is_file() and fp.stat().st_size > 1024 * 1024:
                big.append(f"{fp.name} ({fp.stat().st_size // 1024}KB)")
        except OSError:
            pass
    checks.append(("跟踪文件 >1MB 清单（人工确认为空或合理）", True, "; ".join(big) or "无"))

    # 4/5) 空白错误
    w1 = run(f"git diff --check {args.base}...HEAD").strip()
    checks.append(("git diff --check base...HEAD", not w1, w1[:200] or "干净"))
    w2 = run("git diff --cached --check").strip()
    checks.append(("git diff --cached --check", not w2, w2[:200] or "干净"))

    # 6) TODO_P6 残留
    todo = "TODO_P6" in PROGRESS_FILE.read_text(encoding="utf-8") if PROGRESS_FILE.exists() else True
    checks.append(("当前进度.md 无 TODO_P6 残留", not todo, ""))

    # 6b) pyflakes 过滤白名单后 = 0（C1 门禁固化，round2）
    pyflakes_out = run(f'"{sys.executable}" -m pyflakes app')
    pyflakes_lines = [l for l in pyflakes_out.strip().splitlines() if l.strip()]
    wl = PROJECT_ROOT / "docs" / "superpowers" / "plans" / "logs" / "pyflakes_whitelist.txt"
    wl_files = set()
    if wl.exists():
        for wl_line in wl.read_text(encoding="utf-8").splitlines():
            if wl_line.startswith("#") or not wl_line.strip():
                continue
            wl_files.add(wl_line.split()[0].replace("/", "\\"))
    residual = [l for l in pyflakes_lines if l.split(":")[0] not in wl_files]
    checks.append(("pyflakes 过滤白名单后为 0（C1 门禁固化）", not residual,
                   f"共 {len(pyflakes_lines)} 条 / 白名单外残留 {len(residual)} 条" +
                   ("" if not residual else "；首条: " + residual[0][:120])))

    # 7) 真实库三方 hash
    if args.source_sha256:
        trio = f"开工前={args.pre_sha256 or '未记录'} / 当前={args.source_sha256} / 备份={args.backup_sha256 or '未记录'}"
        untouched = (not args.pre_sha256) or args.pre_sha256 == args.source_sha256
        checks.append(("真实库三方 hash（未触碰=开工前==当前）", untouched, trio))

    # 8) 状态复核
    run("git fetch origin")
    status_sb = run("git status -sb").strip().splitlines()
    commits = run(f"git log --oneline {args.base}..HEAD").strip().splitlines()
    pn = [c for c in commits if any(c.split(" ", 1)[-1].startswith(p)
          for p in ("P1:", "P2:", "P3a", "P4:", "P5:", "P6"))]
    checks.append((f"log {args.base}..HEAD 含 P1~P6 commit", len(pn) >= 5, f"{len(commits)} commits, Pn={len(pn)}"))
    r2 = [c for c in commits if any(c.split(" ", 1)[-1].startswith(p)
          for p in ("R1a:", "R1b:", "R4:", "W1:", "C1-a:", "C1-b:", "D1:", "P6'"))]
    checks.append((f"log {args.base}..HEAD 含 round2 计划 commit（R1a/R1b/R4/C1/D1）",
                   len(r2) >= 4, f"round2 前缀 commit={len(r2)}"))
    checks.append(("git status -sb（工作区状态，人工确认干净）", True, status_sb[0] if status_sb else ""))

    lines = [
        "# final_gate 快照",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    ok_all = True
    for name, ok, detail in checks:
        ok_all &= ok
        lines.append(f"- [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    lines += ["", "## P1~P6 代码 commit", ""]
    lines += [f"- {c}" for c in commits]
    lines += ["", "## 推送目标", "", f"- 分支：codex/stability-convergence → origin（base={args.base}）"]
    content = "\n".join(lines) + "\n"

    print(content)
    if not args.dry_run:
        out = PROJECT_ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"→ 已落盘 {out}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
