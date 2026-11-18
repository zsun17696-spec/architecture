# ADR 0001：课设技术栈与主语料

- Status: accepted
- Date: 2026-11-18

## Context

周一终验要同时交代版本治理、引用完整性与四端演示。仓库里没有可合法入库的 GB 50010 全书，也没有授权图集页。GB 55008-2021 PDF 为扫描件（体检表 #5，`usable_chars=0`）。

## Decision

- 主语料 = GB 55008 页级定位（公告 167）+ GB 50010-2010 十四强条指针（公告 743）。两公告分字段，不合并。
- 后端：单进程 FastAPI + SQLite；检索为 BM25 + 字符 3-gram TF-IDF（词法，不是语义向量）。
- 生成默认 extractive；强制性条文命中时答案第一行精确为 `⚠ 强制性条文`。
- 前端：一个 Vue3 dist，`?client=admin|electron|tauri`；Flutter 独立，离线包来自 `GET /v1/sync/mandatory`。

## Consequences

- 可答辩「并行期 / 引用校验 / 扫描件不编条号」，不能冒充建标库全文。
- Recall 只计黄金集 n=7，不对标作业 0.85。
- 图集未入库时 Electron 只做条文号/扫描页定位。
