import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, statSync, unlinkSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve, join } from "node:path";

const root = resolve(import.meta.dirname, "..");
const html = pathToFileURL(join(root, "assets", "cards.html")).href;
const outDir = root;

const chrome = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
].find(existsSync);

const cards = [
  { n: 1, file: "01-announcement.png" },
  { n: 2, file: "02-what-i-build.png" },
  { n: 3, file: "03-selected-work.png" },
  { n: 4, file: "04-proof.png" },
];

for (const { n, file } of cards) {
  const out = join(outDir, file);
  if (existsSync(out)) unlinkSync(out);
  const res = spawnSync(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      "--force-device-scale-factor=1",
      "--window-size=1200,1200",
      "--virtual-time-budget=5000",
      `--screenshot=${out}`,
      `${html}?card=${n}`,
    ],
    { encoding: "utf8", timeout: 60000 }
  );
  if (!existsSync(out)) {
    console.error(`card ${n} failed\n${res.stderr || res.stdout}`);
    process.exitCode = 1;
  } else {
    console.log(`card ${n} -> ${file} (${(statSync(out).size / 1024).toFixed(0)} KB)`);
  }
}
