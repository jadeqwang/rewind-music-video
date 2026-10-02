// type.js: the lyric and telemetry typography.
// Faces: Anton (impact, EN), Oswald (Cyrillic echo), Instrument Serif italic (the singer's lines),
// JetBrains Mono (telemetry). Type is drawn crisp, then grained lightly so it sits on the paper.

const FONT = {
  impact: (s) => `${s}px Anton`,
  cyr: (s, w = 700) => `${w} ${s}px Oswald`,
  serif: (s) => `italic ${s}px "Instrument Serif"`,
  serifR: (s) => `${s}px "Instrument Serif"`,
  mono: (s, w = 400) => `${w} ${s}px "JetBrains Mono"`,
};

// word timings for the lyric lines: [{sec, text, t0, t1, words:[[t, w], ...]}]
function linesIn(sec) { return TM.lines.filter(l => l.sec === sec); }
function lineAt(t, pad = .15) { return TM.lines.find(l => t >= l.t0 - pad && t < l.t1); }
function wordT(line, i) { return line.words[Math.min(i, line.words.length - 1)][0]; }
// progress of a word's entrance (0 before, 1 after `d` seconds)
const wordIn = (t, wt, d = .14) => clamp((t - wt) / d);

function setFont(g, f, ls = 0) { g.font = f; g.letterSpacing = ls + 'px'; }

// Crisp text with options. x,y is the anchor; returns measured width.
function text(g, s, x, y, o = {}) {
  g.save();
  setFont(g, o.font ?? FONT.impact(120), o.ls ?? 0);
  g.textAlign = o.align ?? 'left'; g.textBaseline = o.base ?? 'alphabetic';
  g.globalAlpha = o.alpha ?? 1;
  g.translate(x, y); if (o.rot) g.rotate(o.rot); if (o.sx || o.sy) g.scale(o.sx ?? 1, o.sy ?? o.sx ?? 1);
  if (o.stroke) { g.lineWidth = o.stroke; g.strokeStyle = P[o.strokeCol] || o.strokeCol || P.night; g.lineJoin = 'round'; g.strokeText(s, 0, 0); }
  if (o.outline) { g.lineWidth = o.outline; g.strokeStyle = P[o.col] || o.col || P.white; g.strokeText(s, 0, 0); }
  else { g.fillStyle = P[o.col] || o.col || P.white; g.fillText(s, 0, 0); }
  const w = g.measureText(s).width;
  g.restore();
  return w;
}
function measure(g, s, font, ls = 0) { g.save(); setFont(g, font, ls); const w = g.measureText(s).width; g.restore(); return w; }

// Letter-by-letter drawing with per-letter transforms: fn(i, ch) → {dx, dy, rot, alpha, s}
function letters(g, s, x, y, font, col, fn, o = {}) {
  g.save(); setFont(g, font, o.ls ?? 0); g.textBaseline = o.base ?? 'alphabetic'; g.fillStyle = P[col] || col;
  const total = g.measureText(s).width;
  let x0 = o.align === 'center' ? x - total / 2 : o.align === 'right' ? x - total : x;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i], pre = g.measureText(s.slice(0, i)).width, cw = g.measureText(ch).width;
    const T = fn(i, ch) || {}; if ((T.alpha ?? 1) <= 0) continue;
    g.save(); g.globalAlpha = (o.alpha ?? 1) * (T.alpha ?? 1);
    g.translate(x0 + pre + cw / 2 + (T.dx ?? 0), y + (T.dy ?? 0)); g.rotate(T.rot ?? 0); g.scale(T.s ?? 1, T.s ?? 1);
    g.textAlign = 'center'; g.fillText(ch, 0, 0);
    g.restore();
  }
  g.restore(); return total;
}

// Type goes on its own layer so it can be grained (pencil sits on the tooth; type is printed ink on top).
function typeLayer() { return layer(6); }
function typeFlush(L, drawIdx, grain = .5) {
  if (grain > 0) {
    const g = L.g, pat = g.createPattern(TOOTH_LIGHT, 'repeat');
    const tb = TOOTH_BOIL ? drawIdx : 0; pat.setTransform(new DOMMatrix([1, 0, 0, 1, Math.floor(hash(tb * 3 + 11) * 512), Math.floor(hash(tb * 3 + 12) * 512)]));
    g.save(); g.globalCompositeOperation = 'destination-in'; g.globalAlpha = 1; g.fillStyle = pat;
    // blend: draw the tooth partially so grain strength is controllable
    g.fillRect(0, 0, W, H); g.restore();
  }
  G.drawImage(L.c, 0, 0);
}

// A pencil-hatched word: letters filled with strokes (used for BURNING GOLD, HOLD ON, HOME).
function hatchedText(s, x, y, font, o = {}) {
  const M = layer(7), S = layer(8);
  M.g.save(); setFont(M.g, font, o.ls ?? 0); M.g.textAlign = o.align ?? 'left'; M.g.textBaseline = o.base ?? 'alphabetic'; M.g.fillStyle = '#fff';
  M.g.translate(x, y); if (o.rot) M.g.rotate(o.rot); if (o.s) M.g.scale(o.s, o.s); M.g.fillText(s, 0, 0);
  const w = M.g.measureText(s).width; M.g.restore();
  const pen = new Pen(), seed = o.seed ?? 3, cols = o.cols ?? ['gold', 'orange', 'white'];
  const size = parseFloat(font.match(/(\d+)px/)[1]) * (o.s ?? 1);
  const x0 = (o.align === 'center' ? x - w / 2 : o.align === 'right' ? x - w : x) - 20, x1 = x0 + w + 40, y0 = y - size * 1.05, y1 = y + size * .15;
  const sp = o.spacing ?? 4.5, ang = o.angle ?? -0.9, L = o.len ?? 22;
  for (let yy = y0; yy < y1; yy += sp) for (let xx = x0; xx < x1; xx += sp) {
    const h = hash3(xx | 0, yy | 0, seed); if (h > (o.density ?? .85)) continue;
    const c = cols[Math.floor(hash3(xx | 0, yy | 0, seed + 1) * cols.length)];
    const js = o.jseed, jx = js !== undefined ? (hash3(xx | 0, yy | 0, js * 5 + 21) - .5) * (o.jit ?? 1.4) : 0, jy = js !== undefined ? (hash3(xx | 0, yy | 0, js * 5 + 22) - .5) * (o.jit ?? 1.4) : 0;
    const X = xx + (hash3(xx | 0, yy | 0, seed + 2) - .5) * sp + jx, Y = yy + (hash3(xx | 0, yy | 0, seed + 3) - .5) * sp + jy;
    pen.l(X - Math.cos(ang) * L / 2, Y - Math.sin(ang) * L / 2, X + Math.cos(ang) * L / 2, Y + Math.sin(ang) * L / 2, c, o.w ?? 2, o.a ?? .9);
  }
  pen.flush(S.g);
  S.g.globalCompositeOperation = 'destination-in'; S.g.drawImage(M.c, 0, 0); S.g.globalCompositeOperation = 'source-over';
  if (o.edge) { // pencil outline around the letters
    S.g.save(); setFont(S.g, font, o.ls ?? 0); S.g.textAlign = o.align ?? 'left'; S.g.textBaseline = o.base ?? 'alphabetic';
    S.g.translate(x, y); if (o.rot) S.g.rotate(o.rot); if (o.s) S.g.scale(o.s, o.s);
    S.g.strokeStyle = P[o.edge] || o.edge; S.g.globalAlpha = .8; S.g.lineWidth = 2; S.g.strokeText(s, 0, 0); S.g.globalAlpha = .4; S.g.strokeText(s, 1.5, -1); S.g.restore();
  }
  toothIn(S, (o.drawIdx ?? 0) + 99);
  G.globalAlpha = o.alpha ?? 1; G.drawImage(S.c, 0, 0); G.globalAlpha = 1;
  return w;
}

// Telemetry line (mono), optionally typed on over `dur` seconds from `t0`.
function tele(g, s, x, y, t, t0, o = {}) {
  const dur = o.dur ?? .5;
  const n = o.instant ? s.length : Math.floor(clamp((t - t0) / dur) * s.length);
  if (n <= 0) return;
  const shown = s.slice(0, n) + (n < s.length && frac(t * 4) < .5 ? '▌' : '');
  const font = FONT.mono(o.size ?? 22, o.weight ?? 400), style = { font, col: o.col ?? 'silver', alpha: o.alpha ?? .85, ls: o.ls ?? 1.5, align: o.align };
  if (!o.wrap) { text(g, shown, x, y, style); return; }
  // wrap on the full line's word breaks so the layout does not jump while typing
  const lines = []; let cur = '';
  for (const w of s.split(' ')) { const tryL = cur ? cur + ' ' + w : w; if (cur && measure(g, tryL, font, o.ls ?? 1.5) > o.wrap) { lines.push(cur); cur = w; } else cur = tryL; }
  lines.push(cur);
  let k = 0;
  lines.forEach((ln, j) => { const part = shown.slice(k, k + ln.length + (j < lines.length - 1 ? 0 : 2)); k += ln.length + 1; if (part) text(g, part, x, y + j * (o.size ?? 22) * 1.35, style); });
}

// Subtitle for story passages: serif italic, lower third, word-by-word fade.
function subtitle(g, line, t, o = {}) {
  if (!line || t < line.t0 - .2 || t > line.t1 + .3) return;
  if (o.split) { // a line crossing a split page changes pencil where it crosses: graphite on white paper, cream on black
    const { x: sx, left, right } = o.split;
    for (const [x0, x1, col] of [[0, sx, left], [sx, W, right]]) {
      g.save(); g.beginPath(); g.rect(x0, 0, x1 - x0, H); g.clip();
      subtitle(g, line, t, { ...o, split: null, col, shadow: col === 'graphite' ? 0 : (o.shadow ?? 0) });
      g.restore();
    }
    return;
  }
  const size = o.size ?? 54, y = o.y ?? H - 96;
  const fade = clamp((t - line.t0 + .2) / .25) * clamp((line.t1 + .3 - t) / .3);
  const words = line.text.split(' ');
  g.save(); setFont(g, FONT.serif(size)); const total = g.measureText(line.text).width; g.restore();
  let x = (o.x ?? W / 2) - total / 2;
  words.forEach((w, i) => {
    const wt = line.words[Math.min(i, line.words.length - 1)][0];
    const k = clamp((t - wt + .05) / .18);
    const ww = measure(g, w + ' ', FONT.serif(size));
    text(g, w, x, y + (1 - k) * 8, { font: FONT.serif(size), col: o.col ?? 'cream', alpha: fade * (.25 + .75 * k), stroke: o.shadow ?? 0 });
    x += ww;
  });
}
