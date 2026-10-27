"""P4 后端冒烟脚本（固化）：launcher 真实启动 → 同步链 → 学习资产 → 教学 v2 → 导出回灌。

用法（仓库根目录或任意目录均可）：
    python backend/scripts/smoke_backend.py              # 自动 preflight + 正式冒烟
    python backend/scripts/smoke_backend.py --check-env  # 仅 preflight（落盘门禁文件）
    python backend/scripts/smoke_backend.py --keep       # 失败时保留临时现场

产出：
    docs/superpowers/plans/logs/preflight_result.txt   PREFLIGHT_PASS / PREFLIGHT_FAIL（P6 门禁输入）
    docs/superpowers/plans/logs/preflight_paths.txt    openapi 实际路径集合
    logs/smoke_run*.txt                                正式运行日志（连续两次均须绿）

事实依据（写死，2026-10-28 核实）：
    - v2 教学开课：POST /api/v1/teaching/sessions/start，payload {book_id, unit_ids:[...], engine:"v2"}
      （router.py:134-170，v2 分支要求 unit 已有 active+teachable 资产）
    - 资产：POST /api/v1/learning-assets/units/{unit_id}/analyze（同步执行，无请求体）
      GET /api/v1/learning-assets/units/{unit_id}/asset（AssetResponse）
    - 同步：POST /api/v1/sync/preview|import（multipart 字段 file，Content-Type: application/json）
      GET /api/v1/sync/export（JSON 响应）；import 为 delete+add 重放语义（重放不膨胀）
    - unit_id 选取：export 包 knowledge_units 筛 book_id=="round4-book"，断言非空后按 id 排序取第一个
      （样例包含 round4-unit-a/b 共 2 个，非唯一，故用确定性排序选取而非唯一断言）
    - 健康检查：GET /api/health（main.py:111）
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_ROOT / "backend" / "launcher.py"
BACKEND_DIR = PROJECT_ROOT / "backend"
SAMPLE_PACKAGE = PROJECT_ROOT / "docs" / "samples" / "round4_sync_package.json"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
LOGS_DIR = PROJECT_ROOT / "docs" / "superpowers" / "plans" / "logs"

BOOK_ID = "round4-book"
DEADLINE_SECONDS = 480  # 脚本级 8 分钟
HTTP_TIMEOUT = 15

_openapi_paths: set[str] = set()
_last_request = {"method": "", "url": "", "status": 0, "body": ""}
START_TIME = time.monotonic()
RESULTS: list[tuple[str, bool, str]] = []


def _deadline_left() -> float:
    left = DEADLINE_SECONDS - (time.monotonic() - START_TIME)
    if left <= 0:
        raise RuntimeError("脚本级 deadline（8 分钟）已用尽")
    return left


def check(step: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((step, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {step}" + (f" — {detail}" if detail else ""))
    return ok


def http_req(method: str, path: str, *, json_body: dict | None = None,
             multipart_path: Path | None = None, expect_json: bool = True,
             timeout: int = HTTP_TIMEOUT):
    """urllib 封装：统一超时/诊断记录。返回 (status, body_dict_or_text)。"""
    _deadline_left()
    url = BASE + path
    data = None
    headers = {}
    if multipart_path is not None:
        boundary = uuid.uuid4().hex
        payload = multipart_path.read_bytes()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{multipart_path.name}"\r\n'
            f"Content-Type: application/json\r\n\r\n"
        ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
        data = body
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8", errors="replace")
    except Exception as e:  # 超时/连接拒绝等
        _last_request.update(method=method, url=url, status=0, body=f"{type(e).__name__}: {e}")
        raise
    _last_request.update(method=method, url=url, status=status, body=raw[:300])
    if expect_json and raw.strip():
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, raw
    return status, raw


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_backend(data_dir: Path):
    """launcher 真实启动（全新临时库），返回 (proc, port, log_path)。"""
    port = pick_free_port()
    log_path = data_dir / "backend_stdout.log"
    env = dict(os.environ)
    env.update(APP_NO_BROWSER="1", APP_PORT=str(port), APP_DATA_DIR=str(data_dir))
    proc = subprocess.Popen(
        [sys.executable, str(LAUNCHER)],
        cwd=str(BACKEND_DIR), env=env,
        stdout=open(log_path, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
    )
    return proc, port, log_path


def wait_health(port: int, proc, log_path: Path, timeout_s: int = 60) -> bool:
    global BASE
    BASE = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"  后端进程提前退出（code={proc.returncode}），最近输出：")
            _print_log_tail(log_path)
            return False
        try:
            status, body = http_req("GET", "/api/health", expect_json=True, timeout=3)
            if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                return True
        except Exception:
            pass
        time.sleep(1)
    print("  健康检查超时，后端最近输出：")
    _print_log_tail(log_path)
    return False


def _print_log_tail(log_path: Path, lines: int = 50):
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        print("\n".join(f"    | {l}" for l in tail))
    except OSError as e:
        print(f"    (无法读取日志: {e})")


def stop_backend(proc, port: int):
    """清理链：terminate → 等待 10s → kill → Windows taskkill → 端口释放断言。"""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return True
        time.sleep(0.5)
    return False


def fetch_openapi_paths() -> set[str]:
    _, spec = http_req("GET", "/openapi.json")
    return set(spec.get("paths", {}).keys()) if isinstance(spec, dict) else set()


REQUIRED_PATHS = [
    "/api/v1/sync/import",
    "/api/v1/sync/export",
    "/api/v1/teaching/sessions/start",
    "/api/v1/aid/{book_id}/design",
    "/api/v1/learning-assets/units/{unit_id}/analyze",
    "/api/v1/learning-assets/units/{unit_id}/asset",
]


def run_core_chain(step_prefix: str) -> dict:
    """核心链：导入→重放→资产→教学v2→导出→回灌→保值。返回上下文 dict，失败抛 AssertionError。"""
    # 1) openapi 路径断言
    _openapi_paths.update(fetch_openapi_paths())
    missing = [p for p in REQUIRED_PATHS if p not in _openapi_paths]
    check(f"{step_prefix}: openapi 含全部关键路径", not missing, f"缺失: {missing}" if missing else f"{len(_openapi_paths)} 条路径")

    # 2) books 列表
    status, books = http_req("GET", "/api/v1/books")
    check(f"{step_prefix}: GET /api/v1/books 200", status == 200, f"status={status}")

    # 3) preview → import → 重放（delete+add 语义：计数不膨胀）
    status, preview = http_req("POST", "/api/v1/sync/preview", multipart_path=SAMPLE_PACKAGE)
    check(f"{step_prefix}: sync/preview 200", status == 200, f"status={status}")
    status, imp1 = http_req("POST", "/api/v1/sync/import", multipart_path=SAMPLE_PACKAGE)
    check(f"{step_prefix}: sync/import 200", status == 200, f"status={status}")
    assert isinstance(imp1, dict)
    status, imp2 = http_req("POST", "/api/v1/sync/import", multipart_path=SAMPLE_PACKAGE)
    check(f"{step_prefix}: 同库重放 import 不膨胀（delete+add 语义）",
          status == 200 and imp2.get("units_imported") == imp1.get("units_imported")
          and imp2.get("books_imported") == imp1.get("books_imported"),
          f"units {imp1.get('units_imported')} -> {imp2.get('units_imported')}")
    status, books_body = http_req("GET", "/api/v1/books")
    check(f"{step_prefix}: import 后 books 含 {BOOK_ID}",
          status == 200 and any(b.get("id") == BOOK_ID for b in books_body.get("items", [])),
          f"books={len(books_body.get('items', []))}")

    # 4) unit_id 选取（非空 + 确定性排序取首）
    status, exported = http_req("GET", "/api/v1/sync/export")
    check(f"{step_prefix}: sync/export 200", status == 200, f"status={status}")
    assert isinstance(exported, dict)
    units = sorted(u["id"] for u in exported.get("knowledge_units", [])
                   if u.get("book_id") == BOOK_ID)
    check(f"{step_prefix}: round4-book units 非空", bool(units), f"选取 {units[0] if units else '无'}")
    unit_id = units[0]
    check(f"{step_prefix}: 导出计数 ≥ 导入",
          len(exported.get("books", [])) >= imp1.get("books_imported", 0)
          and len(exported.get("knowledge_units", [])) >= imp1.get("units_imported", 0),
          f"books {len(exported.get('books', []))}≥{imp1.get('books_imported')} units "
          f"{len(exported.get('knowledge_units', []))}≥{imp1.get('units_imported')}")

    # 5) analyze（同步，无请求体）→ GET asset 防假绿断言
    status, ana = http_req("POST", f"/api/v1/learning-assets/units/{unit_id}/analyze")
    check(f"{step_prefix}: analyze 2xx（同步产出资产）", 200 <= status < 300, f"status={status} body={str(ana)[:120]}")
    assert isinstance(ana, dict)
    check(f"{step_prefix}: AnalyzeResponse 关键字段", all(k in ana for k in
          ("asset_id", "unit_id", "status", "readiness_status")), str({k: ana.get(k) for k in ("status", "readiness_status")}))

    status, asset = http_req("GET", f"/api/v1/learning-assets/units/{unit_id}/asset")
    check(f"{step_prefix}: GET asset 200", status == 200, f"status={status}")
    assert isinstance(asset, dict)
    payload = asset.get("payload") or {}
    check(f"{step_prefix}: asset status=active 且 readiness 可教",
          asset.get("status") == "active" and asset.get("readiness_status") in ("teachable", "degraded_teachable"),
          f"status={asset.get('status')} readiness={asset.get('readiness_status')}")
    check(f"{step_prefix}: 资产内容非空（claims/assessment_items 防假绿）",
          bool(payload.get("claims")) and bool(payload.get("assessment_items")),
          f"claims={len(payload.get('claims') or [])} items={len(payload.get('assessment_items') or [])}")

    # 6) 教学 v2 开课（只接受 2xx）
    status, sess = http_req("POST", "/api/v1/teaching/sessions/start",
                            json_body={"book_id": BOOK_ID, "unit_ids": [unit_id], "engine": "v2"})
    check(f"{step_prefix}: teaching v2 start 2xx", 200 <= status < 300, f"status={status} body={str(sess)[:150]}")
    assert isinstance(sess, dict)
    check(f"{step_prefix}: session 结构（id 非空 + state_v2）",
          bool(sess.get("id")) and bool(sess.get("state_v2")),
          f"id={str(sess.get('id'))[:18]}… state={sess.get('state_v2')}")
    session_id = sess.get("id", "")

    # 7) 导出回灌：session 保值 + 计数不膨胀
    # R1a 后 sync 契约 SyncTeachingSession 含 v1 字段 + v2 三字段
    # （state_v2/asset_id/completion_status，默认 None）→ 保值断言升级为五字段；
    # v2 会话的 state_v2/asset_id 在 start 后非空，回灌必须保值。
    status, exported2 = http_req("GET", "/api/v1/sync/export")
    sessions = [s for s in (exported2.get("teaching_sessions") or []) if s.get("id") == session_id]
    check(f"{step_prefix}: 导出包含该 v2 会话（契约含 teaching_sessions）",
          status == 200 and bool(sessions),
          f"sessions={len(exported2.get('teaching_sessions') or [])}")
    saved_state = {k: sessions[0].get(k) for k in ("current_phase", "status", "state_v2", "asset_id", "completion_status")} if sessions else {}

    # 回灌导出包（落临时文件 → multipart）
    reimport_file = Path(tempfile.mkdtemp(prefix="smoke_reimport_")) / "reimport.json"
    reimport_file.write_text(json.dumps(exported2, ensure_ascii=False), encoding="utf-8")
    try:
        status, reimp = http_req("POST", "/api/v1/sync/import", multipart_path=reimport_file)
        check(f"{step_prefix}: 导出包回灌 import 200", status == 200, f"status={status}")
        check(f"{step_prefix}: 回灌后计数不膨胀",
              reimp.get("units_imported") == imp1.get("units_imported")
              and reimp.get("books_imported") == imp1.get("books_imported"),
              f"units {reimp.get('units_imported')} vs {imp1.get('units_imported')}")
        status, exported3 = http_req("GET", "/api/v1/sync/export")
        s2 = [s for s in (exported3.get("teaching_sessions") or []) if s.get("id") == session_id]
        got_state = {k: s2[0].get(k) for k in ("current_phase", "status", "state_v2", "asset_id", "completion_status")} if s2 else {}
        check(f"{step_prefix}: 回灌后 session 仍可查且契约字段保值",
              bool(s2) and got_state == saved_state and bool(saved_state),
              f"{got_state} vs {saved_state}")
    finally:
        reimport_file.unlink(missing_ok=True)
        reimport_file.parent.rmdir()

    return {"unit_id": unit_id, "session_id": session_id}


def preflight() -> bool:
    """preflight：独立临时库跑最小链路 + e2e 基建预检。落盘门禁文件。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    ok_all = True

    data_dir = Path(tempfile.mkdtemp(prefix="smoke_preflight_"))
    proc, port, log_path = start_backend(data_dir)
    try:
        if not wait_health(port, proc, log_path):
            lines.append("backend: FAIL（启动/健康检查失败）")
            ok_all = False
        else:
            paths = fetch_openapi_paths()
            (LOGS_DIR / "preflight_paths.txt").write_text(
                "\n".join(sorted(paths)), encoding="utf-8")
            missing = [p for p in REQUIRED_PATHS if p not in paths]
            lines.append(f"openapi: {'PASS' if not missing else 'FAIL 缺失 ' + str(missing)}"
                         f"（{len(paths)} 条路径 → preflight_paths.txt）")
            ok_all &= not missing
            try:
                run_core_chain("preflight")
                lines.append("core-chain(analyze→asset→v2 start→export→回灌): PASS")
            except Exception as e:
                lines.append(f"core-chain: FAIL — {type(e).__name__}: {e} "
                             f"(last={_last_request['method']} {_last_request['url']} "
                             f"{_last_request['status']} {_last_request['body'][:120]})")
                ok_all = False
    finally:
        if not stop_backend(proc, port):
            lines.append("端口释放: FAIL")
            ok_all = False
        if not KEEP:
            _rm_tree(data_dir)

    # e2e/playwright 预检（写死判定）
    pw_lines, pw_ok = preflight_playwright()
    lines.extend(pw_lines)
    ok_all &= pw_ok

    verdict = "PREFLIGHT_PASS" if ok_all else "PREFLIGHT_FAIL"
    lines.insert(0, verdict + f"  ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    (LOGS_DIR / "preflight_result.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(f"  {l}" for l in lines))
    print(f"  → 门禁文件已落盘 {LOGS_DIR / 'preflight_result.txt'}")
    return ok_all


def preflight_playwright() -> tuple[list[str], bool]:
    lines, ok = [], True
    pkg = FRONTEND_DIR / "package.json"
    cfg = FRONTEND_DIR / "playwright.config.ts"
    scripts = {}
    if pkg.exists():
        scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    e2e_ok = "test:e2e" in scripts and cfg.exists()
    lines.append(f"e2e 基建: {'PASS' if e2e_ok else 'FAIL'}"
                 f"（test:e2e script={'test:e2e' in scripts}, playwright.config.ts={cfg.exists()}）")
    ok &= e2e_ok
    try:
        r = subprocess.run(["cmd", "/c", "npx", "playwright", "--version"],
                           cwd=str(FRONTEND_DIR), capture_output=True, text=True, timeout=120)
        lines.append(f"playwright 版本: {r.stdout.strip() or r.stderr.strip()}")
        # 幂等安装：浏览器与 playwright 版本不匹配时自动补装（完整输出落盘备查）
        inst = subprocess.run(["cmd", "/c", "npx", "playwright", "install", "chromium"],
                              cwd=str(FRONTEND_DIR), capture_output=True, text=True, timeout=600)
        (LOGS_DIR / "preflight_playwright_install.txt").write_text(
            (inst.stdout or "") + (inst.stderr or ""), encoding="utf-8")
        probe = subprocess.run(
            ["node", "-e",
             "const {chromium}=require('playwright-core');"
             "(async()=>{const b=await chromium.launch();const p=await b.newPage();"
             "await p.goto('about:blank');await b.close();console.log('CHROMIUM_OK');})()"
             ".catch(e=>{console.error(e.message);process.exit(1)})"],
            cwd=str(FRONTEND_DIR), capture_output=True, text=True, timeout=120)
        chromium_ok = "CHROMIUM_OK" in probe.stdout
        lines.append(f"chromium 启动冒烟: {'PASS' if chromium_ok else 'FAIL — ' + probe.stderr.strip()[:150]}"
                     f"（install 输出 → preflight_playwright_install.txt）")
        ok &= chromium_ok
    except Exception as e:
        lines.append(f"playwright 预检异常: {type(e).__name__}: {e}")
        ok = False
    return lines, ok


def _rm_tree(p: Path):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


KEEP = False


def main() -> int:
    global KEEP
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check-env", action="store_true", help="仅跑 preflight 并落盘门禁文件")
    parser.add_argument("--keep", action="store_true", help="失败时保留临时目录与日志")
    args = parser.parse_args()
    KEEP = args.keep

    if not SAMPLE_PACKAGE.exists():
        print(f"FAIL 样例包不存在: {SAMPLE_PACKAGE}")
        return 2

    if args.check_env:
        return 0 if preflight() else 1

    # 正式运行：preflight 门禁必须 PASS（无则自动先跑）
    gate = LOGS_DIR / "preflight_result.txt"
    if not gate.exists() or "PREFLIGHT_PASS" not in gate.read_text(encoding="utf-8"):
        print("[preflight] 门禁文件缺失或非 PASS，自动执行 preflight …")
        if not preflight():
            print("PREFLIGHT_FAIL：不进入正式冒烟")
            return 1

    data_dir = Path(tempfile.mkdtemp(prefix="smoke_run_"))
    proc, port, log_path = start_backend(data_dir)
    try:
        if not wait_health(port, proc, log_path):
            return 1
        run_core_chain("smoke")
        failed = [r for r in RESULTS if not r[1]]
        if failed:
            print(f"\nSMOKE_FAIL：{len(failed)} 项失败（共 {len(RESULTS)} 项）")
            return 1
        print(f"\nSMOKE_PASS：{len(RESULTS)} 项全过")
        return 0
    finally:
        if not stop_backend(proc, port):
            print("FAIL 端口未释放")
        if KEEP:
            print(f"[--keep] 现场保留: {data_dir} (pid={proc.pid})")
        else:
            _rm_tree(data_dir)


if __name__ == "__main__":
    sys.exit(main())
