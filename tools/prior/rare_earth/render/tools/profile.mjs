// Per-frame timing: render vs screenshot, for a handful of representative times.
import { chromium } from 'playwright-core';
import { serve } from './serve.mjs';
const W = Number(process.argv[2] || 960), H = Math.round(W * 9 / 16);
const server = await serve(8791);
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: W, height: H } });
await p.goto(`http://127.0.0.1:8791/index.html?w=${W}&h=${H}`); await p.evaluate(() => window.__ready);
for (const t of [1.0, 7.2, 9.8, 22.6, 45.5, 50.3, 62.0, 76.0, 100.2, 118.0]) {
  const t0 = Date.now(); await p.evaluate((tt) => window.renderAt(tt), t); const t1 = Date.now();
  await p.screenshot({ type: 'jpeg', quality: 88 }); const t2 = Date.now();
  await p.evaluate((tt) => window.renderAt(tt), t + 1 / 24); const t3 = Date.now();
  console.log(t.toFixed(1), 'render', t1 - t0, 'ms  shot', t2 - t1, 'ms  next-frame', t3 - t2, 'ms');
}
await b.close(); server.close();
