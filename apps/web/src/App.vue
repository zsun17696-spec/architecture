<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api, ensureClientParam, pageSrc, readClient, type Client } from "./api";

type Tab = "ask" | "docs" | "review" | "eval" | "trace" | "atlas" | "handover";

const client = ref<Client>(readClient());
const tab = ref<Tab>("ask");
const err = ref("");
const busy = ref(false);
const health = ref({ ok: false, chunks: 0 });

const projects = ref<Record<string, unknown>[]>([]);
const documents = ref<Record<string, unknown>[]>([]);
const pointers = ref<Record<string, unknown>[]>([]);
const reviews = ref<Record<string, unknown>[]>([]);
const traces = ref<Record<string, unknown>[]>([]);
const evalJson = ref<Record<string, unknown> | null>(null);

const ask = reactive({
  project_id: "P-2018",
  query: "纵向受力钢筋最小配筋率的强制性条文是哪一条",
  answer: "",
  citations: [] as Record<string, unknown>[],
  dropped: [] as Record<string, unknown>[],
  trace_id: "",
  mandatory_hit: false,
});

const edit = reactive<Record<string, { valid_from: string; valid_to: string; status: string }>>({});

const locate = reactive({
  q: "8.5.1",
  fig: "",
  hit: null as Record<string, unknown> | null,
  img: "",
  note: "",
});

const handover = reactive({
  part: "主体结构 / 钢筋工程 / 最小配筋率交底",
  project_id: "P-2018",
  draft: "",
  open: null as Record<string, unknown> | null,
});

const isAdmin = computed(() => client.value === "admin");
const isElectron = computed(() => client.value === "electron");
const isTauri = computed(() => client.value === "tauri");

async function loadCore() {
  err.value = "";
  health.value = await api.health();
  projects.value = await api.projects();
  documents.value = await api.documents();
  for (const d of documents.value) {
    const id = String(d.id);
    edit[id] = {
      valid_from: String(d.valid_from || ""),
      valid_to: String(d.valid_to || ""),
      status: String(d.status || "active"),
    };
  }
}

async function loadReview() {
  pointers.value = await api.chunks("?kind=pointer");
  reviews.value = await api.reviews();
}

async function loadEval() {
  try {
    evalJson.value = await api.evalLatest();
  } catch (e) {
    evalJson.value = null;
    err.value = String(e);
  }
}

async function loadTraces() {
  traces.value = await api.traces();
}

onMounted(async () => {
  ensureClientParam(client.value);
  if (isElectron.value) tab.value = "atlas";
  if (isTauri.value) tab.value = "handover";
  try {
    await loadCore();
    if (isAdmin.value) {
      await loadReview();
      await loadTraces();
      try {
        await loadEval();
        err.value = "";
      } catch {
        /* eval optional */
      }
    }
  } catch (e) {
    err.value = String(e);
  }
});

async function doAsk() {
  busy.value = true;
  err.value = "";
  try {
    const data = await api.ask({
      query: ask.query,
      project_id: ask.project_id,
      client: client.value,
    });
    ask.answer = String(data.answer || "");
    ask.citations = (data.citations as Record<string, unknown>[]) || [];
    ask.dropped = (data.dropped_citation as Record<string, unknown>[]) || [];
    ask.trace_id = String(data.trace_id || "");
    ask.mandatory_hit = Boolean(data.mandatory_hit);
    if (isAdmin.value) await loadTraces();
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function saveDoc(id: string) {
  busy.value = true;
  err.value = "";
  try {
    await api.patchDocument(id, edit[id]);
    await loadCore();
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function toggleMandatory(row: Record<string, unknown>, on: boolean) {
  busy.value = true;
  err.value = "";
  try {
    await api.patchMandatory(Number(row.id), { mandatory: on, note: on ? "审核恢复" : "管理端关闭强条标记" });
    await loadReview();
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function doLocate() {
  busy.value = true;
  err.value = "";
  locate.hit = null;
  locate.img = "";
  locate.note = "";
  try {
    if (locate.fig.trim()) {
      locate.note = "图集未入库：不编造图号。请改用条文号（如 8.5.1）或 GB 55008 扫描页码。";
      return;
    }
    const q = locate.q.trim();
    if (/^\d+$/.test(q)) {
      const pages = await api.chunks("?kind=page");
      const hit = pages.find((p) => Number(p.page) === Number(q));
      if (!hit) {
        locate.note = `没有扫描页 p${q}`;
        return;
      }
      locate.hit = hit;
      locate.img = pageSrc(String(hit.doc_id), Number(hit.page));
      locate.note = "按扫描页定位（GB 55008-2021，公告 167 号）。无条文号。";
      return;
    }
    const ptrs = await api.chunks("?kind=pointer");
    const hit = ptrs.find((p) => String(p.article_no) === q);
    if (!hit) {
      locate.note = `仓库没有条文号 ${q}（仅 743 号 14 条指针 + 扫描页）`;
      return;
    }
    locate.hit = hit;
    locate.note = "指针定位，正文来自 chapter_hint + 743 号废止说明，不是 50010 条款原文。";
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function doHandover() {
  busy.value = true;
  err.value = "";
  try {
    const data = await api.ask({
      query: handover.part,
      project_id: handover.project_id,
      client: "tauri",
    });
    ask.citations = (data.citations as Record<string, unknown>[]) || [];
    ask.mandatory_hit = Boolean(data.mandatory_hit);
    const cites = ask.citations
      .map((c) => `- ${c.std_code} ${c.version} ${c.article_no || "p" + c.page} (chunk ${c.chunk_id})`)
      .join("\n");
    const head = ask.mandatory_hit ? "⚠ 强制性条文\n\n" : "";
    handover.draft =
      head +
      `# 技术交底草稿\n分部分项：${handover.part}\n项目：${handover.project_id}\n\n` +
      String(data.answer || "") +
      "\n\n## 引用\n" +
      cites;
    ask.answer = String(data.answer || "");
    ask.trace_id = String(data.trace_id || "");
  } catch (e) {
    err.value = String(e);
  } finally {
    busy.value = false;
  }
}

async function openCite(c: Record<string, unknown>) {
  handover.open = await api.chunk(Number(c.chunk_id));
}

function exportDraft(kind: "md" | "txt") {
  const blob = new Blob([handover.draft], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = kind === "md" ? "handover.md" : "handover.txt";
  a.click();
}

function setTab(name: Tab) {
  tab.value = name;
  err.value = "";
  if (name === "eval") loadEval().catch((e) => (err.value = String(e)));
  if (name === "trace") loadTraces().catch((e) => (err.value = String(e)));
  if (name === "review") loadReview().catch((e) => (err.value = String(e)));
}
</script>

<template>
  <div class="shell">
    <header class="top">
      <div>
        <p class="kicker">混凝土结构 · 版本闸门</p>
        <h1>矩典 SpecGate</h1>
      </div>
      <div class="meta">
        <span class="chip">client={{ client }}</span>
        <span class="chip">chunks {{ health.chunks }}</span>
        <span class="chip warn" v-if="ask.mandatory_hit">⚠ 强制性条文</span>
      </div>
    </header>

    <p class="banner" v-if="isElectron">图集未入库。按条文号或 GB 55008 扫描页定位，不编图号。</p>
    <p class="banner" v-else-if="isTauri">交底工作台：同一 /v1/ask，稿件带 citations；命中强条则稿首 ⚠ 强制性条文。</p>
    <p class="banner" v-else-if="!isAdmin">
      当前壳为 {{ client }}。管理功能请打开 <code>?client=admin</code>
    </p>

    <nav class="tabs">
      <button :class="tab === 'ask' ? '' : 'ghost'" type="button" @click="setTab('ask')">问答</button>
      <button v-if="isElectron" :class="tab === 'atlas' ? '' : 'ghost'" type="button" @click="setTab('atlas')">条文/页定位</button>
      <button v-if="isTauri" :class="tab === 'handover' ? '' : 'ghost'" type="button" @click="setTab('handover')">交底草稿</button>
      <button v-if="isAdmin" :class="tab === 'docs' ? '' : 'ghost'" type="button" @click="setTab('docs')">文档有效期</button>
      <button v-if="isAdmin" :class="tab === 'review' ? '' : 'ghost'" type="button" @click="setTab('review')">强条审核</button>
      <button v-if="isAdmin" :class="tab === 'eval' ? '' : 'ghost'" type="button" @click="setTab('eval')">评估看板</button>
      <button v-if="isAdmin" :class="tab === 'trace' ? '' : 'ghost'" type="button" @click="setTab('trace')">Trace</button>
    </nav>

    <p class="err" v-if="err">{{ err }}</p>

    <section v-if="tab === 'ask'" class="panel">
      <div class="row">
        <label>项目
          <select v-model="ask.project_id">
            <option v-for="p in projects" :key="String(p.id)" :value="String(p.id)">
              {{ p.id }} · {{ p.contract_date }} · {{ p.version_policy }}
            </option>
          </select>
        </label>
        <button type="button" :disabled="busy" @click="doAsk">提问</button>
      </div>
      <textarea v-model="ask.query" rows="3" />
      <article class="answer" v-if="ask.answer">
        <p class="seal" v-if="ask.mandatory_hit">⚠ 强制性条文</p>
        <pre>{{ ask.answer }}</pre>
      </article>
      <p class="muted" v-if="ask.trace_id">trace {{ ask.trace_id }}</p>
      <h3>本轮引用</h3>
      <table>
        <thead>
          <tr><th>条文/页</th><th>标准</th><th>kind</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in ask.citations" :key="String(c.chunk_id)">
            <td>{{ c.article_no || ("p" + c.page) }}</td>
            <td>{{ c.std_code }}-{{ c.version }}</td>
            <td>{{ c.kind }}</td>
          </tr>
        </tbody>
      </table>
      <p class="muted" v-if="ask.dropped.length">dropped {{ ask.dropped.length }}</p>
    </section>

    <section v-if="isElectron && tab === 'atlas'" class="panel">
      <p class="hint">有授权图集页后才抄真实图号。现在输入图号只会提示未入库。</p>
      <div class="row">
        <label>条文号或扫描页码
          <input v-model="locate.q" placeholder="8.5.1 或 3" />
        </label>
        <label>图号（无库）
          <input v-model="locate.fig" placeholder="不要编造" />
        </label>
        <button type="button" :disabled="busy" @click="doLocate">定位</button>
      </div>
      <p class="seal" v-if="locate.note">{{ locate.note }}</p>
      <pre v-if="locate.hit">{{ locate.hit.text }}</pre>
      <p class="muted" v-if="locate.hit">{{ locate.hit.std_code }} {{ locate.hit.article_no || ("p" + locate.hit.page) }} · 不编 fig_no</p>
      <img v-if="locate.img" class="scan" :src="locate.img" alt="GB 55008 scan page" />
    </section>

    <section v-if="isTauri && tab === 'handover'" class="panel">
      <div class="row">
        <label>项目
          <select v-model="handover.project_id">
            <option v-for="p in projects" :key="String(p.id)" :value="String(p.id)">{{ p.id }}</option>
          </select>
        </label>
        <button type="button" :disabled="busy" @click="doHandover">生成交底</button>
        <button class="ghost" type="button" :disabled="!handover.draft" @click="exportDraft('md')">导出 Markdown</button>
        <button class="ghost" type="button" :disabled="!handover.draft" @click="exportDraft('txt')">导出纯文本</button>
      </div>
      <textarea v-model="handover.part" rows="2" />
      <article class="answer" v-if="handover.draft">
        <pre>{{ handover.draft }}</pre>
      </article>
      <h3>点击引用打开 chunk</h3>
      <ul>
        <li v-for="c in ask.citations" :key="String(c.chunk_id)">
          <button class="ghost" type="button" @click="openCite(c)">
            {{ c.std_code }} {{ c.version }} {{ c.article_no || ("p" + c.page) }}
          </button>
        </li>
      </ul>
      <pre v-if="handover.open">{{ handover.open.text }}</pre>
    </section>

    <section v-if="isAdmin && tab === 'docs'" class="panel">
      <p class="hint">PATCH 写库即生效，不重建索引。下一问按新 valid_from / valid_to 过滤。</p>
      <table>
        <thead>
          <tr><th>文档</th><th>valid_from</th><th>valid_to</th><th>status</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="d in documents" :key="String(d.id)">
            <td>
              <strong>{{ d.id }}</strong>
              <div class="muted">{{ d.std_code }} {{ d.version }} · {{ d.kind }}</div>
            </td>
            <td><input v-model="edit[String(d.id)].valid_from" /></td>
            <td><input v-model="edit[String(d.id)].valid_to" /></td>
            <td>
              <select v-model="edit[String(d.id)].status">
                <option value="active">active</option>
                <option value="abolished">abolished</option>
              </select>
            </td>
            <td><button type="button" :disabled="busy" @click="saveDoc(String(d.id))">保存</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="isAdmin && tab === 'review'" class="panel">
      <p class="hint">743 号 14 条指针。关闭 mandatory 后，下一问不再按强制通道加权。不编 50010 正文。</p>
      <table>
        <thead>
          <tr><th>条文</th><th>chapter_hint</th><th>mandatory</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="c in pointers" :key="String(c.id)">
            <td>{{ c.article_no }}</td>
            <td>{{ c.chapter_title }}</td>
            <td>{{ c.mandatory }}</td>
            <td>
              <button v-if="c.mandatory" class="danger" type="button" :disabled="busy" @click="toggleMandatory(c, false)">关闭</button>
              <button v-else type="button" :disabled="busy" @click="toggleMandatory(c, true)">恢复</button>
            </td>
          </tr>
        </tbody>
      </table>
      <h3>审核日志</h3>
      <ul class="log">
        <li v-for="r in reviews" :key="String(r.id)">#{{ r.chunk_id }} {{ r.action }} {{ r.note }} · {{ r.created_at }}</li>
      </ul>
    </section>

    <section v-if="isAdmin && tab === 'eval'" class="panel">
      <p v-if="!evalJson">还没有评估文件。先跑 <code>python eval/run_eval.py</code>。</p>
      <template v-else>
        <p class="seal">{{ evalJson.disclaimer }}</p>
        <p>Recall@5 = {{ evalJson.recall_hits }}/{{ evalJson.recall_n }} = {{ evalJson.recall_at_5 }}</p>
        <table>
          <thead><tr><th>id</th><th>ok</th><th>expect</th></tr></thead>
          <tbody>
            <tr v-for="row in (evalJson.recall_items as Record<string, unknown>[])" :key="String(row.id)">
              <td>{{ row.id }}</td>
              <td>{{ row.ok }}</td>
              <td>{{ (row.expect as string[]).join(", ") }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </section>

    <section v-if="isAdmin && tab === 'trace'" class="panel">
      <table>
        <thead><tr><th>时间</th><th>query</th><th>id</th></tr></thead>
        <tbody>
          <tr v-for="t in traces" :key="String(t.id)">
            <td>{{ t.created_at }}</td>
            <td>{{ (t.payload as Record<string, unknown>)?.query }}</td>
            <td class="mono">{{ t.id }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.shell { max-width: 1080px; margin: 0 auto; padding: 1.5rem 1.2rem 3rem; }
.top { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-end; }
h1 { font-family: var(--display); margin: 0; letter-spacing: 0.08em; font-size: 1.85rem; }
.kicker { margin: 0; color: var(--gold); letter-spacing: 0.24em; font-size: 0.72rem; text-transform: uppercase; }
.meta { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.chip { border: 1px solid var(--line); padding: 0.2rem 0.5rem; border-radius: 99px; font-size: 12px; color: var(--muted); }
.chip.warn { border-color: var(--seal); color: #ffb4ac; }
.tabs { display: flex; gap: 0.4rem; margin: 1.2rem 0 0.8rem; flex-wrap: wrap; }
.panel { background: var(--bg-2); border: 1px solid var(--line); border-radius: 10px; padding: 1rem; }
.row { display: flex; gap: 0.6rem; align-items: end; margin-bottom: 0.6rem; flex-wrap: wrap; }
.row label { flex: 1; display: flex; flex-direction: column; gap: 0.25rem; font-size: 12px; color: var(--muted); }
textarea { width: 100%; min-height: 4.5rem; }
.answer { margin-top: 0.8rem; background: #0c0b09; border-left: 3px solid var(--gold); padding: 0.7rem 0.9rem; }
.answer pre, pre { white-space: pre-wrap; margin: 0.4rem 0 0; font-family: var(--font); line-height: 1.55; }
.seal { color: #ffb4ac; font-weight: 700; }
.muted { color: var(--muted); font-size: 12px; }
.hint { color: var(--muted); }
.err { color: #ffb4ac; }
.banner { border: 1px dashed var(--gold); padding: 0.6rem 0.8rem; color: var(--gold); }
.log { font-size: 12px; color: var(--muted); }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 11px; }
h3 { font-size: 0.95rem; margin: 1rem 0 0.4rem; }
code { color: var(--gold); }
.scan { max-width: 100%; margin-top: 0.8rem; border: 1px solid var(--line); }
</style>
