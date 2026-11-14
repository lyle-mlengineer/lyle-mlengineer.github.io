import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const here = import.meta.dirname;
const root = resolve(here, "..");
const html = pathToFileURL(join(here, "video.html")).href;
const frameDir = join(here, "frames");
const out = join(root, "launch-video.mp4");
const W = 1080, H = 1080, FPS = 30, DUR = 15;

const chromePath = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find(existsSync);

rmSync(frameDir, { recursive: true, force: true });
mkdirSync(frameDir, { recursive: true });

const port = 9344;
const profile = "C:/Users/Lyle/AppData/Local/Temp/opencode/chrome-video-profile-2";
const chrome = spawn(chromePath, [
  "--headless=new",
  "--disable-gpu",
  "--hide-scrollbars",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--mute-audio",
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${profile}`,
  `--window-size=${W},${H}`,
  "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function version() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) return r.json();
    } catch {}
    await sleep(250);
  }
  throw new Error("Chrome debugging endpoint never came up");
}

let nextId = 1;
const pending = new Map();

function connect(url) {
  const ws = new WebSocket(url);
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(`${msg.error.message} (${msg.error.code})`));
      else resolve(msg.result ?? {});
    }
  });
  return new Promise((res, rej) => {
    ws.addEventListener("open", () => res(ws), { once: true });
    ws.addEventListener("error", rej, { once: true });
  });
}

function send(ws, method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
}

try {
  const v = await version();
  const ws = await connect(v.webSocketDebuggerUrl);

  const { targetId } = await send(ws, "Target.createTarget", { url: "about:blank" });
  const { sessionId } = await send(ws, "Target.attachToTarget", { targetId, flatten: true });
  const s = (m, p) => send(ws, m, p, sessionId);

  await s("Page.enable");
  await s("Runtime.enable");
  await s("Emulation.setDeviceMetricsOverride", {
    width: W, height: H, deviceScaleFactor: 1, mobile: false,
  });
  await s("Page.navigate", { url: html });

  // wait for load + images
  for (let i = 0; i < 60; i++) {
    try {
      const r = await s("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (r.result?.value === "complete") break;
    } catch {}
    await sleep(200);
  }
  await s("Runtime.evaluate", {
    expression: `Promise.all([...document.images].map(img => img.complete ? true : new Promise(r => { img.onload = r; img.onerror = r; }))).then(() => true)`,
    awaitPromise: true,
  });
  await s("Runtime.evaluate", {
    expression: `document.fonts ? document.fonts.ready.then(() => true) : true`,
    awaitPromise: true,
  });
  await sleep(400);

  const total = Math.round(DUR * FPS);
  const started = Date.now();

  for (let f = 0; f < total; f++) {
    const t = f / FPS;
    await s("Runtime.evaluate", { expression: `window.renderAt(${t.toFixed(4)})` });
    const shot = await s("Page.captureScreenshot", {
      format: "jpeg",
      quality: 95,
      fromSurface: true,
      captureBeyondViewport: false,
    });
    writeFileSync(join(frameDir, `f_${String(f).padStart(4, "0")}.jpg`), Buffer.from(shot.data, "base64"));
    if (f % 90 === 0) {
      process.stdout.write(`  frame ${f}/${total}  (${((Date.now() - started) / 1000).toFixed(1)}s)\n`);
    }
  }

  await send(ws, "Target.closeTarget", { targetId });
  ws.close();
  console.log(`captured ${total} frames in ${((Date.now() - started) / 1000).toFixed(1)}s`);
} finally {
  if (process.platform === "win32") {
    spawn("taskkill", ["/PID", String(chrome.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    chrome.kill();
  }
}

const ff = spawn("ffmpeg", [
  "-y",
  "-framerate", String(FPS),
  "-i", join(frameDir, "f_%04d.jpg"),
  "-c:v", "libx264",
  "-preset", "slow",
  "-crf", "17",
  "-pix_fmt", "yuv420p",
  "-movflags", "+faststart",
  "-r", String(FPS),
  out,
], { stdio: ["ignore", "inherit", "inherit"] });

const code = await new Promise((r) => ff.on("close", r));
if (code !== 0) throw new Error("ffmpeg failed with code " + code);

rmSync(frameDir, { recursive: true, force: true });
console.log("video ->", out);
