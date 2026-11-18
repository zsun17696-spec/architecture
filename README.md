# architecture

课设：建筑 · 工程规范图集知识库（GB 55008 扫描页定位 + GB 50010-2010 强条指针）。

**终验走查（12 分钟）+ 答辩口径：** `docs/ship-walkthrough.md`  
**栈决策：** `docs/adr/0001-stack.md`

- 需求：`tasks/prd-code-atlas-kb.md`
- 设计：`tasks/spec-code-atlas-kb.md`
- 任务卡：`tasks/issues-code-atlas-kb.md`
- 语料体检：`python scripts/preflight_corpus.py` → `data/raw/_corpus_report.md`

实现按 Issues I-01 → I-08。未配置 LLM 时抽取式作答。不入库实验用 `data/raw/*.md`。

```text
python -m pip install -r backend/requirements.txt
python scripts/preflight_corpus.py
python scripts/ingest.py
```

入库结果：`data/clean/_ingest_report.md`（14 条 743 号指针 + GB 55008 扫描页，0 条从扫描件抽出的条文正文）。

```text
python scripts/search_demo.py
```

同一问「最小配筋率强制性条文」：P-2018 命中 GB 50010 指针；P-2024 只剩 GB 55008 扫描页；P-PARALLEL 两套标准号并列。检索通道为 BM25 + 字符 3-gram TF-IDF（词法，不是语义向量）。

```text
python scripts/run_gateway.py
```

四端共用 `POST /v1/ask`、`/v1/ask/stream`、`GET /v1/traces/{id}`（`packages/api-contract/openapi.yaml`）。无 Key 时 extractive；强条命中首行 `⚠ 强制性条文`；引用必须落在本轮 `chunk_id`。

```text
python eval/run_eval.py
python scripts/e2e.py --reset
```

评估只计黄金集 `in_recall` 的 7 题（G01/G02/G03/G08/G09/G11/G14），报告写明趋势参考、不对标作业 0.85。G17/G18 单列。E2E：ingest → P-2018 ⚠+`8.5.1` → P-2024 扫描页 → 99.9.9 丢弃。

```text
python scripts/run_gateway.py
cd apps/web && npm install && npm run dev
```

管理端：`http://127.0.0.1:5173/?client=admin`（文档有效期、强条审核、评估看板、trace）。`PATCH` 后下一问立即读 DB 新值。同一 dist：

```text
http://127.0.0.1:8000/?client=electron
http://127.0.0.1:8000/?client=tauri
cd apps/electron && npm start
python scripts/desktop_probe.py
```

Electron 图集未入库 → 条文号/扫描页。Tauri 交底草稿带 citations 与强条头。本机无 rustc 时不编造 Tauri 原生 RSS，见 `docs/desktop-compare.md`。

```text
python scripts/run_gateway.py
cd apps/flutter_site
flutter test
flutter run -d windows --dart-define=GATEWAY=http://127.0.0.1:8000
```

工地端：先点同步 `GET /v1/sync/mandatory`，再飞行模式下查 `8.5.1`（743 指针，不编 50010 原文）。Android 模拟器把 GATEWAY 设为 `http://10.0.2.2:8000`。
