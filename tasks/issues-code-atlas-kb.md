# Issues: 建筑规范图集知识库

Source: `tasks/prd-code-atlas-kb.md` + `tasks/spec-code-atlas-kb.md`  
Remote: `git@github.com:zsun17696-spec/architecture.git`  
Preflight: `data/raw/_corpus_report.md`（改 ingest 前先跑 `python scripts/preflight_corpus.py`）

依赖：I-01 → I-02 → I-03 → (I-04, I-05, I-08) ；I-06 依赖 I-05；I-07 依赖 I-03。

---

## I-01 ingest + 14 指针 + 55008 页级 chunk  [P0]

**SPEC:** §3, §5.1 Ingest, §12  
**PRD:** US-001, US-002, US-003, US-004, FR-2, FR-4

- [x] `data/raw/manifest.json` 按 SPEC §12（50010 `valid_to=2099-12-31`，`mandatory_abolished_from=2022-04-01`；167 与 743 分字段）
- [x] 缺 `GB55008-2021.pdf` → 非 0 退出 `MISSING_PDF: GB 55008-2021`
- [x] 体检 #5：只建 `kind=page`（`doc_id`+`page`），**0** 条从该 PDF 抽出的条文正文
- [x] CSV 生成 14 条 `kind=pointer`，`text` 含 `chapter_hint` + 743 号来源模板
- [x] #6 OLE `.doc` 标 provenance-only，不用 python-docx 当正文
- [x] 实验 `*.md` / `atlas-11G101-1.json` 不进 manifest
- [x] 中间产物：clean/chunks 报表；单测 pointer=14 且含 chapter_hint

## I-02 检索 + 合同日期 + 词法双通道  [P0]

**SPEC:** §5.1 retrieve / version select  
**PRD:** US-005, US-006, FR-7, FR-8, FR-9, FR-10

- [x] BM25 + 字符 3-gram TF-IDF 余弦；文档禁止写「语义向量」
- [x] 每次查询从 DB 读 mandatory / 有效期；仅 text 变才重建索引
- [x] `latest_eligible` 且 `contract_date >= mandatory_abolished_from` → 过滤 pointer
- [x] P-2018：可含 50010 指针，无 55008 页
- [x] P-2024：0 条 50010 指针；≥1 条 55008 `kind=page`（不断言页码数字）
- [x] P-PARALLEL `all_eligible`：两 std_code 并列且非空
- [x] safety：仅「强制/强条/必须/严禁」时 `s *= 1.25`

## I-03 网关 ask/stream/cite/trace  [P0]

**SPEC:** §4, §5.1 answer/cite, §6  
**PRD:** US-007, US-008, US-009, FR-12–16, FR-22

- [x] `packages/api-contract/openapi.yaml`；`client` ∈ `admin|flutter|tauri|electron`
- [x] `POST /v1/ask`、`/v1/ask/stream`、`GET /v1/traces/{id}`
- [x] mandatory 命中时答案第一行精确 `⚠ 强制性条文`
- [x] 无 Key → extractive；cite ⊆ **本次** `chunk_id`
- [x] 假条文 99.9.9 → `dropped_citation`
- [x] 指针答案不编 50010 正文；55008 页命中只给 doc_id+page+167 号出处

## I-04 黄金集评估 n=7  [P0]

**SPEC:** §9.4  
**PRD:** US-014  
**权威:** `eval/golden_set_20.json`

- [x] `eval/run_eval.py` 只把 `in_recall=true` 的 7 题计入 Recall（G01/G02/G03/G08/G09/G11/G14）
- [x] G17 版本闸门、G18 引用负例单列
- [x] 报告写明「趋势参考，n=7，不对标作业 0.85」
- [x] 不为凑分母编题或编页码

## I-05 Vue3 管理端  [P0]

**SPEC:** §2 web  
**PRD:** US-010, FR-17, FR-18

- [x] 文档有效期编辑、强条审核、评估看板、trace
- [x] PATCH 后下一问立即用 DB 新值
- [x] `?client=admin`；浏览器可验

## I-06 Electron + Tauri（同一 dist）  [P1]

**PRD:** US-012, US-013, FR-21, FR-24

- [x] 同一 Vue dist：`client=electron|tauri`
- [x] 无图集：按条文号/扫描页定位，标明「图集未入库」
- [x] 交底草稿带 citations，强条头
- [x] `docs/desktop-compare.md` 启动时间与 RSS

## I-07 Flutter 离线速查  [P1]

**PRD:** US-011, FR-19

- [x] `GET /v1/sync/mandatory` → 本地 SQLite
- [x] 离线查 `8.5.1` 打开指针 text（废止说明 + chapter_hint），不编 50010 原文
- [x] 在线走同一 `/v1/ask`

## I-08 E2E  [P0]

**PRD:** US-015

- [x] Happy：ingest → P-2018 最小配筋率 → ⚠ + `8.5.1`
- [x] P-2024 断言见 I-02（无指针 + 有 page chunk）
- [x] MISSING_PDF；假引用被丢弃
- [x] 可重复跑（`--reset`）

---

实现顺序：I-01 → I-02 → I-03 → I-08 与 I-04 可并行于网关之后 → I-05 → I-06/I-07。
