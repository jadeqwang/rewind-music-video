// render.mjs — headless capture harness for the REWIND renderer (playwright-core + SwiftShader WebGL2).
//   node render.mjs --sheet 36,37.5,39 [--cols 4] [--tw 480] [--out lookdev/sheet.png]   contact sheet (also a:b:step)
//   node render.mjs --stills 36.5,40.2 [--out lookdev/stills]                               full-res JPEG stills
//   node render.mjs --range 36 48 [--workers 3] [--dir frames] [--force]                     frames (resumable)
//   node render.mjs --encode [--range 36 48] [--dir frames] [--out lookdev/lookdev.mp4]      frames + song slice → MP4
//   node render.mjs --list                                                                   shot table
// Common: --shots lookdev (shot table, default main) --w 1920 --h 1080 --verbose
// Every frame is a pure function of t, so frames render in any order and any number of workers.
import { chromium } from 'playwright-core';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdirSync, writeFileSync, existsSync, statSync, renameSync, readdirSync, createReadStream } from 'node:fs';
import { dirname, resolve, extname, join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url)), ROOT = resolve(HERE, '..');
const argv = process.argv.slice(2), args = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i]; if (!a.startsWith('--')) continue;
  const k = a.slice(2), eq = k.indexOf('=');
  if (eq >= 0) { args[k.slice(0, eq)] = k.slice(eq + 1); continue; }
  const vals = []; while (i + 1 < argv.length && !argv[i + 1].startsWith('--')) vals.push(argv[++i]);
  args[k] = vals.length === 0 ? true : vals.length === 1 ? vals[0] : vals;
}
const findChrome = () => {
  if (args.chrome || process.env.CHROME) return args.chrome || process.env.CHROME;
  const base = '/opt/pw-browsers';
  for (const d of readdirSync(base).filter(d => d.startsWith('chromium-')).sort().reverse()) { const p = join(base, d, 'chrome-linux', 'chrome'); if (existsSync(p)) return p; }
  throw new Error('no chrome under /opt/pw-browsers');
};
const CHROME = findChrome();
const SONG = resolve(ROOT, args.song || 'Rewind (4).mp3');
const FPS = 30, W = +(args.w || 1920), H = +(args.h || 1080);
const SHOTS = args.shots || 'main';
const FRAMES = resolve(HERE, args.dir || `frames/${SHOTS}${W === 1920 ? '' : '_' + W}`);
const Q = +(args.q || 0.94);
const run = (cmd, a) => new Promise((ok, bad) => { const p = spawn(cmd, a, { stdio: 'inherit' }); p.on('close', c => (c ? bad(new Error(cmd + ' exited ' + c)) : ok())); });
const range = () => { const r = [].concat(args.range || []).map(Number); return r.length === 2 ? r : null; };
const fname = i => join(FRAMES, `f${String(i).padStart(5, '0')}.jpg`);

if (args.encode && !args.sheet && !args.stills) {
  const files = readdirSync(FRAMES).filter(f => /^f\d{5}\.jpg$/.test(f)).sort();
  if (!files.length) throw new Error('no frames in ' + FRAMES);
  let [a, b] = range() || [parseInt(files[0].slice(1)) / FPS, (parseInt(files[files.length - 1].slice(1)) + 1) / FPS];
  const i0 = Math.round(a * FPS), i1 = Math.round(b * FPS);
  const missing = []; for (let i = i0; i < i1; i++) if (!existsSync(fname(i))) missing.push(i);
  if (missing.length) throw new Error(`${missing.length} frames missing in ${FRAMES} (first ${missing[0]}); run --range first`);
  const out = resolve(HERE, args.out || `lookdev/${SHOTS}.mp4`); mkdirSync(dirname(out), { recursive: true });
  console.log(`encoding ${i1 - i0} frames (${a.toFixed(3)}–${b.toFixed(3)} s) → ${out}`);
  await run('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-start_number', String(i0), '-i', join(FRAMES, 'f%05d.jpg'),
    '-ss', a.toFixed(4), '-t', (b - a).toFixed(4), '-i', SONG, '-map', '0:v', '-map', '1:a', '-frames:v', String(i1 - i0),
    '-c:v', 'libx264', '-preset', args.preset || 'slow', '-crf', String(args.crf || 17), '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out]);
  console.log('wrote ' + out);
  process.exit(0);
}

// static server over the repo root (render/ page + ../assets, ../analysis), so canvases are never tainted
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.woff': 'font/woff', '.mp3': 'audio/mpeg' };
const server = createServer((req, res) => {
  const p = resolve(ROOT, '.' + decodeURIComponent(req.url.split('?')[0]));
  if (!(p === ROOT || p.startsWith(ROOT + sep)) || !existsSync(p) || statSync(p).isDirectory()) { if (args.verbose) console.log('404 ' + req.url); res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[extname(p)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
  createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const PORT = server.address().port;

const FLAGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
  '--disable-renderer-backgrounding', '--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows',
  '--force-color-profile=srgb', '--js-flags=--max-old-space-size=4096', '--no-sandbox', '--disable-accelerated-2d-canvas',
  ...(args.flags ? String(args.flags).split(' ') : [])];
const browsers = [];
async function openPage(tag = '') {
  // one browser per worker: SwiftShader rasterises in the GPU process, pages in one browser would contend for it
  const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: FLAGS });
  browsers.push(browser);
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on('console', m => { if (['error', 'warning'].includes(m.type()) || args.verbose) console.log(`[page${tag}] ${m.text()}`); });
  page.on('pageerror', e => console.log(`[page error${tag}] ${e.message}`));
  await page.goto(`http://127.0.0.1:${PORT}/render/index.html?render&shots=${SHOTS}&w=${W}&h=${H}`, { waitUntil: 'load' });
  await page.waitForFunction('window.ready === true || window.bootError', null, { timeout: 120000, polling: 100 });
  const err = await page.evaluate('window.bootError'); if (err) throw new Error('boot failed: ' + err);
  if (args.verbose) console.log(await page.evaluate('JSON.stringify(window.timingInfo)'));
  return { page, browser };
}
const dataUrl = s => Buffer.from(s.slice(s.indexOf(',') + 1), 'base64');
const parseTimes = s => [].concat(s).join(',').split(',').filter(Boolean).flatMap(x => {
  if (x.includes(':')) { const [a, b, st] = x.split(':').map(Number); const r = []; for (let t = a; t < b - 1e-9; t += st) r.push(+t.toFixed(4)); return r; }
  return [Number(x)];
});
const atomic = (f, buf) => { writeFileSync(f + '.tmp', buf); renameSync(f + '.tmp', f); };

try {
  if (args.list) {
    const { page } = await openPage();
    const info = await page.evaluate('window.timingInfo'); console.log(JSON.stringify(info));
    for (const s of await page.evaluate('window.listShots()')) console.log(`${s.id.padEnd(16)} ${s.scene.padEnd(8)} ${s.t0.toFixed(3).padStart(8)} → ${s.t1.toFixed(3).padStart(8)}  (${(s.t1 - s.t0).toFixed(2)} s)`);
  } else if (args.sheet) {
    const { page } = await openPage(); const times = parseTimes(args.sheet);
    const out = resolve(HERE, args.out || `lookdev/sheet_${SHOTS}.png`); mkdirSync(dirname(out), { recursive: true });
    const r = await page.evaluate(([t, c, w]) => window.renderSheet(t, c, w), [times, +(args.cols || 4), +(args.tw || 480)]);
    atomic(out, dataUrl(r.url));
    const ms = r.ms; console.log(`${out}\nms/frame: ${ms.map(x => x.toFixed(0)).join(' ')}  (mean ${(ms.reduce((a, b) => a + b, 0) / ms.length).toFixed(0)})`);
  } else if (args.stills) {
    const { page } = await openPage(); const out = resolve(HERE, args.out || `lookdev/stills_${SHOTS}`); mkdirSync(out, { recursive: true });
    for (const t of parseTimes(args.stills)) {
      const r = await page.evaluate(([t, q]) => window.renderTimed(t, 'image/jpeg', q), [t, Q]);
      const f = join(out, `t${t.toFixed(3).replace('.', '_')}.jpg`); atomic(f, dataUrl(r.url));
      console.log(`${f}  render ${r.ms.toFixed(0)} ms  encode ${r.msEnc.toFixed(0)} ms`);
    }
  } else if (range()) {
    const [a, b] = range(), workers = +(args.workers || 3);
    mkdirSync(FRAMES, { recursive: true });
    const i0 = Math.round(a * FPS), i1 = Math.round(b * FPS);
    const todo = []; for (let i = i0; i < i1; i++) if (args.force || !existsSync(fname(i)) || statSync(fname(i)).size < 1000) todo.push(i);
    console.log(`${todo.length} frames to render (${i1 - i0 - todo.length} done) with ${workers} workers → ${FRAMES}`);
    let next = 0, done = 0, msSum = 0; const start = Date.now();
    const work = async w => {
      if (next >= todo.length) return;
      let P = await openPage('#' + w);
      while (next < todo.length) {
        const i = todo[next++]; let r;
        try { r = await P.page.evaluate(([t, q]) => window.renderTimed(t, 'image/jpeg', q), [i / FPS, Q]); }
        catch (e) {
          console.log(`worker ${w}: frame ${i} failed (${e.message.split('\n')[0]}); reopening`);
          try { await P.browser.close(); } catch (e2) { /* gone */ }
          P = await openPage('#' + w); r = await P.page.evaluate(([t, q]) => window.renderTimed(t, 'image/jpeg', q), [i / FPS, Q]);
        }
        atomic(fname(i), dataUrl(r.url)); msSum += r.ms + r.msEnc;
        if (++done % 30 === 0 || done === todo.length) {
          const el = (Date.now() - start) / 1000;
          console.log(`frame ${done}/${todo.length}  in-page ${(msSum / done).toFixed(0)} ms/frame  wall ${(el / done * 1000).toFixed(0)} ms/frame effective  eta ${((todo.length - done) * el / done / 60).toFixed(1)} min`);
        }
      }
    };
    await Promise.all(Array.from({ length: workers }, (_, w) => work(w)));
    if (args.encode) {
      const out = resolve(HERE, args.out || `lookdev/${SHOTS}.mp4`); mkdirSync(dirname(out), { recursive: true });
      await run('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-start_number', String(i0), '-i', join(FRAMES, 'f%05d.jpg'),
        '-ss', a.toFixed(4), '-t', (b - a).toFixed(4), '-i', SONG, '-map', '0:v', '-map', '1:a', '-frames:v', String(i1 - i0),
        '-c:v', 'libx264', '-preset', args.preset || 'slow', '-crf', String(args.crf || 17), '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out]);
      console.log('wrote ' + out);
    }
  } else console.log('nothing to do: --sheet | --stills | --range a b [--encode] | --encode | --list');
} finally {
  for (const b of browsers) await b.close().catch(() => {});
  server.close();
}
