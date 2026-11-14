import { spawnSync } from "node:child_process";
import { existsSync, statSync, unlinkSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve, join } from "node:path";

const root = resolve(import.meta.dirname, "..");
const assets = join(root, "assets");

const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find(existsSync);

const cards = [
  { html: "status.html", file: "status.png", w: 1080, h: 1920 },
  { html: "share.html", file: "share.png", w: 1080, h: 1080 },
];

for (const { html, file, w, h } of cards) {
  const out = join(root, file);
  if (existsSync(out)) unlinkSync(out);
  const res = spawnSync(chrome, [
    "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
    "--no-default-browser-check", "--force-device-scale-factor=1",
    `--window-size=${w},${h}`, "--virtual-time-budget=5000",
    `--screenshot=${out}`, pathToFileURL(join(assets, html)).href,
  ], { encoding: "utf8", timeout: 60000 });
  if (!existsSync(out)) {
    console.error(`${file} failed\n${res.stderr || res.stdout}`);
    process.exitCode = 1;
  } else {
    console.log(`${file} (${w} x ${h}) -> ${(statSync(out).size / 1024).toFixed(0)} KB`);
  }
}
