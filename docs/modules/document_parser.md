# document_parser 模块

## 职责

负责把上传的 PDF/TXT/EPUB 转成后续可拆分的章节结构，并支持目录预览、目录确认和解析进度查询。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/documents` 路由 |
| `service.py` | 解析流程编排、上传状态、目录确认 |
| `schemas.py` | 上传/解析/目录相关模型 |
| `parsers/pdf_parser.py` | PDF 文本解析 |
| `parsers/txt_parser.py` | TXT 编码检测和章节解析 |
| `parsers/epub_parser.py` | EPUB manifest/spine 和 HTML 清理 |
| `toc_detector.py` | 目录识别 |
| `toc_prompt.py` | LLM 辅助目录识别 prompt |
| `noise_cleaner/` | 页眉页脚、目录、前后文噪声清理 |

## API 入口

前缀：`/api/v1/documents`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/parse` | 上传并同步/半同步解析 |
| POST | `/parse/start` | 启动解析任务 |
| GET | `/parse/{upload_id}/progress` | 查询解析进度 |
| GET | `/formats` | 查询支持格式 |
| GET | `/{book_id}/toc/preview` | 获取目录预览 |
| POST | `/{book_id}/toc/confirm` | 确认目录并写入章节 |

## 数据流

```text
UploadFile
  -> FileStorage 保存文件
  -> 根据扩展名选择 parser
  -> 清理噪声和目录
  -> 生成 Chapter / Toc 结构
  -> 写 BookModel / ChapterModel
  -> 等待 knowledge_splitter 拆单元
```

## 依赖关系

- 依赖 `user_storage.services.file_storage` 保存文件。
- 依赖 `BookModel`、`ChapterModel`。
- 可选依赖 parser LLM client，用于目录识别 fallback。
- 下游是 `knowledge_splitter`。

## Web / Android 关系

- Web 上传走后端 `document_parser`。
- Android 有端侧 TXT/EPUB/PDF 基础导入，不必经过后端解析；同步时再把结果带回 Web。

## 验证入口

```bash
cd backend && python -m pytest app/modules/document_parser/tests/ -q
```

## 已知风险

- 扫描版 PDF 不等于文字型 PDF；当前主要处理可抽取文本。
- LLM 目录识别不可作为唯一可靠路径，规则解析仍需可用。
- 目录确认会影响后续章节和知识单元 ID/顺序，改动时要检查 split 流程。
