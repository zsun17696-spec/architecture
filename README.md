# architecture

课设：建筑 · 工程规范图集知识库（GB 55008 扫描页定位 + GB 50010-2010 强条指针）。

- 需求：`tasks/prd-code-atlas-kb.md`
- 设计：`tasks/spec-code-atlas-kb.md`
- 任务卡：`tasks/issues-code-atlas-kb.md`
- 语料体检：`python scripts/preflight_corpus.py` → `data/raw/_corpus_report.md`

实现按 Issues I-01 → I-08。未配置 LLM 时抽取式作答。不入库实验用 `data/raw/*.md`。
