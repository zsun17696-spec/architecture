# Desktop compare (Electron vs Tauri2)

Measured: 2026-11-18 11:18 UTC. Same Vue dist: `apps/web/dist` served by FastAPI `/?client=`.

| shell | client | startup_ms | rss_mb | notes |
|-------|--------|------------|--------|-------|
| electron | electron | 1168 | 126.4 | http://127.0.0.1:8000/?client=electron |
| electron | tauri | 931 | 128.2 | http://127.0.0.1:8000/?client=tauri |
| tauri2-native | tauri | n/a | n/a | rustc missing; conf at apps/tauri-handover/src-tauri |

- Gateway `http://127.0.0.1:8000` reachable: **True**.
- rustc/cargo present: **False**. This machine cannot build native Tauri2 until Rust is installed.
- Electron loads the **same** SPA as Tauri (`apps/web/dist`). Atlas missing → 条文号/扫描页, never invent `fig_no`.
- Tauri mode is `http://127.0.0.1:8000/?client=tauri` (handover draft + citations). Native binary: `apps/tauri-handover`.
- FR-24: fill native Tauri RSS after `cargo tauri build`; until then SPA row is the demo path (SPEC: npm/dev same SPA).
