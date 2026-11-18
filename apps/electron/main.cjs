const { app, BrowserWindow } = require("electron");

const GATEWAY = process.env.SPECGATE_URL || "http://127.0.0.1:8000";
const CLIENT = process.env.SPECGATE_CLIENT || "electron";
const t0 = Date.now();

async function run() {
  const win = new BrowserWindow({
    width: 1100,
    height: 780,
    show: process.env.SPECGATE_HEADLESS !== "1",
    webPreferences: { sandbox: true },
  });
  const url = `${GATEWAY}/?client=${CLIENT}`;
  await win.loadURL(url);
  const rss = process.memoryUsage().rss;
  const payload = {
    client: CLIENT,
    shell: "electron",
    url,
    startup_ms: Date.now() - t0,
    rss_mb: Math.round((rss / (1024 * 1024)) * 10) / 10,
  };
  console.log(JSON.stringify(payload));
  if (process.env.SPECGATE_HEADLESS === "1") {
    app.quit();
  }
}

app.whenReady().then(run);
app.on("window-all-closed", () => app.quit());
