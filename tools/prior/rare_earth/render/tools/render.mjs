// Frame-accurate capture of the renderer with headless Chromium.
//   node tools/render.mjs --stills 3.2,10,22.5 --w 960 --h 540 --outdir /tmp/work/stills
//   node tools/render.mjs --from 0 --to 128 --fps 24 --w 1920 --h 1080 --jobs 2 --out out/rare_earth.mp4
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { serve } from './serve.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : '1']);
  return acc;
}, []));
const W = Number(args.w || 1920), H = Number(args.h || 1080);
const FPS = Number(args.fps || 24);
const JOBS = Number(args.jobs || 1);
const PORT = 8800 + Math.floor(Math.random() * 100);
const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(`http://127.0.0.1:${PORT}/index.html?w=${W}&h=${H}`);
  await page.waitForFunction(() => window.__ready !== undefined, null, { timeout: 60000 });
  await page.evaluate(() => window.__ready);
  return page;
}

async function shoot(page, t, file) {
  await page.evaluate((tt) => window.renderAt(tt), t);
  await page.screenshot({ path: file, type: 'jpeg', quality: Number(args.q || 94), clip: { x: 0, y: 0, width: W, height: H } });
}

const server = await serve(PORT);
const launch = () => chromium.launch({
  executablePath: CHROME,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-web-security'],
});
const browser = await launch();
const extraBrowsers = [];

try {
  if (args.stills) {
    const outdir = args.outdir || '/tmp/work/stills';
    fs.mkdirSync(outdir, { recursive: true });
    const page = await openPage(browser);
    const times = args.stills.split(',').map(Number);
    for (const t of times) {
      const f = path.join(outdir, `s_${t.toFixed(3).padStart(8, '0')}.jpg`);
      const t0 = Date.now();
      await shoot(page, t, f);
      console.log(`still ${t.toFixed(3)} -> ${f} (${Date.now() - t0} ms)`);
    }
  } else {
    const from = Number(args.from || 0), to = Number(args.to || 128);
    const out = args.out || '/tmp/work/out.mp4';
    const frameDir = args.framedir || `/tmp/work/frames_${Date.now()}`;
    fs.mkdirSync(frameDir, { recursive: true });
    const n = Math.round((to - from) * FPS);
    // one browser process per job: SwiftShader rasterizes in the GPU process, so pages in one browser contend
    const browsers = [browser];
    for (let j = 1; j < JOBS; j++) { const b = await launch(); browsers.push(b); extraBrowsers.push(b); }
    const pages = await Promise.all(browsers.map((b) => openPage(b)));
    const t0 = Date.now();
    let done = 0;
    await Promise.all(pages.map(async (page, j) => {
      for (let i = j; i < n; i += JOBS) {
        const f = path.join(frameDir, `f_${String(i).padStart(5, '0')}.jpg`);
        if (args.resume && fs.existsSync(f)) { done++; continue; }
        await shoot(page, from + i / FPS, f);
        done++;
        if (done % 48 === 0) {
          const el = (Date.now() - t0) / 1000;
          console.log(`${done}/${n} frames  ${(el / done).toFixed(2)} s/frame  eta ${((n - done) * el / done / 60).toFixed(1)} min`);
        }
      }
    }));
    // --audio: the mix to mux (default: the song; the release uses the song + sound-design layer, which runs past the last note)
    const audio = args.audio || path.resolve('..', 'audio', 'Rare_Earth_DDR.mp3');
    const venc = args.bitrate
      ? ['-b:v', args.bitrate, '-maxrate', args.maxrate || args.bitrate, '-bufsize', args.bufsize || '16M']
      : ['-crf', args.crf || '17'];
    if (args.noenc) console.log(`frames in ${frameDir} (not encoded)`);
    else {
      const enc = spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', path.join(frameDir, 'f_%05d.jpg'),
        '-ss', String(from), '-t', String(to - from), '-i', audio,
        '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', args.preset || 'medium', ...venc,
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', args.abitrate || '256k', '-t', String(to - from), '-movflags', '+faststart', out], { stdio: 'inherit' });
      console.log(enc.status === 0 ? `wrote ${out}` : 'ffmpeg failed');
    }
  }
} finally {
  await browser.close();
  for (const b of extraBrowsers) await b.close();
  server.close();
}
