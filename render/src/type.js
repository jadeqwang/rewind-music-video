// type.js: fonts + kinetic lyric typography (design px, draws into the type layer unless told otherwise).
// Roles: CMU (Computer Modern italic, the dissertation voice) · SLAM (Anton / Big Shoulders, drops) · JBM (mono, system/HUD)
// Modes: page() (a) · slam() (b) · subtitle() (c) · redact() (d) · revisions() (e)
import { DW, DH, PAL, clamp, lerp, inv, smooth, easeOutCubic, easeOutExpo, easeOutBack, hash, hsig, rgba, fin } from './core.js';

const LATIN = 'U+0000-00D6,U+00D8-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2000-2015,U+2017-206F,U+20AC,U+2122';
const SYMS = 'U+00D7,U+2016,U+2190-27BF';
export const FONTS = [
  ['CMU', 'fonts/cmu-serif-500-italic.ttf', { style: 'italic', weight: '500' }],
  ['CMU', 'fonts/cmu-serif-700-italic.ttf', { style: 'italic', weight: '700' }],
  ['CMU', 'fonts/cmu-serif-500-roman.ttf', { style: 'normal', weight: '500' }],
  ['CMUB', 'fonts/cmu-serif-700-roman.ttf', { style: 'normal', weight: '700' }],
  ['Anton', 'fonts/anton-latin-400-normal.woff2', { weight: '400' }],
  ['BigShoulders', 'fonts/big-shoulders-display-latin-800-normal.woff2', { weight: '800' }],
  ['BigShoulders', 'fonts/big-shoulders-display-latin-900-normal.woff2', { weight: '900' }],
  ['Archivo', 'fonts/archivo-latin-wdth-normal.woff2', { weight: '100 900', stretch: '62% 125%' }],
  ['JBM', 'fonts/jetbrains-mono-latin-400-normal.woff2', { weight: '400', unicodeRange: LATIN }],
  ['JBM', 'fonts/jetbrains-mono-latin-700-normal.woff2', { weight: '700', unicodeRange: LATIN }],
  // symbols the JetBrains latin subset lacks (✗ ◀ ▶ − ∎ ∴ ‖ × █ box/arrows): DejaVu Sans Mono subset, same family
  ['JBM', 'fonts/dejavu-sans-mono-symbols.ttf', { weight: '400', unicodeRange: SYMS }],
  ['JBM', 'fonts/dejavu-sans-mono-Bold-symbols.ttf', { weight: '700', unicodeRange: SYMS }],
];
export async function loadFonts() {
  await Promise.all(FONTS.map(async ([fam, u, d]) => { const f = new FontFace(fam, `url(${u})`, d); await f.load(); document.fonts.add(f); }));
  await document.fonts.ready;
  for (const s of ['italic 500 40px CMU', 'italic 700 40px CMU', '500 40px CMU', '700 40px CMUB', '40px Anton', '900 40px BigShoulders', '800 40px Archivo', '400 20px JBM', '700 20px JBM'])
    await document.fonts.load(s, 'Aa1✗◀−∎');
}
export const F = {
  cmu: (px, w = 500) => `italic ${w} ${px}px CMU`, cmuR: px => `500 ${px}px CMU`,
  slam: px => `400 ${px}px Anton`, shoulders: (px, w = 900) => `${w} ${px}px BigShoulders`,
  archivo: (px, w = 800) => `${w} ${px}px Archivo`, mono: (px, w = 400) => `${w} ${px}px JBM`,
};
export function setFont(g, f, spacing = 0) { g.font = f; try { g.letterSpacing = `${spacing}px`; } catch (e) { /* old canvas */ } }

const clean = w => String(w).replace(/^[\s"“]+|[\s"”]+$/g, '');

// (a) PAGE — big Computer Modern italic (120–170 px), word by word, in the left two-thirds, set like a dissertation
// page. The sung word is bone-white, past words dim. Paginates: maxLines lines per page; the page holding the latest
// sung word is shown (the folio advances with it).
// words: [{w,start,end, note?: '1'}]; o: {x, y, w (measure), size, lead, maxLines, color, header, folio, footnotes:[{mark,text,at}]}
export function page(g, words, t, o = {}) {
  const x0 = o.x ?? 150, y0 = o.y ?? 400, measure = o.w ?? 1150, size = o.size ?? 140, lead = o.lead ?? 1.12;
  const col = o.color || PAL.bone, maxLines = o.maxLines ?? 3;
  g.save(); g.textBaseline = 'alphabetic';
  setFont(g, F.cmu(size));
  const space = g.measureText(' ').width;
  let x = x0, line = 0;
  const placed = [];
  for (const w of words) {
    const s = clean(w.w), ww = g.measureText(s).width;
    if (x > x0 && x + ww > x0 + measure) { x = x0; line++; }
    placed.push({ w, s, x, line, ww, pg: Math.floor(line / maxLines), y: y0 + (line % maxLines) * size * lead }); x += ww + space * 1.05;
  }
  let cur = 0; for (const p of placed) if (p.w.start <= t + 0.04) cur = p.pg;
  if (o.page != null) cur = o.page;
  const a0 = o.furniture ?? 1;
  if (o.header) {
    const hx = o.headerX ?? x0;   // shifted right when the proof HUD (ATTEMPT, top-left) is on
    setFont(g, F.cmu(34)); g.fillStyle = rgba(PAL.boneDim, a0);
    g.fillText(o.header, hx, 120); const hw = g.measureText(o.header).width;
    const xr = Math.max(x0 + measure, hx + hw + 90);
    if (o.folio) { const fo = String(/^\d+$/.test(o.folio) ? +o.folio + cur : o.folio); setFont(g, F.cmuR(34)); const fw = g.measureText(fo).width; g.fillText(fo, xr - fw, 120); }
    g.fillStyle = rgba(PAL.boneDim, 0.7 * a0); g.fillRect(hx, 142, xr - hx, 2);
  }
  for (const p of placed) {
    if (p.pg !== cur) continue;
    const u = inv(p.w.start - 0.04, p.w.start + 0.18, t);
    if (u <= 0) continue;
    const e = easeOutCubic(u);
    const sung = t >= p.w.start - 0.04 && t < (p.w.end ?? p.w.start + .4) + 0.12;
    g.fillStyle = rgba(col, e * (sung ? 1 : (o.settle ?? 0.62)) * (o.alpha ?? 1));
    setFont(g, F.cmu(size));
    g.fillText(p.s, p.x, p.y + (1 - e) * size * 0.06);
    if (p.w.note) { setFont(g, F.cmuR(size * 0.4)); g.fillStyle = rgba(o.noteColor || PAL.red, e); g.fillText(p.w.note, p.x + p.ww + 6, p.y - size * 0.5); }
  }
  if (o.footnotes) {
    let fy = o.footY ?? 990;
    const shown = o.footnotes.filter(f => t >= f.at && (f.page == null || f.page === cur));
    if (shown.length) { g.fillStyle = rgba(PAL.boneDim, 0.8 * smooth(shown[0].at, shown[0].at + .3, t)); g.fillRect(x0, fy - 58, measure * 0.3, 2); }
    for (const f of shown) {
      const a = smooth(f.at, f.at + .35, t);
      setFont(g, F.cmuR(24)); g.fillStyle = rgba(o.noteColor || PAL.red, a); g.fillText(f.mark, x0, fy - 16);
      setFont(g, F.cmu(o.footSize ?? 36)); g.fillStyle = rgba(PAL.bone, 0.85 * a); g.fillText(f.text, x0 + 22, fy);
      fy += 46;
    }
  }
  g.restore();
  return placed.filter(p => p.pg === cur);
}

// (b) SLAM — massive condensed grotesk for drops, with stutter: on each hit the word re-slams with frame-skipped
// offset copies (plate offsets in siren colours), fitted to maxW. o: {t0 (hit time), t, text, x, y, maxW, maxH, color,
// stutter (0..1), plates [colA,colB], seed, align, font: 'anton'|'shoulders'}
export function slam(g, o) {
  const t = o.t, dt = t - o.t0; if (dt < 0) return;
  const text = o.text.toUpperCase();
  g.save(); g.textBaseline = 'alphabetic';
  const fam = o.font === 'shoulders' ? (px => F.shoulders(px, 900)) : F.slam;
  let px = o.size ?? 700; setFont(g, fam(px), o.track ?? 0);
  let w = g.measureText(text).width;
  const maxW = o.maxW ?? 1760; if (w > maxW) { px *= maxW / w; setFont(g, fam(px), o.track ?? 0); w = g.measureText(text).width; }
  if (o.maxH && px * 0.74 > o.maxH) { px = o.maxH / 0.74; setFont(g, fam(px), o.track ?? 0); w = g.measureText(text).width; }
  // slam-in: overshoot scale 1.18 → 1 over 5 frames, then a slow creep
  const dc = t - (o.creepFrom ?? o.t0);   // slow creep measured from the first hit, overshoot only on real hits
  const e = (o.stutter ?? 0) >= 0.9 && dt < 0.17 ? lerp(1.18, 1, easeOutExpo(dt / 0.17)) : 1 + 0.02 * Math.min(1, Math.max(0, dc - .17) / 1.2);
  const cx = o.x ?? DW / 2, by = o.y ?? DH / 2 + px * 0.36;
  const frame = Math.floor(dt * 30 + 1e-3);
  g.translate(cx, by - px * 0.36); g.scale(e, e); g.translate(-cx, -(by - px * 0.36));
  const left = o.align === 'left' ? cx : cx - w / 2;
  const st = clamp(o.stutter ?? 0), seed = o.seed ?? 0, col = o.color || PAL.bone;
  // stutter: a single offset plate (siren colour) behind the word on the first frames, converging to zero,
  // and on the first two frames the word is cut into a few horizontal bands that slip sideways (frame skip)
  if (st > 0 && frame < 5 && o.plates !== false) {
    const plates = o.plates || [PAL.red, PAL.blue], k = frame % 2;
    const dx = (k ? 1 : -1) * (34 - frame * 7) * st;
    g.fillStyle = rgba(plates[k], 1 - frame / 5); g.fillText(text, left + dx, by + (k ? 4 : -4) * st);
  }
  if (st > 0 && frame < 2 && o.slices !== false) {
    const n = 4, top = by - px * 0.74, hh = px * 0.76 / n;
    for (let i = 0; i < n; i++) {
      g.save(); g.beginPath(); g.rect(0, top + i * hh, DW, hh + (i === n - 1 ? px : 1)); g.clip();
      g.fillStyle = col; g.fillText(text, left + hsig(seed, frame, i, 3) * 46 * st * (i % 2 ? 1 : 0.4), by);
      g.restore();
    }
  } else { g.fillStyle = col; g.fillText(text, left, by); }
  g.restore();
  return { w: w * e, px };
}

// (c) SUBTITLE — small mono, bottom centre; the sung word lit. o: {y, size, color, lit, upper}
export function subtitle(g, words, t, o = {}) {
  const vis = words.filter(w => t >= w.start - 0.05);
  if (!vis.length) return;
  g.save(); setFont(g, F.mono(Math.max(42, o.size ?? 44), 400), 1); g.textBaseline = 'alphabetic';
  const txt = words.map(w => (o.upper ? clean(w.w).toUpperCase() : clean(w.w).toLowerCase()));
  const sp = g.measureText(' ').width, widths = txt.map(s => g.measureText(s).width);
  const total = widths.reduce((a, b) => a + b, 0) + sp * (txt.length - 1);
  let x = (o.x ?? DW / 2) - total / 2; const y = o.y ?? 990;
  for (let i = 0; i < words.length; i++) {
    const w = words[i], on = t >= w.start - 0.05;
    const lit = t >= w.start && t < (w.end ?? w.start + .4);
    g.fillStyle = on ? (lit ? (o.lit || PAL.bone) : rgba(o.color || PAL.boneDim, 0.95)) : rgba(PAL.boneDim, 0.0);
    g.fillText(txt[i], x, y); x += widths[i] + sp;
  }
  g.restore();
}

// (d) REDACT — a solid bar the colour of the type covers the word, then retracts in steps to reveal it
// (the FOIA bar lifting). o: {text, x, y, font, t0, dur, color, barColor, align}
export function redact(g, o) {
  const t = o.t; g.save(); setFont(g, o.font || F.mono(60, 700), o.track ?? 0); g.textBaseline = 'alphabetic';
  const w = g.measureText(o.text).width, px = parseFloat(/(\d+(\.\d+)?)px/.exec(g.font)[1]);
  const x = o.align === 'center' ? o.x - w / 2 : o.x, y = o.y;
  const u = clamp((t - o.t0) / (o.dur ?? 0.4));
  const steps = o.steps ?? 6, us = Math.floor(u * steps) / steps;            // stepped like a printer head
  g.fillStyle = o.color || PAL.bone; g.fillText(o.text, x, y);
  const barL = x - px * 0.08 + (w + px * 0.16) * us, barR = x + w + px * 0.08;
  if (u < 1) { g.fillStyle = o.barColor || o.color || PAL.bone; g.fillRect(barL, y - px * 0.78, barR - barL, px * 0.98); }
  g.restore();
  return w;
}
// a static redaction banner line: some words visible, others replaced by bars
export function redactedLine(g, parts, x, y, font, col = PAL.boneDim, barCol = PAL.bone) {
  g.save(); setFont(g, font, 1); g.textBaseline = 'alphabetic';
  const px = parseFloat(/(\d+(\.\d+)?)px/.exec(g.font)[1]);
  for (const p of parts) {
    const s = typeof p === 'string' ? p : '█'.repeat(p.bar);
    const w = typeof p === 'string' ? g.measureText(s).width : g.measureText('M').width * p.bar;
    if (typeof p === 'string') { g.fillStyle = col; g.fillText(s, x, y); }
    else { g.fillStyle = barCol; g.fillRect(x, y - px * 0.8, w, px * 0.98); }
    x += w + g.measureText(' ').width;
  }
  g.restore();
}

// (e) REVISIONS — stacked, overlapping takes of the same line (vocal stacks as track changes):
// each revision is offset and dimmer; struck words get a rule, inserted words an underline in siren red.
// revs: [{words:[{w,start,end, del?, ins?}], dx, dy, alpha}], o: {x,y,size,measure}
export function revisions(g, revs, t, o = {}) {
  for (let i = 0; i < revs.length; i++) {
    const r = revs[i];
    const placed = page(g, r.words, t, { x: (o.x ?? 150) + (r.dx ?? i * 18), y: (o.y ?? 420) + (r.dy ?? i * 40), w: o.measure ?? 1150, size: o.size ?? 120, maxLines: 99, alpha: r.alpha ?? Math.pow(0.55, revs.length - 1 - i), settle: 1 });
    g.save();
    for (const p of placed) {
      if (t < p.w.start) continue;
      const u = easeOutCubic(inv(p.w.start, p.w.start + .25, t));
      if (p.w.del) { g.fillStyle = rgba(PAL.red, (r.alpha ?? 1) * 0.9); g.fillRect(p.x, p.y - (o.size ?? 80) * 0.28, p.ww * u, 3); }
      if (p.w.ins) { g.fillStyle = rgba(PAL.red, (r.alpha ?? 1) * 0.9); g.fillRect(p.x, p.y + 10, p.ww * u, 2); }
    }
    g.restore();
  }
}
