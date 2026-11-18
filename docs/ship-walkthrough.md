# 终验走查与答辩口径

产品：**矩典 SpecGate**。故事是版本闸门 + 引用完整性，不是迷你建标库。

黄金集权威：`eval/golden_set_20.json`。8.5.1 是最小配筋率，不是保护层（保护层在 8.2 节，G15 未锁定）。

---

## 0. 一键自检（答辩前 5 分钟）

```text
python -m pip install -r backend/requirements.txt
python scripts/preflight_corpus.py
python scripts/ingest.py
python scripts/e2e.py --reset
python eval/run_eval.py
python -m pytest tests -q
```

通过标准：E2E PASS；`eval/_eval_report.md` 写明「趋势参考，n=7，不对标作业 0.85」；缺 PDF 时 ingest 打印 `MISSING_PDF: GB 55008-2021`。

然后：

```text
python scripts/run_gateway.py
```

浏览器：`http://127.0.0.1:8000/?client=admin`（已 build 的 `apps/web/dist`）。热更新则 `cd apps/web && npm run dev` → `:5173`。

---

## 1. 现场 12 分钟脚本

| 分 | 动作 | 必须看见 |
|----|------|----------|
| 1 | 打开 `_corpus_report.md` 第 5、6 行 | #5 scan-page-locate、usable_chars=0；#6 provenance-only OLE。实验 md 不在 manifest |
| 2 | 管理端 P-2018 问「纵向受力钢筋最小配筋率的强制性条文是哪一条」 | 第一行 `⚠ 强制性条文`；引用 GB 50010 / 2010 / **8.5.1**；指针 text 含 743 号，无「条款正文」 |
| 3 | 同一问切 P-2024 | 无 50010 指针；有 GB 55008 扫描页；不编条文号；出处 167 号 |
| 4 | 文档有效期：把 50010 指针 `valid_to` 改成 `2017-12-31`，再问 P-2018 | 下一问立刻按新区间过滤。演示完改回 `2099-12-31` |
| 5 | `?client=electron` 查 8.5.1；图号栏填乱码 | 「图集未入库」；不编 fig_no |
| 6 | `?client=tauri` 生成交底 | 稿首强条头；底部 citations |
| 7 | Flutter：先同步，再飞行模式查 8.5.1 | 本地 SQLite；743 废止说明；在线仍 `client=flutter` 打 `/v1/ask` |

不要演示：从扫描 PDF 抽出的「第 x.x.x 条正文」；把 743 与 167 写成同一来源；把 8.5.1 说成保护层。

---

## 2. 答辩三句话

1. **语料**：55008 是扫描页定位（首都之窗 167 附件）；50010 全书未收，只用住建部公告 743 的 14 个真实条文号做指针。
2. **闸门**：`valid_to=2099`，强条废止日 `mandatory_abolished_from=2022-04-01`。`latest_eligible` 且合同日 ≥ 该日则丢掉 pointer；`all_eligible` 两套 std_code 并列。
3. **引用**：cite ⊆ 本轮 chunk_id；99.9.9 进 `dropped_citation`；无 Key 则 extractive。

检索通道：**jieba BM25 + 字符 3-gram TF-IDF**，不要说「语义向量」。

---

## 3. 指标怎么报

- 入库完整性：14/14 指针在 SQLite（不是 golden Recall）。
- Golden Recall@5：**n=7**（G01/G02/G03/G08/G09/G11/G14），本机最近一次见 `eval/_eval_report.md`。只报趋势，不与作业 0.85 对标。
- G17 版本闸门、G18 假引用单列。

---

## 4. 已知缺口（主动说）

- 无授权图集页 → G19 未锁定；Electron 降级为条文/页定位。
- 无 50010 摘录 → G15/G16 未锁定；保护层不得答 8.5.1。
- 本机无 rustc → Tauri 原生 RSS 为 n/a，同一 dist 用 `?client=tauri` 演示（`docs/desktop-compare.md`）。
- LLM Key 可选；当前全程 extractive。

---

## 5. GitHub

远程约定：`git@github.com:zsun17696-spec/architecture.git`。本 walkthrough **不自动 commit/push**。需要入库时再说「提交并 push」。
