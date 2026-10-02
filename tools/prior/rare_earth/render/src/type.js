// Kinetic typography. Draws into engine.typeCtx in 1920x1080 design pixels.
import { clamp, lerp, easeOutBack, easeOutCubic, easeOutExpo, hash1, hash2, css, INK, range, smooth } from './util.js';

export const FONTS = [
  ['Archivo', 'assets/fonts/Archivo-VF.ttf', { weight: '100 900', stretch: '62% 125%' }],
  ['Anton', 'assets/fonts/Anton-Regular.ttf', {}],
  ['NotoSerifDisplay', 'assets/fonts/NotoSerifDisplay-VF.ttf', { weight: '100 900', stretch: '62% 100%' }],
  ['Unbounded', 'assets/fonts/Unbounded-VF.ttf', { weight: '200 900' }],
  ['SpaceMono', 'assets/fonts/SpaceMono-Regular.ttf', {}],
  ['SpaceMonoB', 'assets/fonts/SpaceMono-Bold.ttf', {}],
  ['JetBrainsMono', 'assets/fonts/JetBrainsMono-VF.ttf', { weight: '100 800' }],
  // Noto Sans SC Black, subset to the six characters the titles use (稀有地球第二); OFL
  ['NotoSansSC', 'assets/fonts/NotoSansSC-Black-subset.ttf', { weight: '900' }],
  ['InstrumentSerif', 'assets/fonts/InstrumentSerif-Regular.ttf', {}],
  ['InstrumentSerifI', 'assets/fonts/InstrumentSerif-Italic.ttf', {}],
  ['BigShoulders', 'assets/fonts/BigShouldersDisplay-VF.ttf', { weight: '100 900' }],
  ['VT323', 'assets/fonts/VT323-Regular.ttf', {}],
];

export async function loadFonts() {
  await Promise.all(FONTS.map(async ([name, url, desc]) => {
    const f = new FontFace(name, `url(${url})`, desc);
    await f.load();
    document.fonts.add(f);
  }));
}

// ---------- alien script (Echo glyphs): each Latin letter maps to a deterministic dial glyph
export function drawGlyph(ctx, ch, x, y, size, col, lw = 0.08) {
  const code = ch.toUpperCase().charCodeAt(0);
  if (ch === ' ') return;
  const r = size * 0.42;
  ctx.save();
  ctx.translate(x + size * 0.5, y - size * 0.5);
  ctx.strokeStyle = col; ctx.fillStyle = col;
  ctx.lineWidth = size * lw; ctx.lineCap = 'round';
  const h = (k) => hash2(code, k);
  // outer arc (partial ring), gap position encodes the letter
  const a0 = h(1) * Math.PI * 2, span = Math.PI * (1.1 + h(2) * 0.8);
  ctx.beginPath(); ctx.arc(0, 0, r, a0, a0 + span); ctx.stroke();
  // 1-3 inner spokes
  const n = 1 + Math.floor(h(3) * 3);
  for (let i = 0; i < n; i++) {
    const a = a0 + span * (0.2 + 0.6 * h(10 + i));
    const l0 = r * (0.15 + 0.2 * h(20 + i)), l1 = r * (0.55 + 0.4 * h(30 + i));
    ctx.beginPath(); ctx.moveTo(Math.cos(a) * l0, Math.sin(a) * l0); ctx.lineTo(Math.cos(a) * l1, Math.sin(a) * l1); ctx.stroke();
  }
  // dots
  const nd = Math.floor(h(4) * 3);
  for (let i = 0; i < nd; i++) {
    const a = h(40 + i) * Math.PI * 2, rr = r * (0.3 + 0.5 * h(50 + i));
    ctx.beginPath(); ctx.arc(Math.cos(a) * rr, Math.sin(a) * rr, size * 0.055, 0, Math.PI * 2); ctx.fill();
  }
  if (h(5) > 0.6) { ctx.beginPath(); ctx.arc(0, 0, r * 0.22, 0, Math.PI * 2); ctx.stroke(); }
  ctx.restore();
}

const SCRAMBLE = 'ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#%&*+=<>/\\';

export class TypeLayer {
  constructor(engine, audio) {
    this.e = engine; this.a = audio;
    this.ctx = engine.typeCtx;
  }

  begin() {
    const c = this.ctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, this.e.W, this.e.H);
    c.setTransform(this.e.S, 0, 0, this.e.S, 0, 0);
    c.textBaseline = 'alphabetic';
    c.globalAlpha = 1;
  }

  font(family, px, weight = 400, stretch = 'normal', style = 'normal') {
    const c = this.ctx;
    c.font = `${style} ${weight} ${px}px ${family}`;
    try { c.fontStretch = stretch; } catch (e) { /* older canvas */ }
  }

  // text with an offset color plate underneath (riso misregistration)
  plateText(str, x, y, main, plate, off = [4, 3], alpha = 1) {
    const c = this.ctx;
    c.globalAlpha = alpha;
    if (plate) { c.fillStyle = plate; c.fillText(str, x + off[0], y + off[1]); }
    c.fillStyle = main; c.fillText(str, x, y);
    c.globalAlpha = 1;
  }

  // ---------------------------------------------------------------- modes
  // STACK: each word of the given lines slams in on its sung syllable, stacked in a column.
  stack(t, lines, o = {}) {
    const c = this.ctx;
    const x = o.x ?? 110, y0 = o.y ?? 250, lh = o.lineH ?? 190, size = o.size ?? 200;
    const words = [];
    for (const li of lines) for (const w of this.a.line(li).words) if (!o.filter || o.filter(w)) words.push({ ...w, li });
    let row = 0;
    const maxW = o.maxW ?? 1100;
    // lay out: words flow into rows no wider than maxW
    this.font(o.family ?? 'Archivo', size, o.weight ?? 900, o.stretch ?? 'expanded');
    const rows = [[]]; let rw = 0;
    for (const w of words) {
      const txt = (o.upper === false ? w.w : w.w.toUpperCase()).replace(/[,.]/g, '');
      const ww = c.measureText(txt + ' ').width;
      if (rw + ww > maxW && rows[rows.length - 1].length) { rows.push([]); rw = 0; }
      rows[rows.length - 1].push({ ...w, txt, x: rw });
      rw += ww;
    }
    const total = rows.length;
    for (const r of rows) {
      const yy = y0 + row * lh - (o.scroll ? Math.max(0, total - (o.maxRows ?? 4)) * lh * 0 : 0);
      for (const w of r) {
        const dt = t - w.t + (o.lead ?? 0.03);
        if (dt < 0) continue;
        const k = easeOutBack(clamp(dt / 0.16), 2.2);
        const sc = lerp(o.fromScale ?? 1.6, 1, k);
        const alpha = clamp(dt / 0.05);
        const kick = this.a.kick(t) * (o.kickAmt ?? 0);
        c.save();
        c.translate(x + w.x, yy);
        c.scale(sc * (1 + kick * 0.04), sc * (1 + kick * 0.04));
        c.rotate((1 - k) * (hash1(w.t * 7) - 0.5) * 0.25);
        // karaoke: word glows in the accent color while being sung
        const singing = t >= w.t && t < w.end;
        const main = singing && o.accent ? o.accent : (o.color ?? css(INK.paper));
        this.plateText(w.txt, 0, 0, main, o.plate ?? css(INK.orange, 0.9), o.plateOff ?? [6, 5], alpha);
        c.restore();
      }
      row++;
    }
  }

  // SUBTITLE: one line, lower third, karaoke fill left->right
  subtitle(t, li, o = {}) {
    const c = this.ctx;
    const L = this.a.line(li);
    const text = o.text ?? L.text;
    const size = o.size ?? 54;
    this.font(o.family ?? 'Archivo', size, o.weight ?? 600, o.stretch ?? 'normal', o.style ?? 'normal');
    const tw = c.measureText(text).width;
    const x = (o.x ?? 960) - (o.align === 'left' ? 0 : tw / 2), y = o.y ?? 960;
    const inA = clamp((t - L.t + 0.25) / 0.25), outA = 1 - clamp((t - (o.end ?? L.end + 0.35)) / 0.25);
    const a = Math.min(inA, outA) * (o.alpha ?? 1);
    if (a <= 0) return;
    c.globalAlpha = a;
    // base
    c.fillStyle = o.dim ?? css(INK.paper, 0.45);
    c.fillText(text, x, y);
    // fill progress by word timing
    let prog = 0;
    const ws = L.words;
    for (let i = 0; i < ws.length; i++) {
      if (t >= ws[i].t) prog = i + clamp((t - ws[i].t) / Math.max(0.08, ws[i].end - ws[i].t));
    }
    const words = text.split(' ');
    let acc = 0; let px = 0;
    for (let i = 0; i < words.length; i++) {
      const wtxt = words[i] + (i < words.length - 1 ? ' ' : '');
      const ww = c.measureText(wtxt).width;
      const f = clamp(prog - i);
      if (f > 0) px = acc + ww * f;
      acc += ww;
    }
    c.save(); c.beginPath(); c.rect(x - 4, y - size * 1.2, px + 4, size * 1.6); c.clip();
    c.fillStyle = o.color ?? css(INK.paper); c.fillText(text, x, y);
    c.restore();
    c.globalAlpha = 1;
  }

  // LINE: a whole lyric line on screen at once, each word lighting up as it is sung (the word being sung takes its
  // accent colour). For a line that is hard to follow a word at a time.
  line(t, li, o = {}) {
    const c = this.ctx;
    const L = this.a.line(li), words = L.words;
    const texts = o.words ?? words.map((w) => w.w.toUpperCase().replace(/[,.]/g, ''));
    const size = o.size ?? 60;
    this.font(o.family ?? 'Archivo', size, o.weight ?? 800, o.stretch ?? 'expanded');
    const gap = c.measureText(' ').width * 1.3;
    const ws = texts.map((s) => c.measureText(s).width);
    const tw = ws.reduce((a, b) => a + b, 0) + gap * (ws.length - 1);
    const fit = Math.min(1, (o.maxW ?? 1700) / tw);
    const x0 = 960 - tw * fit / 2, y = o.y ?? 1015;
    const a = (o.alpha ?? 1) * clamp((t - (o.tIn ?? L.t - 0.3)) / 0.1);
    if (a <= 0) return;
    c.save();
    c.globalAlpha = a;
    // an ink band behind it, so the line reads over launch plumes and fireballs
    if (o.plate !== false) {
      c.fillStyle = o.plate ?? css(INK.ink, 0.72);
      c.fillRect(x0 - 28, y - size * fit * 1.02, tw * fit + 56, size * fit * 1.42);
    }
    c.translate(x0, y); c.scale(fit, fit);
    let x = 0;
    for (let i = 0; i < texts.length; i++) {
      const w = words[i];
      const sung = t >= w.t;
      const singing = sung && (i + 1 < words.length ? t < words[i + 1].t : t < L.end + 0.3);
      const pop = sung ? 1 + 0.1 * Math.exp(-(t - w.t) / 0.06) : 1;
      c.save();
      c.translate(x, -size * 0.36); c.scale(pop, pop);          // grows from its left edge, into its own space
      c.fillStyle = !sung ? (o.dim ?? css(INK.paper, 0.34)) : singing ? (o.accents?.[i] ?? o.accent ?? css(INK.yellow)) : (o.color ?? css(INK.paper));
      c.fillText(texts[i], 0, size * 0.36);
      c.restore();
      x += ws[i] + gap;
    }
    c.restore();
  }

  // KEYWORD: a single huge word, stretched and pulsed on the beat
  keyword(t, word, t0, o = {}) {
    const c = this.ctx;
    const dt = t - t0;
    if (dt < 0) return;
    const size = o.size ?? 300;
    this.font(o.family ?? 'Archivo', size, o.weight ?? 900, o.stretch ?? 'expanded');
    const k = easeOutExpo(clamp(dt / (o.inDur ?? 0.22)));
    const kick = this.a.kick(t, 0.1) * (o.kickAmt ?? 0.06);
    const tw = c.measureText(word).width;
    const fit = Math.min(1, (o.maxW ?? 1760) / Math.max(1, tw));
    const sx = lerp(o.fromSX ?? 0.4, 1, k) * (1 + kick) * fit, sy = lerp(o.fromSY ?? 1.3, 1, k) * (1 + kick * 0.5) * fit;
    const x = o.x ?? 960, y = o.y ?? 620;
    const a = clamp(dt / 0.04) * (o.alpha ?? 1) * (1 - clamp((t - (o.t1 ?? 1e9)) / 0.15));
    if (a <= 0) return;
    c.save();
    c.translate(x, y); c.scale(sx, sy);
    c.globalAlpha = a;
    if (o.outline) {
      c.lineWidth = o.outline; c.strokeStyle = o.color ?? css(INK.paper);
      c.strokeText(word, -tw / 2, 0);
    } else {
      this.plateText(word, -tw / 2, 0, o.color ?? css(INK.paper), o.plate ?? null, o.plateOff ?? [7, 6]);
    }
    c.restore();
    c.globalAlpha = 1;
  }

  // TERMINAL: brutalist monospace log lines typed out
  terminal(t, entries, o = {}) {
    const c = this.ctx;
    const size = o.size ?? 26;
    this.font(o.family ?? 'JetBrainsMono', size, o.weight ?? 500);
    let y = o.y ?? 120;
    for (const e of entries) {
      const dt = t - e.t;
      if (dt < 0) continue;
      const n = Math.floor(clamp(dt / (e.dur ?? 0.35)) * e.s.length);
      const s = e.s.slice(0, n);
      c.fillStyle = e.color ?? o.color ?? css(INK.paper, 0.9);
      c.fillText(s, o.x ?? 90, y);
      if (n < e.s.length && Math.floor(t * 8) % 2 === 0) c.fillRect((o.x ?? 90) + c.measureText(s).width + 4, y - size * 0.8, size * 0.55, size);
      y += size * 1.45;
    }
  }

  // DECODE: text appears as Echo glyphs, scrambles, resolves to Latin letters
  decode(t, text, t0, o = {}) {
    const c = this.ctx;
    const size = o.size ?? 90;
    const dur = o.dur ?? 0.8;
    this.font(o.family ?? 'Archivo', size, o.weight ?? 800, o.stretch ?? 'normal');
    const chars = [...text];
    const adv = chars.map((ch) => c.measureText(ch).width);
    const tw = adv.reduce((a, b) => a + b, 0);
    let x = (o.x ?? 960) - (o.align === 'left' ? 0 : tw / 2);
    const y = o.y ?? 540;
    const col = o.color ?? css(INK.mint);
    for (let i = 0; i < chars.length; i++) {
      const ch = chars[i];
      const start = t0 + i * (o.stagger ?? 0.02);
      const p = (t - start) / dur;
      if (p < -0.05) { x += adv[i]; continue; }
      if (ch !== ' ') {
        if (p < 0.45) {
          drawGlyph(c, ch, x, y + size * 0.1, size * 0.95, o.glyphColor ?? col, 0.075);
        } else if (p < 0.75) {
          const r = SCRAMBLE[Math.floor(hash2(i, Math.floor(t * 30)) * SCRAMBLE.length)];
          c.fillStyle = o.scrambleColor ?? css(INK.yellow); c.fillText(r, x, y);
        } else {
          c.fillStyle = o.latinColor ?? css(INK.paper); c.fillText(ch, x, y);
        }
      }
      x += adv[i];
    }
  }

  // GLYPHS only (their script), for signage on the other world
  glyphLine(text, x, y, size, col, o = {}) {
    let xx = x;
    for (const ch of text) { drawGlyph(this.ctx, ch, xx, y, size, col, o.lw ?? 0.08); xx += size * (o.adv ?? 0.9); }
    return xx - x;
  }

  // TITLE CARD: RARE EARTH / 稀有地球 / Уникальная Земля (Rare Earth as in the hypothesis: the planet, not the metals)
  title(t, t0, o = {}) {
    const c = this.ctx;
    const dt = t - t0;
    if (dt < 0) return;
    const k = easeOutExpo(clamp(dt / 0.35));
    const a = (1 - clamp((t - (o.t1 ?? t0 + 2)) / 0.2));
    if (a <= 0) return;
    c.globalAlpha = a;
    // main title in condensed serif
    this.font('NotoSerifDisplay', 330, 900, 'extra-condensed');
    const s = 'RARE EARTH';
    const tw = c.measureText(s).width;
    const fit = Math.min(1, 1680 / tw);
    c.save();
    c.translate(960, 640);
    c.scale(lerp(1.25, 1, k) * fit, lerp(1.25, 1, k) * fit);
    this.plateText(s, -tw / 2, 0, o.color ?? css(INK.paper), o.plate ?? css(INK.orange, 0.95), [8, 7]);
    c.restore();
    // sub lines, centred as a pair
    const zh = '稀有地球', ru = 'Уникальная Земля';
    this.font('NotoSansSC', 64, 900); const wz = c.measureText(zh).width;
    this.font('Unbounded', 46, 800); const wr = c.measureText(ru).width;
    const x0 = 960 - (wz + 56 + wr) / 2;
    c.fillStyle = o.sub ?? css(INK.pale);
    this.font('NotoSansSC', 64, 900); c.fillText(zh, x0, 782);
    this.font('Unbounded', 46, 800); c.fillText(ru, x0 + wz + 56, 778);
    this.font('JetBrainsMono', 22, 500);
    const meta = 'PALE BLUE DOT  ·  RX 1420.40575 MHz  ·  2011 → 2026';
    c.fillStyle = css(INK.paper, 0.8); c.fillText(meta, 960 - c.measureText(meta).width / 2, 850);
    c.globalAlpha = 1;
  }

  // small HUD string
  hud(str, x, y, o = {}) {
    const c = this.ctx;
    this.font(o.family ?? 'JetBrainsMono', o.size ?? 20, o.weight ?? 500);
    const w = c.measureText(str).width, sz = o.size ?? 20;
    const x0 = o.align === 'right' ? x - w : o.align === 'center' ? x - w / 2 : x;
    if (o.plate && str) {            // optional ink backing, for HUD lines over busy light-mode frames
      c.globalAlpha = 1; c.fillStyle = o.plate; c.fillRect(x0 - 10, y - sz * 1.02, w + 20, sz * 1.42);
    }
    c.globalAlpha = o.alpha ?? 0.9;
    c.fillStyle = o.color ?? css(INK.paper);
    c.fillText(str, x0, y);
    c.globalAlpha = 1;
  }

  // censor bar for the blank
  censor(t, t0, t1, o = {}) {
    if (t < t0 || t > t1) return;
    const c = this.ctx;
    this.font('Archivo', 96, 800, 'normal');
    const pre = o.pre ?? 'and now we’re';
    const pw = c.measureText(pre + ' ').width;
    const barW = 520;
    const x = 960 - (pw + barW) / 2, y = 575;
    c.fillStyle = css(INK.paper, 0.9); c.fillText(pre, x, y);
    c.fillStyle = css(INK.paper);
    c.fillRect(x + pw, y - 78, barW, 96);
  }
}
