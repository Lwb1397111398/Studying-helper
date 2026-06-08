# document_parser 模块

## 概述

文档解析模块，负责将上传的 PDF/TXT/EPUB 文件解析为章节结构和纯文本。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（上传、解析状态、SSE 进度推送） |
| `schemas.py` | 请求/响应模型 |
| `service.py` | 解析服务（协调解析器、噪声清洗、目录检测） |
| `parsers/pdf_parser.py` | PDF 解析器（pdfplumber） |
| `parsers/txt_parser.py` | TXT 解析器（chardet 编码检测） |
| `parsers/epub_parser.py` | EPUB 解析器（ebooklib） |
| `toc_detector.py` | 目录检测（正则 + LLM fallback） |
| `noise_cleaner.py` | 噪声清洗（页眉页脚、重复空白） |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/documents/upload` | 上传文件 |
| GET | `/api/v1/documents/{book_id}/status` | 查询解析状态 |
| GET | `/api/v1/documents/{book_id}/parse` | 触发解析（SSE 进度） |

## 解析流程

```
上传 → 保存文件 → 创建 BookModel (pending)
  → 触发解析 → 解析器提取文本+章节
    → 噪声清洗 → 目录检测 → 更新 BookModel (completed)
```

## 已知问题

| 严重度 | 问题 | 位置 |
|--------|------|------|
| **严重** | 522 行，零测试覆盖，是整个项目风险最高的模块 | `router.py` |
| 中等 | async/sync 混用：pdfplumber 等同步库通过 `run_in_executor` 包装 | 全模块 |
| 中等 | SSE 进度推送无超时机制，客户端断开后服务端继续轮询 | `router.py` |
| 中等 | 进度存储基于内存（dict），重启后丢失 | `router.py` |
| 低 | PDF 解析器对扫描版 PDF 无 OCR 支持 | `pdf_parser.py` |
| 低 | TXT 编码检测依赖 chardet，对小文件准确率低 | `txt_parser.py` |

## 优化建议

1. **优先添加测试**: 至少覆盖 TXT 解析器（最简单）和 service 层
2. SSE 进度添加心跳和超时（建议 5 分钟）
3. 进度存储迁移到数据库或 Redis
4. 考虑将 `run_in_executor` 包装提取为统一工具函数

## 测试覆盖

- `tests/test_pdf_parser.py` — 存在
- `tests/test_txt_parser.py` — 存在
- `tests/test_service.py` — 存在
- `tests/test_toc_detector_enhanced.py` — 存在
- **router.py — 零覆盖**（最大风险点）
