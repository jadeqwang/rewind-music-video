// render.mjs: drive studio.html in headless Chromium.
//   node render.mjs --sheet=23,23.5,24 [--cols=3] [--w=640] --out=out/check.jpg   contact sheet (fast visual check)
//   node render.mjs --stills=0.8,3,23.8 --out=out/test                          full-res stills (JPEG)
//   node render.mjs --clip=0:6 [--fps=24] --out=out/test.mp4                    short clip with the song
//   node render.mjs --frames=0:237.8 --workers=4                                full-res JPEG frames → out/frames (resumable)
//   node render.mjs --encode [--out=out/orbital_sunrise.mp4]                     frames + song → MP4
// Every frame is a pure function of song time t, so frames can be rendered in any order.
import puppeteer from 'puppeteer-core';
import { spawn, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdirSync, writeFileSync, existsSync, statSync, renameSync, readdirSync, createReadStream } from 'node:fs';
import { dirname, resolve, extname, join } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(a => { const s = a.replace(/^--/, ''), i = s.indexOf('='); return i < 0 ? [s, true] : [s.slice(0, i), s.slice(i + 1)]; }));
const CHROME = args.chrome || process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const ROOT = resolve('.');
// the final mix: the song with its last chord allowed to ring out (tools/extend_ending.py); falls back to the original
const EXT = resolve('../media/audio/Orbital_Sunrise_extended.wav');
const SONG = args.song ? resolve(args.song) : (existsSync(EXT) ? EXT : resolve('../Orbital_Sunrise.mp3'));
const probeDur = f => { try { return +execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).toString().trim(); } catch (e) { return 237.76; } };
const DUR = probeDur(SONG), fps = +(args.fps || 24);
const FRAMES_DIR = args.dir || 'out/frames';
const W = +(args.width || 1920), H = +(args.height || 1080);

const run = (cmd, a) => new Promise((ok, bad) => { const p = spawn(cmd, a, { stdio: 'inherit' }); p.on('close', c => c ? bad(new Error(cmd + ' exited ' + c)) : ok()); });

if (args.encode) {
  const out = args.out || 'out/orbital_sunrise.mp4', n = readdirSync(FRAMES_DIR).filter(f => f.endsWith('.jpg')).length;
  mkdirSync(dirname(out), { recursive: true });
  console.log(`encoding ${n} frames → ${out}`);
  await run('ffmpeg', ['-y', '-loglevel', 'error', '-stats', '-framerate', String(fps), '-i', `${FRAMES_DIR}/f%05d.jpg`, '-i', SONG,
    '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', args.preset || 'slow', '-crf', String(args.crf || 16), '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', '-shortest', out]);
  console.log('wrote ' + out);
  process.exit(0);
}

// Static file server (localhost) so plates can be read back with getImageData without canvas tainting.
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png', '.ttf': 'font/ttf', '.webp': 'image/webp', '.bin': 'application/octet-stream' };
const server = createServer((req, res) => {
  const p = join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !existsSync(p) || statSync(p).isDirectory()) { if (args.verbose) console.log('404 ' + req.url); res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[extname(p)] || 'application/octet-stream', 'Cache-Control': 'max-age=3600' });
  createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const PORT = server.address().port;

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: true, protocolTimeout: 0,
  args: ['--no-sandbox', `--window-size=${W},${H}`, '--disable-renderer-backgrounding', '--disable-background-timer-throttling', '--force-color-profile=srgb', '--js-flags=--max-old-space-size=4096']
});
async function openPage(tag = '') {
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  page.on('console', m => { if (['error', 'warn'].includes(m.type()) || args.verbose) console.log(`[page${tag}]`, m.text()); });
  page.on('pageerror', e => console.log(`[page error${tag}]`, e.message));
  await page.goto(`http://127.0.0.1:${PORT}/studio.html?render&w=${W}&h=${H}${args.q ? '&' + args.q : ''}`, { waitUntil: 'load' });
  await page.waitForFunction('window.ready === true', { timeout: 900000, polling: 500 });
  return page;
}
const frameOf = async (page, t, type, q) => {
  const url = await page.evaluate((t, type, q) => window.renderAt(t, type, q), t, type, q);
  return Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');
};
const times = s => String(s).split(',').map(Number);

try {
  if (args.list) {
    const page = await openPage();
    const shots = await page.evaluate(() => SHOTS.map(s => [s.name, +s.t0.toFixed(3), +s.t1.toFixed(3)]));
    for (const [n, a, b] of shots) console.log(`${n.padEnd(18)} ${a.toFixed(2).padStart(7)} → ${b.toFixed(2).padStart(7)}  (${(b - a).toFixed(2)} s)`);
    if (args.out) writeFileSync(args.out, JSON.stringify(shots));
  } else if (args.sheet) {
    const page = await openPage(), out = args.out || 'out/sheet.jpg'; mkdirSync(dirname(out), { recursive: true });
    const { url, ms } = await page.evaluate((ts, c, w) => window.renderSheet(ts, c, w), times(args.sheet), +(args.cols || 3), +(args.w || 640));
    writeFileSync(out, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
    console.log(`${out}  ms/frame: ${ms.map(x => x.toFixed(0)).join(' ')}`);
  } else if (args.source) {
    // making-of pairs: the reference plate as the renderer placed it | the drawn frame
    const page = await openPage(), out = args.out || 'out/source'; mkdirSync(out, { recursive: true });
    const info = {};
    for (const s of times(args.source)) {
      const tag = `t${s.toFixed(2).replace('.', '_')}`;
      const { url, plates } = await page.evaluate(t => window.renderSource(t), s);
      writeFileSync(`${out}/${tag}_plate.jpg`, Buffer.from(url.slice(url.indexOf(',') + 1), 'base64'));
      writeFileSync(`${out}/${tag}_drawn.jpg`, await frameOf(page, s, 'image/jpeg', 0.92));
      info[tag] = plates; console.log(tag, JSON.stringify(plates));
    }
    writeFileSync(`${out}/plates.json`, JSON.stringify(info, null, 1));
  } else if (args.stills) {
    const page = await openPage(), out = args.out || 'out/stills'; mkdirSync(out, { recursive: true });
    for (const s of times(args.stills)) {
      const t0 = Date.now(), buf = await frameOf(page, s, 'image/jpeg', 0.95);
      const f = `${out}/t${s.toFixed(2).replace('.', '_')}.jpg`; writeFileSync(f, buf);
      console.log(`${f}  ${Date.now() - t0} ms`);
    }
  } else if (args.frames) {
    // Parallel, resumable: each worker page pulls the next missing frame index; files are written atomically.
    const [a, b] = String(args.frames).split(':').map(Number), workers = +(args.workers || 4);
    mkdirSync(FRAMES_DIR, { recursive: true });
    const first = Math.round(a * fps), last = Math.min(Math.ceil(DUR * fps) - 1, Math.round(b * fps) - 1);
    const todo = []; for (let i = first; i <= last; i++) { const f = `${FRAMES_DIR}/f${String(i).padStart(5, '0')}.jpg`; if (args.force || !existsSync(f) || statSync(f).size < 1000) todo.push(i); }
    console.log(`${todo.length} frames to render (${last - first + 1 - todo.length} already done), ${workers} workers`);
    let next = 0, done = 0; const start = Date.now();
    const work = async w => {
      if (next >= todo.length) return;
      let page = await openPage('#' + w);
      while (next < todo.length) {
        const i = todo[next++], f = `${FRAMES_DIR}/f${String(i).padStart(5, '0')}.jpg`;
        let buf;
        try { buf = await frameOf(page, i / fps, 'image/jpeg', 0.93); }
        catch (e) { // a crashed or hung page: open a fresh one and retry this frame once
          console.log(`worker ${w}: frame ${i} failed (${e.message}); reopening page`);
          try { await page.close(); } catch (e2) { }
          page = await openPage('#' + w); buf = await frameOf(page, i / fps, 'image/jpeg', 0.93);
        }
        writeFileSync(f + '.tmp', buf); renameSync(f + '.tmp', f);
        if (++done % 48 === 0 || done === todo.length) {
          const el = (Date.now() - start) / 1000;
          console.log(`frame ${done}/${todo.length}  ${(el / done * 1000).toFixed(0)} ms/frame effective  eta ${((todo.length - done) * el / done / 60).toFixed(1)} min`);
        }
      }
    };
    await Promise.all(Array.from({ length: workers }, (_, w) => work(w)));
  } else {
    const page = await openPage();
    const [a, b] = args.clip ? String(args.clip).split(':').map(Number) : [0, DUR];
    const out = args.out || 'out/clip.mp4'; mkdirSync(dirname(out), { recursive: true });
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
      '-ss', String(a), '-t', String(b - a), '-i', SONG,
      '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-shortest', out],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    const n = Math.round((b - a) * fps), start = Date.now();
    for (let i = 0; i < n; i++) {
      const buf = await frameOf(page, a + i / fps, 'image/jpeg', 0.92);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 24 === 0 || i === n - 1) console.log(`frame ${i + 1}/${n}  ${((Date.now() - start) / (i + 1)).toFixed(0)} ms/frame`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
    console.log(`wrote ${out}`);
  }
} finally {
  await browser.close();
  server.close();
}
