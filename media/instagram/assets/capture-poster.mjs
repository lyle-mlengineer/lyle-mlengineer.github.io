import { spawnSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const here = import.meta.dirname;
const root = resolve(here, "..");
const html = pathToFileURL(join(here, "reel.html")).href;
const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find(existsSync);

const t = Number(process.argv[2] ?? 17.4);
const out = join(root, "reel-poster.png");
spawnSync(chrome, [
  "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
  "--force-device-scale-factor=1", "--window-size=1080,1920",
  "--virtual-time-budget=3000", `--screenshot=${out}`, `${html}?t=${t}`,
], { encoding: "utf8", timeout: 60000 });
console.log(out, existsSync(out) ? `${(statSync(out).size / 1024).toFixed(0)} KB` : "FAILED");
