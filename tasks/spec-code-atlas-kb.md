# SPEC: 建筑 · 工程规范图集知识库

> Technical specification derived from: `tasks/prd-code-atlas-kb.md`  
> Generated: 2026-11-18 | Target branch: `main` | Commit: (uncommitted greenfield + experimental stubs)

## 1. Summary

### 1.1 What This SPEC Covers

本 SPEC 规定课设终验系统的实现契约：MVP 语料 = **GB 55008-2021 扫描件（页定位）** + **GB 50010-2010 强条清单（指针）**；不收 50010 全文。55008 PDF 见体检表第 5 行（`usable_chars=0`，禁止全文切条）。经页级入库 + 指针 chunk → SQLite → BM25 + 字符 3-gram TF-IDF 词法通道 → FastAPI 网关 → 四端共用 OpenAPI。不实现爬虫、不编造 50010 条文正文、不把未核实页码写入黄金集。

实验草稿（`data/raw/GB50010-2010.md` 等、未完成 `backend/app/*`）可参考结构，验收以本 SPEC 重写后的模块为准。

### 1.2 PRD Reference

- Source: `tasks/prd-code-atlas-kb.md`
- User Stories: US-001 … US-015
- Functional Requirements: FR-1 … FR-24  
- Alignment: 2026-11-18 对照 PRD 与 `data/raw/_corpus_report.md`。词法通道为字符 3-gram TF-IDF 余弦；全文不得出现「语义向量」。

### 1.3 Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| 主语料 | 55008 扫描页定位 + 50010 十四指针 | 体检表 #5 无正文；#6 仅 provenance |
| 50010 全书 | 不收 | 版权 |
| 55008 角色 | page 级 chunk，不承诺条文正文 | extract_text 仅水印 |
| 图集 | 有授权页则 fig_no；否则 Electron 按条文号/页 | 避免假图号 |
| 后端 | 单进程 FastAPI + SQLite | 课设可一键演示 |
| 双通道 | jieba BM25 + 字符 3-gram TF-IDF 余弦（词法） | 不是语义向量 |
| 生成 | `OPENAI_API_KEY` 可选；默认 extractive | 引用错误率优先 |
| 前端复用 | 一个 Vue3 SPA，`?client=admin\|electron\|tauri`；Flutter 独立 | 与 AskRequest.client 枚举一致：admin\|flutter\|tauri\|electron |
| 鉴权 | 演示用 `X-Role: admin\|user` | 课设级 |

---

## 2. Architecture

### 2.1 System Context

```
[Vue Admin] [Electron] [Tauri] [Flutter]
        \       |        |        /
         \      |        |       /
              FastAPI :8000
         /ingest /v1/ask /v1/ask/stream /v1/traces /admin
                    |
         SQLite warehouse.sqlite  +  in-memory BM25/TF-IDF
                    ^
         data/raw/*.pdf  manifest.json  tasks/ref-*-mandatory.csv
```

### 2.2 Component Design

| Module | Responsibility |
|--------|----------------|
| `ingest.manifest` | 读 `data/raw/manifest.json`，缺主 PDF 则失败 |
| `ingest.pdf_extract` | 对 55008：不抽条文；登记每页为 page chunk（可附页图）。体检表 #5 |
| `ingest.chunker` | 仅对 **有文本层** 的 code PDF 跑章-节-条；55008 不走此路 |
| `ingest.pointers` | CSV 生成 14 条指针，`text` 含 `chapter_hint`（公告第743号） |
| `index.hybrid` | BM25 + 字符 3-gram TF-IDF；**仅 text 变更时重建** |
| `gateway.retrieve` | 合同日期过滤 → 混合检索 → safety 加权 → Top-k |
| `gateway.cite` | 校验 (std_code, version, article_no) |
| `gateway.answer` | extractive 或 LLM，强制头注入 |
| `gateway.trace` | JSON 落库 |
| `web` | 管理/图集/交底三模式 |
| `flutter` | 离线条文号查询 |

### 2.3 Module Interactions

1. `python scripts/preflight_corpus.py` → `_corpus_report.md`  
2. `python -m app.ingest` → pointers + 55008 页级 chunk；全文切条仅当体检 `fulltext-ingest-ok`  
3. Client POST `/v1/ask` → 每次从 **DB** 读 `mandatory` 与 `valid_from`/`valid_to`/`mandatory_abolished_from`（不读索引快照）→ retrieve → answer → cite ⊆ 本次 `chunk_id`  
4. Admin PATCH 有效期/mandatory → 写库即生效，不重建索引；仅 `text` 变才重建 BM25/TF-IDF  
5. Flutter GET `/v1/sync/mandatory` → 本地 SQLite  

### 2.4 File Structure

```
data/raw/manifest.json              [NEW]
data/raw/_corpus_report.md          [EXISTS preflight]
data/raw/GB55008-2021.pdf           [EXISTS _corpus_report.md #5 scan-page-locate usable_chars=0]
data/raw/GB55008-abolished-mandatory.docx [EXISTS #6 provenance-only OLE/.doc]
data/raw/SOURCE.md                  [EXISTS #8 provenance-only]
tasks/ref-gb50010-2010-mandatory.csv [EXISTS 743 号 14 条]
data/clean/                         [NEW artifacts]
data/chunks/                        [NEW artifacts]
data/warehouse.sqlite               [NEW]
eval/golden_set_20.json             [EXISTS]
eval/run_eval.py                    [NEW]
packages/api-contract/openapi.yaml  [NEW]
backend/app/
  main.py ingest.py pdf_extract.py chunker.py pointers.py
  search.py retrieve.py cite.py answer.py traces.py admin_api.py
apps/web/                           [NEW Vue3 Vite]
apps/electron/                      [NEW]
apps/tauri-handover/                [NEW]
apps/flutter_site/                  [NEW]
docs/adr/0001-stack.md              [NEW]
docs/desktop-compare.md             [NEW]
tests/test_e2e_ask.py               [NEW]
```

实验用 `data/raw/*.md` 默认 **不** 进入 `manifest.json`。

---

## 3. Data Model

### 3.1 Schema Changes

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,           -- e.g. GB55008-2021
  std_code TEXT NOT NULL,        -- GB 55008
  version TEXT NOT NULL,         -- 2021
  title TEXT,
  kind TEXT,                     -- code | atlas | pointer
  status TEXT,                   -- active | abolished
  valid_from TEXT NOT NULL,      -- ISO date
  valid_to TEXT NOT NULL,
  mandatory_abolished_from TEXT, -- e.g. 2022-04-01; 强条废止日，不是整本失效
  source_path TEXT,
  replaced_by TEXT
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT NOT NULL,
  std_code TEXT NOT NULL,
  version TEXT NOT NULL,
  kind TEXT,
  valid_from TEXT,
  valid_to TEXT,
  chapter TEXT,
  section TEXT,
  article_no TEXT NOT NULL,      -- 4.4.2 or pointer 8.5.1
  clause_no TEXT,
  fig_no TEXT,
  page INTEGER,
  caption TEXT,
  mandatory INTEGER NOT NULL,
  mandatory_source TEXT,         -- gb55008_all | csv_743 | human_review | keyword_hint
  mandatory_reviewed INTEGER DEFAULT 0,
  text TEXT NOT NULL
);
CREATE INDEX idx_chunk_cite ON chunks(std_code, version, article_no);
CREATE INDEX idx_chunk_valid ON chunks(valid_from, valid_to);

CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT,
  contract_date TEXT NOT NULL,
  version_policy TEXT NOT NULL DEFAULT 'latest_eligible'
);

CREATE TABLE traces (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  payload TEXT
);

CREATE TABLE reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id INTEGER,
  action TEXT,
  note TEXT,
  created_at TEXT
);
```

### 3.2 Entity Definitions

```python
class Citation(TypedDict):
    std_code: str
    version: str
    article_no: str
    clause_no: str
    fig_no: str
    mandatory: bool
    chunk_id: int

class AskRequest(TypedDict):
    query: str
    project_id: str | None
    contract_date: str | None  # YYYY-MM-DD
    client: str  # admin | flutter | tauri | electron  only; no atlas|handover
    top_k: int  # default 8
```

### 3.3 Relationships

- chunks.N : 1 documents  
- traces 无 FK，payload 内嵌 chunk_id 列表  
- 指针 chunk：`doc_id=GB50010-2010-pointers`，`kind=pointer`。`text` 必须含 CSV `chapter_hint`，模板：  
  `"{chapter_hint}；GB 50010-2010 第{article_no}条为强制性条文，自 2022-04-01 起废止，由 GB 55008-2021 承担。来源：住建部公告第743号。"`  
  **不含编造的 50010 条款正文。** 单测：14 条 text 均含对应 chapter_hint。

### 3.4 Migration Plan

无历史生产库。`ingest` 可 `--reset` 删库重建。回滚=保留 `data/raw` 重新 ingest。

**种子项目**

| id | contract_date | version_policy | 预期（禁止断言未核实页码） |
|----|---------------|----------------|------------------------------|
| P-2018 | 2018-06-01 | latest_eligible | 可含 GB 50010 指针；55008 尚未施行则无 55008 页级 chunk |
| P-2024 | 2024-06-01 | latest_eligible | **不含** GB 50010 指针；至少 1 条 GB 55008 页级 chunk（`doc_id` 与 `page` 字段存在） |
| P-PARALLEL | 2024-03-15 | all_eligible | 两个 `std_code` 并列：50010 指针 + 55008 页级 chunk；不得空结果 |

GB 55008：`valid_from=2022-04-01`，`valid_to=2099-12-31`  
GB 50010 指针文档：`valid_from=2011-07-01`，`valid_to=2099-12-31`，`mandatory_abolished_from=2022-04-01`  

默认 `latest_eligible` 且 `contract_date >= mandatory_abolished_from` 时，**过滤 `kind=pointer`**（强条已改由 55008 承担，不把整本 50010 标失效）。`all_eligible` 仍可并列返回指针（历史强条号）与 55008 页。

---

## 4. API Design

### 4.1 Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/v1/ingest` | 触发本地 ingest（管理员） | X-Role: admin |
| GET | `/v1/documents` | 文档与有效期 | user |
| PATCH | `/v1/documents/{id}` | `{valid_from,valid_to,status}` | admin |
| GET | `/v1/chunks` | 筛选 mandatory / std_code | user |
| PATCH | `/v1/chunks/{id}/mandatory` | `{mandatory, note}` | admin |
| GET | `/v1/projects` | 项目列表 | user |
| POST | `/v1/ask` | 问答 | user |
| POST | `/v1/ask/stream` | SSE | user |
| GET | `/v1/traces/{id}` | 追踪 | user |
| GET | `/v1/eval/latest` | 最近评估 JSON | admin |
| GET | `/v1/sync/mandatory` | Flutter 离线包 | user |
| GET | `/health` | 存活 | none |

### 4.2 Request/Response Schemas

`POST /v1/ask` body:

```json
{
  "query": "纵向受力钢筋最小配筋率强制要求",
  "project_id": "P-2018",
  "client": "admin",
  "top_k": 8
}
```

Response:

```json
{
  "trace_id": "uuid",
  "mode": "extractive",
  "mandatory_hit": true,
  "answer": "⚠ 强制性条文\n...",
  "citations": [
    {
      "std_code": "GB 50010",
      "version": "2010",
      "article_no": "8.5.1",
      "mandatory": true,
      "chunk_id": 12
    }
  ],
  "dropped_citation": [],
  "used_versions": [{"std_code": "GB 50010", "version": "2010"}]
}
```

约束：`answer` 若 `mandatory_hit` 则**第一行精确等于** `⚠ 强制性条文`（全角叹号）。

SSE：首 event `event: meta` 含强制头标志；随后 `event: token`；结束 `event: done` 含 citations。

`GET /v1/sync/mandatory`：JSON 数组 `{article_no,std_code,version,mandatory,text,valid_from,valid_to}`。

### 4.3 Error Responses

见 §6.1。

### 4.4 Breaking Changes

无既有外部客户端。OpenAPI 作为四端唯一契约，字段改名需同步 `packages/api-contract/openapi.yaml`。

---

## 5. Business Logic

### 5.1 Core Algorithms

**Ingest**

1. 先跑 / 读取 `data/raw/_corpus_report.md`。  
2. 读 manifest；若 `GB55008-2021.pdf` 不存在 → exit 2，`MISSING_PDF: GB 55008-2021`（缺的是扫描件，不是 50010 全书）。  
3. **禁止**对体检 `need_ocr=true` / `usable_chars=0` 的 PDF 做 `extract_text`→条号切分。55008（#5）：为每一页插入 `kind=page` chunk：`doc_id, page, std_code, version`，`article_no` 可空，`text` 可为「扫描页 p{n}，无文本层」。可选存页图。  
4. 章-节-条正则 **仅**用于 `ingest_role=fulltext-ingest-ok` 的文件（当前验收语料中不存在此类 PDF）。  
5. 55008 页级 chunk：`mandatory_source=gb55008_scan`；不声称已切出 55008 条号。  
6. 从 `tasks/ref-gb50010-2010-mandatory.csv` 生成 14 条 pointer（公告 **第743号**）。`text` 用 §3.3 模板（含 `chapter_hint`）。废止清单文件（#6，公告 **2021年第167号 附件2**）只作 provenance，不作为 python-docx 正文源。  
7. 若日后出现有文本层的 50010 摘录且体检通过：再切分；`mandatory` 仅当 article_no ∈ CSV。  
8. 关键词「必须/严禁」只写 `keyword_hint`，不覆盖 CSV / 55008 规则。  
9. 重建 BM25 + 字符 3-gram TF-IDF（词法通道）。  

**Version select**

```
eligible = chunks where valid_from <= contract_date <= valid_to
if policy == latest_eligible and contract_date >= doc.mandatory_abolished_from:
    drop kind == pointer
if policy == latest_eligible:
    for each std_code: keep version with max(valid_from)
if policy == all_eligible:
    keep all eligible (pointers may appear beside 55008 pages)
```

**Hybrid retrieve**

- tokens = jieba.lcut(query)  
- s_bm25 = rank_bm25 归一化  
- s_lex = cosine(char-3gram-tfidf(query), chunk)  
- s = 0.6 * s_bm25 + 0.4 * s_lex  
- 仅当 query 含「强制」「强条」「必须」「严禁」之一且 chunk.mandatory：`s *= 1.25`  
- 不得用「保护层」「配筋率」「安全」「抗震」触发加权  
- 返回 Top-k  

**Extractive answer**

- 指针命中：`⚠ 强制性条文`（若 mandatory 且未过 abolished_from）+ 指针 `text` + 条文号  
- 55008 页级命中：给出 `doc_id` + `page` + 公告出处（167 号），**不编造该页条文号**  
- citations 只来自本次检索 hits  

**LLM answer（可选）**

- prompt 只给本次 hits  
- 输出 JSON `{answer, citations:[{chunk_id,...}]}`  

**Cite**

- `citations ⊆ 本次检索返回的 chunk_ids`  
- 同时校验 `chunk_id` 在 warehouse 且三元组一致  
- `99.9.9` 必须 drop  

### 5.2 Validation Rules

- `contract_date` ISO 日期  
- `query` 1–500 字  
- `article_no` 匹配 `^\d+(\.\d+){1,3}$` 或图号（有图集时）  
- 不得在 ingest 时请求外网下载规范  

### 5.3 State Machine

Document `status`: `active` ↔ `abolished`（admin PATCH）。`abolished` 仍可被 `valid_*` 过滤；默认检索只取 `active` **或** 指针 kind（指针 status=abolished 但在 valid 期内可检索，以 `kind=pointer` 例外）。

规则：**kind=pointer 在 valid 期内可检索**；kind=code 仅 status=active。

### 5.4 Edge Cases

| Case | Handling |
|------|----------|
| 无 55008 PDF | ingest 失败 `MISSING_PDF: GB 55008-2021` |
| 55008 无文本层 | 页级 chunk，不切条 |
| 无 50010 正文 | 指针 text 含 chapter_hint + 废止说明，仍可引用 8.5.1 号 |
| 合同日早于所有 valid_from | 空检索，answer 说明无适用版本，citations=[] |
| 图集缺失 | `/v1/ask` 不编图号；Electron 切换为 PDF 条文定位 |
| OCR 空页 | 记 ocr_needed，不丢页码 |
| 切不出条号 | chunk 降级为 section 级，article_no 用 section，不得进入黄金集 locked 强条统计 |

---

## 6. Error Handling

### 6.1 Error Taxonomy

| Error Code | HTTP | Condition | User Message |
|------------|------|-----------|--------------|
| MISSING_PDF | 422 | 无 55008 文件 | MISSING_PDF: GB 55008-2021 |
| EMPTY_CORPUS | 503 | 未 ingest | 知识库为空，请先入库 |
| BAD_DATE | 400 | 日期非法 | contract_date 须为 YYYY-MM-DD |
| NOT_FOUND | 404 | 无 trace/文档 | 资源不存在 |
| FORBIDDEN | 403 | 非 admin 写操作 | 需要管理员角色 |
| UPSTREAM_LLM | 200 | LLM 失败 | 降级 extractive，trace.mode=extractive_fallback |

### 6.2 Retry Strategy

- ingest：失败不自动重试  
- LLM：1 次超时（8s）后立即 extractive  

### 6.3 Failure Modes

- jieba 缺失：退回字符 2-gram  
- 索引未建：ask 返回 503  
- Flutter 离线且从未 sync：显示「请先在线同步」  

---

## 7. Security

### 7.1 Authentication & Authorization

演示：`X-Role` 默认 `user`；写接口要 `admin`。禁止实现「任意用户上传规范 URL 代下载」。

### 7.2 Input Validation

限制 query 长度；SQLite 参数绑定；不把用户 query 拼进 SQL。

### 7.3 Data Protection

仓库含规范摘录，不公开部署到公网。trace 保留 7 天即可（课设可永久）。

---

## 8. Performance

### 8.1 Expected Load

课设演示：单用户，chunks < 2000，P95 ask（extractive）< 3s。

### 8.2 Optimization Strategy

索引常驻内存；ask 同步计算；stream 对 extractive 按句切 SSE。

### 8.3 Database Considerations

cite 三列索引；chunks 全表扫描可接受。

---

## 9. Testing Strategy

### 9.1 Unit Tests

- chunker 对 55008 样例页抽出 `x.x.x`  
- pointer 生成恰好 14 条且号与 CSV 一致  
- cite 丢弃 99.9.9  
- version filter：2018 latest 不含 55008 页；2024 latest 不含 pointer  
- pointer text 含 chapter_hint  
- 强制头第一行  

### 9.2 Integration Tests

- ingest 真实 `GB55008-2021.pdf`：产生 ≥1 条 `kind=page` 且 `page` 非空；**0** 条从该 PDF 抽出的 article 正文  
- POST ask P-2018「最小配筋率」→ citation `GB 50010` `2010` `8.5.1`  
- POST ask P-2024 任意非空 query：hits 中 **0** 条 `kind=pointer` / `std_code=GB 50010`；至少 1 条 `std_code=GB 55008` 且 `page` 字段存在。不断言具体页码数字  

### 9.3 Edge Case Tests

- MISSING_PDF  
- mock LLM 输出假条文号 → dropped_citation  

### 9.4 Acceptance Criteria Mapping

| US/FR | Test | Type |
|-------|------|------|
| US-001 / FR-2 | test_missing_pdf | unit |
| US-003 | test_chunk_article_pattern | unit |
| US-004 | test_14_pointers | unit |
| US-005 | test_contract_date_filter | unit |
| US-007 / FR-13 | test_mandatory_header | api |
| US-008 / FR-14 | test_drop_fake_cite | api |
| US-009 | test_trace_roundtrip | api |
| US-014 | eval/run_eval.py | eval | Recall 分母 **n=7**：G01/G02/G03/G08/G09/G11/G14。仅趋势参考。G17 版本闸门、G18 引用负例单列。expect 为空或不 in_recall 的题不计入 Recall。不为凑 n 编题。 |
| US-015 | tests/test_e2e_ask.py | e2e |
| FR-19 | flutter widget test 离线条文号 | flutter |
| FR-24 | docs/desktop-compare.md 手工填数 | manual |

---

## 10. Implementation Plan

### 10.1 Phases

1. manifest + ingest 55008 + pointers + artifacts  
2. hybrid index + retrieve + date filter  
3. gateway ask/stream/trace/cite  
4. eval 20 问（locked 子集）  
5. Vue admin  
6. Electron / Tauri 包同一 SPA  
7. Flutter sync + offline  
8. e2e + desktop-compare  

### 10.2 Issue Mapping

实现前由 `/to-issues` 生成 `tasks/issues-code-atlas-kb.md`。预映射：

| Issue | SPEC | Priority | Depends |
|-------|------|----------|---------|
| I-01 ingest+pointers | 5.1 ingest, 3.x | P0 | — |
| I-02 search+version | 5.1 retrieve | P0 | I-01 |
| I-03 gateway | 4.x, 5.1 answer/cite | P0 | I-02 |
| I-04 eval | 9.4 US-014 | P0 | I-03 |
| I-05 admin Vue | US-010 | P0 | I-03 |
| I-06 electron/tauri | US-012/013 | P1 | I-05 |
| I-07 flutter | US-011 | P1 | I-03 |
| I-08 e2e | US-015 | P0 | I-03 |

### 10.3 Incremental Delivery

每天可演示：先 CLI ingest+ask，再浏览器 admin，再桌面壳。

---

## 11. Open Questions & Risks

### 11.1 Unresolved Questions

- 55008 PDF 文本层是否可选中（扫描件则需 OCR，本 SPEC 不强制上 OCR 引擎，只记 ocr_needed）  
- 用户是否补 50010 摘录页（不阻塞 I-01）  
- 是否提供 OPENAI_API_KEY（不阻塞，默认 extractive）  

### 11.2 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| PDF 无文本层 | 切分失败 | 报表列出空页；指针通道仍可演示条文号 |
| 55008 条号版式不规整 | 召回下降 | 人工抽检 10 条改正则 |
| 四端工期 | Electron/Tauri 装包失败 | 至少 `npm run dev` 加载同一 SPA |
| Recall 仅 n=7 | 指标不能对标作业 0.85 | 报告写明趋势参考，不编题凑分母 |

### 11.3 Assumptions

- 首都之窗附件 PDF 与住建部公开文本一致，可作为课设语料  
- GB 55008 全部条文按公告视为强制  
- 50010 **强条**废止日取 2022-04-01（55008 实施日）；文档 `valid_to` 仍为 2099-12-31  
- 实验 md 语料不进入 manifest  
- Windows 本机 Python 3.13 + Node 24 可用；Flutter SDK 可用  

---

## 12. Manifest 约定

`data/raw/manifest.json` 示例：

```json
{
  "documents": [
    {
      "id": "GB55008-2021",
      "std_code": "GB 55008",
      "version": "2021",
      "title": "混凝土结构通用规范",
      "kind": "code",
      "status": "active",
      "valid_from": "2022-04-01",
      "valid_to": "2099-12-31",
      "filename": "GB55008-2021.pdf",
      "required": true
    },
    {
      "id": "GB50010-2010-pointers",
      "std_code": "GB 50010",
      "version": "2010",
      "title": "废止强制性条文指针",
      "kind": "pointer",
      "status": "active",
      "valid_from": "2011-07-01",
      "valid_to": "2099-12-31",
      "mandatory_abolished_from": "2022-04-01",
      "pointer_source": "住建部公告第743号",
      "abolition_annex": "住房和城乡建设部公告2021年第167号 附件2",
      "filename": "GB55008-abolished-mandatory.docx",
      "filename_note": "provenance-only OLE/.doc；指针正文来自 CSV chapter_hint 模板",
      "required": true
    }
  ]
}
```
