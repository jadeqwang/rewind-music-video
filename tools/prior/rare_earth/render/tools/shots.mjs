// Print the edit's shot table (id, t0, t1, scene) as JSON, for re-rendering selected shots.
//   node tools/shots.mjs > /tmp/work/shots.json
import { chromium } from 'playwright-core';
import { serve } from './serve.mjs';

const PORT = 8900 + Math.floor(Math.random() * 90);
const server = await serve(PORT);
const browser = await chromium.launch({
  executablePath: process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
try {
  const page = await browser.newPage({ viewport: { width: 480, height: 270 } });
  await page.goto(`http://127.0.0.1:${PORT}/index.html?w=480&h=270`);
  await page.waitForFunction(() => window.__ready !== undefined, null, { timeout: 60000 });
  await page.evaluate(() => window.__ready);
  console.log(JSON.stringify(await page.evaluate(() => window.__shots)));
} finally {
  await browser.close();
  server.close();
}
