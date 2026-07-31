import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const siteRoot = new URL("../", import.meta.url);

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the public telemetry dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /FFXI Telemetry — Autonomy, measured/);
  assert.match(html, /Autonomy,/);
  assert.match(html, /measured\./);
  assert.match(html, /1,245/);
  assert.match(html, /47,094/);
  assert.match(html, /EXP and gil, normalized by active time/);
  assert.match(html, /Current (?:<!-- -->)?hour(?:<!-- -->)? EXP\/hour/);
  assert.match(
    html,
    /Completed (?:<!-- -->)?hour(?:<!-- -->)?s/,
  );
  assert.match(html, /No raw payloads, agent IDs, lease IDs/);
  assert.match(html, /Twenty legends\./);
  assert.match(html, /Jaggedy-Eared Jack/);
  assert.match(html, /Charybdis/);
  assert.match(html, /Swipe, scroll, or use arrow keys/);
  assert.match(html, /og:image/);
  assert.match(html, /\/og-v2\.png/);
  assert.doesNotMatch(html, /codex-preview/);
  assert.doesNotMatch(html, /OpenAI Sites Starter/);
});

test("source contains only the finished dashboard experience", async () => {
  const [layout, page, css, liveConfig, nmCarousel, nmCatalog, packageJson, hostingJson] = await Promise.all([
    readFile(new URL("app/layout.tsx", siteRoot), "utf8"),
    readFile(new URL("app/page.tsx", siteRoot), "utf8"),
    readFile(new URL("app/globals.css", siteRoot), "utf8"),
    readFile(new URL("app/live-config.ts", siteRoot), "utf8"),
    readFile(new URL("app/nm-carousel.tsx", siteRoot), "utf8"),
    readFile(new URL("public/data/nm_catalog.json", siteRoot), "utf8"),
    readFile(new URL("package.json", siteRoot), "utf8"),
    readFile(new URL(".openai/hosting.json", siteRoot), "utf8"),
  ]);

  assert.match(layout, /generateMetadata/);
  assert.match(layout, /\/og-v2\.png/);
  assert.match(page, /const qualityRows/);
  assert.match(page, /ProgressionRatePanel/);
  assert.match(page, /Hourly refresh/);
  assert.match(page, /initialProgressionSnapshot/);
  assert.match(page, /NmCarousel/);
  assert.match(page, /No raw payloads, agent IDs, lease IDs/);
  assert.match(page, /Historical Git attribution is inferred/);
  assert.match(css, /--ink:/);
  assert.match(css, /scroll-snap-type: x mandatory/);
  assert.match(nmCarousel, /Next notorious monster/);
  assert.equal(JSON.parse(nmCatalog).nms.length, 20);
  assert.match(liveConfig, /https:\/\/.*\.public\.blob\.vercel-storage\.com/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(
    hostingJson,
    /appgprj_6a6b7b1c80c0819197f7321013484605/,
  );

  await access(new URL("public/og-v2.png", siteRoot));
});
