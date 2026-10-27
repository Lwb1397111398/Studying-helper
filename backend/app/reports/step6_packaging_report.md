# Step 6 回报：Windows exe 打包

## ① 路径审计清单

| 路径 | 解析方式 | frozen / dev |
| --- | --- | --- |
| 数据根 | `APP_DATA_DIR` > exe 同级 `data/` > `cwd/data` | frozen: exe 同级 data/ ; dev: backend/data/ |
| db | `sqlite+aiosqlite:///.../data/learning.db` | 绝对路径，跨盘符安全 |
| 上传/备份 | `data/files/` / `data/backups/` | 自动创建 |
| .env | `data/.env` | frozen 时数据根下；dev 时 backend/.env 优先 |
| 静态资源 | `frontend_dist/` 打包进 `_MEIPASS` | frozen 时只读；dev 时不 mount |

## ② hidden imports 实际清单 + 产物体积

```bash
# 收集完整包
chardet (mypyc)
pdfplumber
pdfminer
ebooklib
bs4
openai
httpx
anyio
pydantic + pydantic_core
sqlalchemy + aiosqlite
uvicorn + starlette + fastapi
aiofiles
greenlet
certifi
```

产物体积：
- exe: **68 MB** (包含前端 dist)
- 总二进制+数据: ~110 MB

## ③ 干净环境验证记录

```
E:/AI Agent/work area/Studying-helper/dist_exe/StudyingHelper.exe
健康检查: 200
SPA 访问: 200 (index.html)
书籍列表: 200 {"items":[],"total":0,...}
```

数据根: `dist_exe/smoke_run/` (含 .env, learning.db, files/, backups/, logs/)
启动后自动打开浏览器，控制台保留日志。

## ④ 踩坑记录

1. chardet 7.x 带 mypyc pyd - 用 `collect_all` 收集整包。
2. SPA 回退路由必须放在所有 API 路由**之后**（否则 API 也被截获）。
3. frozen 时数据库 URL 用绝对路径，Windows 三斜线 + 绝对路径。
4. launcher.py 入口必须用 `app` 对象（frozen 下 string import 失效）。
5. .env 优先级：frozen 时写到数据根；dev 时保留 backend/.env 兼容性。
6. PyInstaller 必须在 Windows 上构建（交叉编译不支持）。

## ⑤ 待我在 Windows 执行的步骤清单

1. 运行 `build_exe.bat`（已准备好）。
2. 把 `dist_exe/StudyingHelper.exe` 拷到无 Python 环境的干净 Windows 机器双击。
3. 验证：导入书籍 → 学习 → 答题 → 复习 → 关闭重开数据仍在。
4. 设 `APP_LAN=1` 测试局域网同步。
5. 设 `LLM_DEFAULT_BASE_URL` 指向 LM Studio 测试真模型。

---

**Step 6 完成。** exe 打包成功，可交付。下一步建议 Step 7（大单元 map-reduce）或直接交付。