# PRD: 建筑 · 工程规范图集知识库

## Introduction / Overview

建筑央企技术中心需要一套可演示的规范/图集知识库：把国标、行标、标准图集、施工方案与技术交底变成可检索、可引用、可按项目日期选版本的知识。工地问「保护层怎么做」「这是不是强制条文」时，系统必须给出**真实条文号 + 规范版本**，强制条文必须置顶并打「⚠ 强制性条文」标识。引用错误率必须为 0。

本 PRD 覆盖周一终验范围：采集→清洗→章-节-条-款切分→双索引→混合检索→统一 AI 上下文网关→四端客户端（Vue3 管理端、Flutter 工地端、Tauri2 交底端、Electron 图集端）。语料以**官方公开件 + 用户有权投放的 PDF** 为准（主语料为 GB 55008-2021），不以模型编造的条文号为准。

仓库内已有 `data/raw` 模拟摘录与部分 `backend` 草稿，仅作实验，**不纳入本 PRD 验收范围**。

## Goals

- 用官方公开的 GB 55008-2021 PDF（及废止强条清单）跑通七环节；若用户另投 GB 50010 摘录页则并入，过程有日志与中间产物。
- 强制性条文号与住建部第 743 号公告 14 条清单一致；命中强制条文时答案头部注入「⚠ 强制性条文」。
- 引用同时校验 `article_no` 与 `version`；校验失败则不得输出该引用。
- 按工程合同日期选择有效版本（有效期内取不晚于合同日的最新版）。
- 四端均调用同一份 ask/stream 契约；行业核心能力在四端分别落地。
- 黄金集 20 问；检索与答案指标达到作业基线或给出未达标原因与下一轮实验。
- 没配置 LLM Key 时，网关退化为「只摘检索命中条文」，仍保证引用为真。

## Decisions (from stakeholder)

| 项 | 选择 |
|---|---|
| 验收目标 | 1A 期末终验 |
| 四端 | 2A 四端都做深 |
| 语料 | 3A 曾选真实 PDF；落地改为官方公开 GB 55008 + 废止清单（不强制 50010 全书/图集） |
| 生成 | 4A 可插拔 LLM；无 Key 时抽取式作答 |
| 并行期 | 5A 合同日落在有效期内可检索；默认取不晚于合同日的最新版 |
| 已有草稿 | 6C 保留当实验，不写入本 PRD 范围 |
| 黄金集 | 20 问；条文号必须来自真实规范/官方公告 |
| 语料落地（2026-11-18 确认） | 主库：住建部公开的 GB 55008-2021 + 废止强条清单；不强制 GB 50010 全书与 G101 图集；禁止第三方转载站 |

## User Stories

### US-001: 投放正式 PDF 并登记元数据
**Description:** As a 知识管理员, I want to drop a licensed GB/JGJ PDF into `data/raw` and register std_code/version/valid_from/valid_to so that ingest does not guess identity.

**Acceptance Criteria:**
- [ ] `data/raw/` 存在登记表（如 `manifest.json`）字段：`std_code, version, title, valid_from, valid_to, filename, kind`
- [ ] 缺少主 PDF 时 ingest 以非 0 退出并打印「MISSING_PDF: GB 55008-2021」
- [ ] 运行时 ingest **不得**从互联网下载规范全文（已放入 `data/raw` 的官方公开附件除外）
- [ ] Typecheck/lint passes（Python ruff 或等价）

### US-002: 清洗管线产出 RawDoc / CleanDoc
**Description:** As a 知识管理员, I want PDF 文本抽出并清洗 so that 后续切分不依赖排版噪声。

**Acceptance Criteria:**
- [ ] 对 `GB55008-2021.pdf` 产出 `data/raw/*.raw.json`（页码、字符数）与 `data/clean/*.clean.json`（去页眉页脚后的文本）；若另有 50010 摘录页则同样产出
- [ ] 清洗报表含：页数、抽取成功率、空页列表
- [ ] 抽取失败的页写入 `ocr_needed` 列表，不静默丢弃

### US-003: 按章-节-条-款切分
**Description:** As a 检索工程师, I want chunks keyed by 章-节-条-款 so that 引用能落到条文号。

**Acceptance Criteria:**
- [ ] chunk 元数据含 `chapter, section, article_no, clause_no, std_code, version`
- [ ] 抽检：743 号公告 14 条强条号在 chunk 表中**全部出现**（无 50010 正文时允许以 `kind=pointer` 出现；article_no 必须为 `3.1.7` 这种点分格式）
- [ ] 切分抽检报告写入 `data/chunks/_qa.md`（至少 10 条人工抽检记录）

### US-004: 强制条文打标对齐官方清单
**Description:** As a 规范审核员, I want chunks tagged `mandatory` using the official 14-article list so that 安全问答不漏强条。

**Acceptance Criteria:**
- [ ] 系统加载 `tasks/ref-gb50010-2010-mandatory.csv`（14 行，来源：住建部公告第 743 号）
- [ ] 对 **GB 50010** chunk/指针：`article_no` 落在该 CSV 则为 `mandatory=true`，否则 false；对 **GB 55008** chunk：按该规范公告「全部条文必须严格执行」标 `mandatory=true`。关键词「必须/严禁」只作审核提示，**不得**覆盖上述两类权威规则
- [ ] 管理端可把误标改为已审核；审核后 `mandatory_reviewed=1`
- [ ] 识别准确率按「14 条召回 = 14/14」计算并写入评估报告

### US-005: 并行期按合同日期选版本
**Description:** As a 项目工程师, I want retrieval scoped by contract_date so that 2010 版与后续局部修订/GB/T 换版并行时不会串版本。

**Acceptance Criteria:**
- [ ] 查询参数含 `contract_date`（或 `project_id` → 合同日期）
- [ ] 仅检索 `valid_from <= contract_date <= valid_to` 的文档
- [ ] 同一 `std_code` 多版本命中时，默认保留 `valid_from` 最大且 `valid_from <= contract_date` 的版本
- [ ] 政策 `all_eligible` 时返回全部有效版本并在引用中并列标注版本号
- [ ] 演示用例：合同日 `2018-06-01` 可命中 GB 50010 指针；`2024-06-01`（默认 latest_eligible）检索结果**不含** GB 50010 指针 chunk，且至少 1 条 GB 55008 页级 chunk（`doc_id` 与 `page` 存在）。不把 50010 的 `documents.valid_to` 写成 2022-03-31。

### US-006: 双索引与强制通道加权
**Description:** As a 检索工程师, I want BM25 + 字符 3-gram TF-IDF 余弦（词法通道）and extra weight on mandatory chunks for safety queries so that 安全问题优先强条。

**Acceptance Criteria:**
- [ ] 每个 chunk 同时进入 BM25 与字符 3-gram TF-IDF 词法通道（不得称为语义向量）
- [ ] 仅当 query 含「强制/强条/必须/严禁」时 `s *= 1.25`（mandatory chunk）；不得用「保护层/配筋率」触发加权（避免与 G15 冲突）
- [ ] 若语料含授权图集页，则图集 chunk 可用 `fig_no` 精确过滤；无图集时本条不验收

### US-007: 网关 ask / stream + 强制条文头
**Description:** As a 任一端用户, I want a unified `/v1/ask` and `/v1/ask/stream` so that 四端答案策略一致。

**Acceptance Criteria:**
- [ ] 请求体含 `query, project_id|contract_date, client`
- [ ] 若检索命中 `mandatory=true`，答案纯文本**第一行**为 `⚠ 强制性条文`
- [ ] 无 LLM Key 时 `mode=extractive`：答案正文只拼接命中 chunk，不新增未检索数字
- [ ] 有 Key 时 `mode=llm`，但仍必须经过引用校验
- [ ] `/v1/ask/stream` 以 SSE 推送 token；强制条文头在首个 event 发出

### US-008: 条文号 + 版本双字段引用校验
**Description:** As a 技术负责人, I want every citation checked against warehouse so that 引用错误率为 0。

**Acceptance Criteria:**
- [ ] 每条 citation 必须含 `std_code, version, article_no`
- [ ] 校验：三元组必须在 chunk 表存在，否则剥离该 citation 并记 `dropped_citation`
- [ ] 模型若输出仓库中不存在的条文号，不得出现在最终 `citations[]`
- [ ] 评估脚本对黄金集计算「幻觉引用率」，目标 ≤ 2%，引用命中率 ≥ 0.9

### US-009: 全链路 trace
**Description:** As a 助教/评委, I want to open a trace id so that 七环节可点击核验。

**Acceptance Criteria:**
- [ ] 每次 ask 返回 `trace_id`
- [ ] `GET /v1/traces/{id}` 含：project/contract_date、检索 Top-k、是否强制通道、生成 mode、citations、dropped_citation
- [ ] 管理端可打开同一 trace

### US-010: Vue3 管理端 — 并行期与强条审核
**Description:** As a 技术中心管理员, I want a Vue3 admin so that 我能改有效期、审核 mandatory、看评估看板。

**Acceptance Criteria:**
- [ ] 页面：文档版本列表、有效期编辑、强条审核队列、评估指标、trace 查看
- [ ] 修改 `valid_to` 后，下一问检索立即按新区间过滤
- [ ] 审核 mandatory 后，下一问加权立即变化
- [ ] Typecheck passes
- [ ] Verify in a browser

### US-011: Flutter 工地离线条文速查
**Description:** As a 现场工程师, I want offline lookup of 强条 and article numbers so that 没网也能查。

**Acceptance Criteria:**
- [ ] 首次在线将 GB 50010-2010 强条 14 条指针（及已 sync 的 55008 条）+ 最近检索缓存写入本地 SQLite
- [ ] 飞行模式（或断网）下按条文号 `8.5.1` 能打开对应 chunk：无 50010 正文时展示**官方废止说明**，不得编造 50010 条款原文
- [ ] 离线命中强条时 UI 显示「⚠ 强制性条文」
- [ ] 在线 ask 走同一 `/v1/ask` 契约

### US-012: Tauri2 技术交底工作台
**Description:** As a 技术员, I want a Tauri2 desktop workbench so that 交底稿带真实条文引用。

**Acceptance Criteria:**
- [ ] 输入分部分项 + 合同日期，调用 `/v1/ask` 生成交底草稿
- [ ] 草稿底部列出 `std_code version article_no`，点击打开 chunk 原文
- [ ] 命中强条时稿件顶部显示「⚠ 强制性条文」
- [ ] 可导出 Markdown/纯文本
- [ ] Verify on desktop window

### US-013: Electron 标准图集查看端
**Description:** As a 翻样/施工员, I want Electron 按图号定位页面 so that 图集以图为主可查。

**Acceptance Criteria:**
- [ ] 有授权图集页时：输入真实图号滚动到对应页，图注+图号入索引
- [ ] 无图集时：按条文号定位 GB 55008 / 摘录 PDF，界面标明「图集未入库」
- [ ] 与 ask 契约一致：有图则引用含图号与图集版本；无图则引用条文号+版本
- [ ] 记录启动时间与内存，写入与 Tauri2 的对比表
- [ ] Verify in Electron window

### US-014: 黄金集 20 问与评估脚本
**Description:** As a 评委, I want 20 golden questions with real article numbers so that Recall/nDCG/引用命中可复现。

**Acceptance Criteria:**
- [ ] `eval/golden_set_20.json` 恰好 20 条；每条含 `id, query, expect_article_no, expect_version, expect_mandatory, contract_date, source`
- [ ] `expect_article_no` 不得为模型编造；GB 50010 强条问必须落在 743 号公告 14 条之内
- [ ] 非强条问的条文号必须在 PDF 切分结果中存在后才能标 `locked=true`；未锁定不得计入正式分数
- [ ] 脚本输出 Recall@5、nDCG@10、引用命中率、幻觉引用率、强条召回

### US-015: End-to-end test of 并行期 + 强制条文问答
**Description:** As a QA engineer, I want an automated E2E covering ingest→ask→citation→admin so that 终验主路径不回归。

**Acceptance Criteria:**
- [ ] Happy path：ingest 用户 PDF（或 CI 用的最小夹具页）→ ask「最小配筋率强制要求」且 `contract_date=2018-06-01` → 响应第一行为 `⚠ 强制性条文` → `citations` 含 `GB 50010` + `2010` + `8.5.1` → GET trace 可见检索列表
- [ ] Edge：ask 引用一个仓库不存在的条文号（提示词注入或 mock LLM）→ 最终 `citations` 不含该号，`dropped_citation >= 1`
- [ ] Edge：缺 `GB55008-2021.pdf` 时 ingest 失败信息为 `MISSING_PDF: GB 55008-2021`
- [ ] 测试可独立重复（自备/清理 DB）
- [ ] 测试在 CI 或本地一键脚本中通过

## Functional Requirements

- FR-1: The system must not scrape or download commercial standard/atlas full text at runtime. Official government public attachments already stored in `data/raw` may be parsed.
- FR-2: The system must require a local file for GB 55008-2021 before claiming ingest success; GB 50010 全书缺失时不得伪造正文，仅可从官方清单生成「废止指针」chunk（条文号真实、无假正文）。
- FR-3: The system must split code documents by 章-节-条-款.
- FR-4: The system must mark **GB 50010** mandatory articles exclusively from `tasks/ref-gb50010-2010-mandatory.csv` (14 rows). GB 55008 chunks are all mandatory per that code's official notice.
- FR-5: The system must treat keyword hits (必须/严禁) as review hints only, not as authority over the official list.
- FR-6: The system must store `std_code` and `version` as separate fields on every chunk and citation.
- FR-7: The system must filter retrieval by `valid_from <= contract_date <= valid_to`.
- FR-8: The system must default to the eligible version with the latest `valid_from` that is still `<= contract_date`.
- FR-9: The system must provide BM25 and character 3-gram TF-IDF cosine (lexical channel) over the same chunks. Do not describe this as a semantic vector index.
- FR-10: The system must boost mandatory chunks for safety-classified queries.
- FR-11: If authorized atlas pages are in the corpus, the system must index them by `fig_no` plus caption text; if none, skip without fabricating figure numbers.
- FR-12: The system must expose `POST /v1/ask` and `POST /v1/ask/stream`.
- FR-13: The system must inject the exact header `⚠ 强制性条文` as the first line when any cited chunk is mandatory.
- FR-14: The system must drop citations whose `(std_code, version, article_no)` is absent from the warehouse.
- FR-15: The system must return `trace_id` and persist a retrievable trace document.
- FR-16: The system must support extractive answers when no LLM credential is configured.
- FR-17: The admin Vue3 app must edit version validity windows.
- FR-18: The admin Vue3 app must review and override `mandatory` with an audit log.
- FR-19: The Flutter app must answer article-number lookup offline for the 14 mandatory articles after sync.
- FR-20: The Tauri2 app must generate a technical-disclosure draft with clickable citations.
- FR-21: The Electron app must locate an atlas page by figure number when authorized atlas pages exist; otherwise it must locate GB 55008 / 摘录 PDF by article number and declare atlas as out of corpus.
- FR-22: The four clients must share one OpenAPI contract package.
- FR-23: The evaluation harness must run the 20-question golden set and write a metrics JSON.
- FR-24: The system must record Tauri2 vs Electron startup time and RSS memory in `docs/desktop-compare.md`.

## Non-Goals

- 不采购/不爬取规范全文；不提供「全网规范下载」。
- 不把仓库里现有教学模拟 `data/raw/*.md` 当作终验语料。
- 不做 BIM、不算钢筋量、不替代结构师签字。
- 不保证覆盖全部国标。MVP 语料 = GB 55008-2021 扫描件（页定位）+ GB 50010-2010 强条清单（指针）；不收 50010 全文。
- 不在无 PDF 时用模型生成假条文正文充数。
- 不做多租户计费、不做公网生产加固（课程演示级鉴权即可）。

## Design Considerations

- 管理端：版本时间轴（并行期高亮）+ 强条审核队列表。
- 工地端：大号条文号、强条红底、离线标识。
- 交底端：左检索右稿件。
- 图集端：左图号树、右大图、下图注。
- 四端 UI 不确定时先出线框，再实现。

## Technical Considerations

- 版权：只解析已放入 `data/raw` 的文件；ingest 运行时不联网拉规范。
- 强条权威源：住建部公告第 **743** 号（2010-08-18）14 条清单，见 CSV。GB 55008 及其废止清单来自住建部公告 **2021 年第 167** 号，二者不得合并。50010 文档 `valid_to` 保持远期；14 条自 `mandatory_abolished_from=2022-04-01` 起不再作为强制指针进入默认检索。
- 易错点（评分命根）：**8.5.1 是最小配筋率，不是保护层**；保护层在目录上为 **第 8.2 节**。模拟语料若写反，终验前必须废弃。
- 网关八项职责至少实现：项目上下文、检索编排、强制加权、提示/头注入、流式、引用校验、trace；查询改写可选。
- 指标基线：Recall@5 ≥ 0.85，nDCG@10 ≥ 0.75，faithfulness ≥ 0.85，引用命中率 ≥ 0.9，幻觉引用率 ≤ 2%，入库到可检索 < 10 min，P95 < 3s。
- 周一时间盒：主路径 GB 55008-2021 + 50010 指针并行期 + 四端（Electron/Tauri 可共用 Vue dist）；50010 全书与图集仅在文件到位后加深。

## Success Metrics

- 14 条官方强条指针在索引中的条号召回 = 100%（入库完整性，不是 golden Recall@5）。
- Golden Recall 只统计 n=7（G01/G02/G03/G08/G09/G11/G14），仅作趋势参考。
- 黄金集 20 问中，已 `locked=true` 的子集引用错误率 = 0。
- 安全类问题答案第一行必为 `⚠ 强制性条文`（当期望 mandatory=true）。
- 四端各完成一条与网关契约一致的演示路径。
- 评估 JSON 与 trace 截图可提交。

## Golden set (20) — 条文号规则

权威文件：`eval/golden_set_20.json`（下表须与其 query / in_recall 一致）。

**Recall 分母 n=7（in_recall=true）：** G01、G02、G03、G08、G09、G11、G14。指标仅作趋势参考。不为凑分母编题。  
**单列不并入 Recall：** G17 版本闸门；G18 引用负例。  
**题面已去号、不计入 Recall：** G04、G05、G06、G07、G10、G12、G13、G20。  
**未锁定：** G15、G16、G19。

| id | query | expect_article_no | expect_version | expect_mandatory | contract_date | source |
|----|-------|-------------------|----------------|------------------|---------------|--------|
| G01 | GB 50010-2010 哪些条文是强制性条文？请列出条文号 | 3.1.7（及同批 14 条均可，至少命中一条强条） | 2010 | true | 2018-06-01 | 743号公告 |
| G02 | 混凝土结构设计中与基本规定相关的强制性条文是哪一条 | 3.1.7 | 2010 | true | 2018-06-01 | 743号公告 |
| G03 | 承载能力极限状态相关强制条文号 | 3.3.2 | 2010 | true | 2018-06-01 | 743号公告 |
| G04 | 混凝土材料强度相关强制条文 | 4.1.3 | 2010 | true | 2018-06-01 | 743号公告 |
| G05 | 混凝土材料另一条强制条文 | 4.1.4 | 2010 | true | 2018-06-01 | 743号公告 |
| G06 | 钢筋材料相关的强制性条文有哪些 | 4.2.2（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |
| G07 | 钢筋材料的另一条强制性条文 | 4.2.3（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |
| G08 | 纵向受力钢筋最小配筋率强制要求 | 8.5.1 | 2010 | true | 2018-06-01 | 743号公告 |
| G09 | 预应力混凝土构件一般规定中的强制条文 | 10.1.1 | 2010 | true | 2018-06-01 | 743号公告 |
| G10 | 抗震设计一般规定中的强制性条文 | 11.1.3（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |
| G11 | 抗震材料强制条文 | 11.2.3 | 2010 | true | 2018-06-01 | 743号公告 |
| G12 | 框架梁抗震构造中的强制性条文 | 11.3.1（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |
| G13 | 框架梁的另一条强制性条文 | 11.3.6（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |
| G14 | 剪力墙及连梁强制条文 | 11.7.14 | 2010 | true | 2018-06-01 | 743号公告 |
| G15 | 混凝土保护层厚度在哪一节（不得答成 8.5.1） | 8.2（节，条号待 PDF 抄录后锁定） | 2010 | false | 2018-06-01 | 规范目录 |
| G16 | 钢筋锚固在哪一节 | 8.3（条号待 PDF 锁定） | 2010 | false | 2018-06-01 | 规范目录 |
| G17 | 合同日期 2018-06-01 应使用哪个版本的 GB 50010 | GB 50010-2010 | 2010 | n/a | 2018-06-01 | 施行日期 2011-07-01 |
| G18 | 引用仓库中不存在的条文 99.9.9 应被丢弃 | （负例，citations 不得含 99.9.9） | 2010 | n/a | 2018-06-01 | 校验规则 |
| G19 | 按图号打开图集页 | 待用户图集 PDF 抄图号 | 图集版本 | n/a | 用户项目日期 | 用户图集 |
| G20 | 框架柱及框支柱的强制性条文 | 11.4.12（不计入 Recall） | 2010 | true | 2018-06-01 | 743号公告 |

G08 是易错题：答案必须是 **8.5.1 最小配筋率**，禁止把保护层写成 8.5.1。

## Open Questions

- 是否补 GB 50010 摘录页（不阻塞开工；无摘录则 G15/G16 保持未锁定）。
- 是否有授权图集页（无则 G19 未锁定，Electron 走条文定位降级）。
- LLM Key 是否到位（不到位则全程 extractive）。
- 四端安装包是否必须提交，还是源码 + 现场 `dev` 启动可接受。

## Blocked on user

无阻塞主路径：`GB55008-2021.pdf` 与废止清单已在 `data/raw/`。可选：50010 摘录页、图集页、LLM Key。
