// hud.js: the nightmare's UI — chess-engine eval bar, ATTEMPT counter, search tree with pruned ✗ leaves,
// move annotations (?!, ??, !!), classification banners, rewind transport (◀◀, ×N badge, timecode).
// Symbols (✗ ◀ ▶ − ∎ ∴ ‖ ×) come from the DejaVu Sans Mono symbol subset registered under the JBM family.
// Legibility floor (phone, muted): mono cap-height ≥ 30 px at 1080p (JetBrains Mono cap ≈ 0.73 em → ≥ 42 px font),
// key items ≥ 40 px cap (≥ 56 px font). Fewer elements, larger.
import { DW, DH, PAL, clamp, lerp, inv, smooth, easeOutCubic, easeOutExpo, hash, hsig, rng, rgba, fin, timecode } from './core.js';
import { F, setFont, redactedLine } from './type.js';
import { AGENCY } from './agency.js';

// ✗ as two brush-ish strokes
export function cross(g, x, y, r, col = PAL.red, lw = null, u = 1) {
  g.save(); g.strokeStyle = col; g.lineWidth = lw ?? Math.max(1.5, r * 0.28); g.lineCap = 'butt';
  const a = clamp(u * 2), b = clamp(u * 2 - 1);
  g.beginPath(); g.moveTo(x - r, y - r); g.lineTo(x - r + 2 * r * a, y - r + 2 * r * a);
  if (b > 0) { g.moveTo(x + r, y - r); g.lineTo(x + r - 2 * r * b, y - r + 2 * r * b); }
  g.stroke(); g.restore();
}
// ◀◀ (or ▶▶) transport glyph
export function transport(g, x, y, h, col, dir = -1, n = 2) {
  g.save(); g.fillStyle = col;
  for (let i = 0; i < n; i++) {
    const ox = x + dir * i * h * 0.78;
    g.beginPath(); g.moveTo(ox + dir * h * 0.0, y); g.lineTo(ox - dir * h * 0.85, y - h / 2); g.lineTo(ox - dir * h * 0.85, y + h / 2); g.closePath();
    g.fill();
  }
  g.restore();
}

export const MONO_MIN = 42, MONO_KEY = 56;
export function glyph(g, ch, x, y, px, col, w = 700) { g.save(); setFont(g, F.mono(px, w)); g.fillStyle = col; g.textBaseline = 'middle'; g.textAlign = 'center'; g.fillText(ch, x, y); g.restore(); }

// ---- chess-engine evaluation bar (left edge) ----
// value: pawns from Jade's side (+ good). mate: if set (e.g. -1) shows "−#1" and the bar empties.
export function evalBar(g, o) {
  const x = o.x ?? 44, y0 = o.y ?? 250, h = o.h ?? 700, w = o.w ?? 20, a = o.alpha ?? 1;
  const v = fin(o.value, 0), mate = o.mate;
  const p = o.inf ? 1 : mate != null ? (mate > 0 ? 1 : 0) : clamp(0.5 + Math.atan(v / 2.2) / Math.PI);   // share of the bar that is "hers"
  g.save();
  g.fillStyle = rgba('#000000', 0.92 * a); g.fillRect(x, y0, w, h);
  g.strokeStyle = rgba(PAL.boneDim, 0.7 * a); g.lineWidth = 2; g.strokeRect(x - 1, y0 - 1, w + 2, h + 2);
  const hb = h * p; g.fillStyle = rgba(PAL.bone, a); g.fillRect(x, y0 + h - hb, w, hb);
  g.fillStyle = rgba(PAL.red, a); g.fillRect(x + w + 3, y0 + h / 2 - 1, 8, 3);    // zero tick
  const label = o.inf ? '+∞' : mate != null ? `${mate < 0 ? '−' : '+'}#${Math.abs(mate)}` : `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`;
  setFont(g, F.mono(o.size ?? MONO_KEY, 700), 0); g.textBaseline = 'alphabetic';
  g.fillStyle = mate != null && mate < 0 ? rgba(PAL.red, a) : rgba(o.ink ? PAL.ink : PAL.bone, a);
  g.fillText(label, x - 6, y0 - 26);
  g.restore();
}

// ---- ATTEMPT counter (top right): "ATTEMPT 01", ✗ when failed ----
export function attempt(g, o) {
  const n = o.n ?? 1, x = o.x ?? DW - 64, y = o.y ?? 100, a = o.alpha ?? 1;
  g.save(); g.textBaseline = 'alphabetic'; g.textAlign = 'right';
  const fg = o.ink ? PAL.ink : PAL.bone, dim = o.ink ? PAL.ink : PAL.boneDim;
  setFont(g, F.mono(o.size ?? 64, 700), 1); g.fillStyle = rgba(fg, a);
  const s = String(n).padStart(2, '0'); g.fillText(s, x, y); const nw = g.measureText(s).width;
  setFont(g, F.mono(MONO_MIN, 400), 2); g.fillStyle = rgba(dim, 0.95 * a); g.fillText(o.label ?? 'ATTEMPT', x - nw - 18, y);
  const lw = g.measureText(o.label ?? 'ATTEMPT').width;
  if (o.failed) { setFont(g, F.mono(64, 700)); g.fillStyle = rgba(PAL.red, a * clamp(o.failed * 1.5)); g.fillText('✗', x - nw - lw - 40, y); }
  if (o.sub) { setFont(g, F.mono(MONO_MIN, 700), 2); g.fillStyle = rgba(o.subColor || PAL.red, a); g.fillText(o.sub, x, y + 58); }
  g.restore();
}

// ---- move annotation: "1. pull over" + "?!" ----
const NAG_COL = { '?!': PAL.sodium, '?': PAL.sodium, '??': PAL.red, '!!': PAL.cyan, '!': PAL.bone };
export function annotation(g, o) {
  const a = o.alpha ?? 1, x = o.x, y = o.y, px = o.size ?? 50;
  g.save(); g.textBaseline = 'alphabetic';
  setFont(g, F.mono(px, 400), 1); g.fillStyle = rgba(o.ink ? PAL.ink : PAL.bone, a);
  const mv = `${o.n ?? 1}. ${o.move}`; g.fillText(mv, x, y);
  const w = g.measureText(mv).width;
  if (o.nag) { setFont(g, F.mono(px * 1.15, 700), 0); g.fillStyle = rgba(NAG_COL[o.nag] || PAL.bone, a); g.fillText(o.nag, x + w + 10, y); }
  g.restore();
}

// ---- the agency's classification banner ----
export function agencyBanner(g, o = {}) {
  const a = o.alpha ?? 1, y = o.y ?? 52;
  g.save(); g.textBaseline = 'middle'; g.textAlign = 'center';
  setFont(g, F.mono(o.size ?? MONO_MIN, 700), 4); g.fillStyle = rgba(o.color || PAL.boneDim, a);
  g.fillText(o.text ?? AGENCY.classif, DW / 2, y);
  g.restore();
}

// ---- rewind transport HUD: ◀◀ REWIND ×4 · timecode running backwards ----
export function rewindHud(g, o) {
  const a = o.alpha ?? 1, x = o.x ?? 90, y = o.y ?? 130;
  g.save(); g.textBaseline = 'alphabetic';
  setFont(g, F.mono(64, 700), 0); g.fillStyle = rgba(PAL.cyan, a); g.fillText('◀◀', x, y);
  let cx = x + g.measureText('◀◀').width + 22;
  setFont(g, F.mono(64, 700), 6); g.fillText('REWIND', cx, y); cx += g.measureText('REWIND').width + 34;
  const sp = `×${o.speed ?? 2}`; setFont(g, F.mono(64, 700), 0);
  const bw = g.measureText(sp).width + 30;
  g.fillRect(cx, y - 58, bw, 74); g.fillStyle = PAL.ink; g.fillText(sp, cx + 15, y);
  setFont(g, F.mono(60, 400), 1); g.fillStyle = rgba(PAL.cyan, a);
  g.textAlign = 'right'; g.fillText(timecode(o.tc ?? 0), DW - 80, y);
  g.restore();
}

// ---- search tree ----
// A procedural game tree: root at (x,y), depth levels to the right. Every leaf but those on `line` is pruned (✗).
// progress 0..1 grows it breadth-first; lit (0..1) lights the surviving line. Labels: optional move names per depth.
export function buildTree(seed, depth = 5, maxKids = 3, line = null) {
  const R = rng(seed); const nodes = [{ d: 0, parent: -1, kids: [], i: 0 }];
  const q = [0];
  while (q.length) {
    const id = q.shift(), n = nodes[id]; if (n.d >= depth) continue;
    const k = n.d === 0 ? 3 : 1 + Math.floor(R() * maxKids * (1 - n.d / (depth + 2)) + R() * 0.8);
    for (let j = 0; j < k; j++) { const c = { d: n.d + 1, parent: id, kids: [], i: nodes.length, r: R() }; nodes.push(c); n.kids.push(c.i); q.push(c.i); }
  }
  // surviving line: follow `line` child indices (or the last child) to a leaf
  const alive = new Set([0]); let cur = 0, dd = 0;
  while (nodes[cur].kids.length) { const ks = nodes[cur].kids; cur = ks[line ? Math.min(ks.length - 1, line[dd] ?? ks.length - 1) : ks.length - 1]; alive.add(cur); dd++; }
  // layout: leaves get evenly spaced rows; parents centred over children
  let row = 0; const place = id => { const n = nodes[id]; if (!n.kids.length) { n.row = row++; return n.row; } const rs = n.kids.map(place); n.row = (rs[0] + rs[rs.length - 1]) / 2; return n.row; };
  place(0);
  return { nodes, alive, rows: row, depth, leaf: cur };
}
export function searchTree(g, T, o) {
  const x = o.x ?? 1200, y = o.y ?? 540, W = o.w ?? 620, H = o.h ?? 760, prog = clamp(o.progress ?? 1), lit = clamp(o.lit ?? 0), a = o.alpha ?? 1;
  const { nodes, alive, rows, depth } = T;
  const P = n => [x + (n.d / depth) * W, y - H / 2 + (rows <= 1 ? .5 : n.row / (rows - 1)) * H];
  const grow = prog * (depth + 1);  // depth levels revealed so far (fractional)
  g.save(); g.lineCap = 'round';
  for (const n of nodes) {
    if (n.parent < 0) continue;
    const u = clamp(grow - n.d + 1 - (n.r ?? 0) * 0.35);
    if (u <= 0) continue;
    const p0 = P(nodes[n.parent]), p1 = P(n);
    const mx = p0[0] + (p1[0] - p0[0]) * 0.45;
    const isLit = alive.has(n.i);
    g.strokeStyle = isLit && lit > 0 ? rgba(o.litColor || (o.ink ? PAL.ink : PAL.bone), a * lerp(0.6, 1, lit)) : rgba(o.ink ? PAL.ink : PAL.boneDim, a * (o.ink ? 0.8 : 0.75));
    g.lineWidth = (isLit && lit > 0 ? lerp(3, 6, lit) : 3) * (o.ink ? 1.4 : 1);
    if (o.elbow) {   // elbow connector (bracket look), partially drawn by u
      const L1 = mx - p0[0], L2 = Math.abs(p1[1] - p0[1]), L3 = p1[0] - mx, Lt = L1 + L2 + L3, s = u * Lt;
      g.beginPath(); g.moveTo(p0[0], p0[1]);
      if (s <= L1) g.lineTo(p0[0] + s, p0[1]);
      else if (s <= L1 + L2) { g.lineTo(mx, p0[1]); g.lineTo(mx, p0[1] + Math.sign(p1[1] - p0[1]) * (s - L1)); }
      else { g.lineTo(mx, p0[1]); g.lineTo(mx, p1[1]); g.lineTo(mx + (s - L1 - L2), p1[1]); }
      g.stroke();
    } else {         // game-tree look: straight edges fanning out from each node
      g.beginPath(); g.moveTo(p0[0], p0[1]); g.lineTo(lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u)); g.stroke();
    }
    if (u >= 1) {
      if (!n.kids.length && !alive.has(n.i)) {
        const st = clamp((grow - n.d - (n.r ?? 0) * 0.35) * 2.2);
        if (st > 0) glyph(g, '✗', p1[0] + 22, p1[1], o.leafSize ?? 40, rgba(PAL.red, a * clamp(st * 1.5)));
      } else { g.fillStyle = o.ink ? PAL.ink : isLit && lit > 0 ? rgba(PAL.bone, a) : rgba(PAL.boneDim, a * 0.8); g.beginPath(); g.arc(p1[0], p1[1], n.d === 1 ? 9 : 5, 0, Math.PI * 2); g.fill(); }
    }
  }
  const r0 = P(nodes[0]); g.fillStyle = o.ink ? PAL.ink : rgba(PAL.bone, a); g.fillRect(r0[0] - 8, r0[1] - 8, 16, 16);
  if (o.labels) {
    setFont(g, F.mono(o.labelSize ?? 48, 700), 0); g.textBaseline = 'alphabetic';
    for (const lb of o.labels) {
      const n = nodes[lb.node]; if (!n) continue; const p = P(n);
      if (grow - n.d < 0.6) continue;
      g.fillStyle = rgba(lb.color || (o.ink ? PAL.ink : PAL.bone), a * clamp((grow - n.d - 0.6) * 3));
      g.fillText(lb.text, p[0] + 22, p[1] - 22);
    }
  }
  g.restore();
  return { P };
}

// ---- ANOMALY meter: the agency detects every rewind. Spikes at each rewind start (escalating), decays slowly; in the
// final drop she never rewinds, so it drains to "ANOMALY: NONE DETECTED". T.rewindStarts is set by the engine at boot.
const AMPS = [0.62, 0.8, 0.95, 1];
export function anomaly(T, t) {
  const st = (T && T.rewindStarts) || []; let v = 0;
  st.forEach((s, i) => { if (t >= s) v = Math.max(v, AMPS[Math.min(i, AMPS.length - 1)] * smooth(0, 0.25, t - s) * Math.exp(-(t - s) / 38)); });
  const fd = T && T.opt ? T.opt(T => T.section('final_drop').start, 171.3) : 171.3;
  return v * (1 - smooth(fd, fd + 6.5, t));
}
export function anomalySpike(T, t) {   // 1 right at a rewind start → 0 over a few seconds (amber glints, meter flash)
  let k = 0; for (const s of (T && T.rewindStarts) || []) if (t >= s) k = Math.max(k, Math.exp(-(t - s) / 2.5)); return k;
}
export function anomalyMeter(g, t, T, o = {}) {
  const x = o.x ?? 96, y = o.y ?? 162, a = o.alpha ?? 1, ink = o.ink, fd = T.opt ? T.opt(T => T.section('final_drop').start, 171.3) : 171.3;
  const v = anomaly(T, t), sp = anomalySpike(T, t), col = ink ? PAL.ink : PAL.amber;
  g.save(); g.globalAlpha = a; g.textBaseline = 'alphabetic';
  redactedLine(g, AGENCY.mark, x, y, F.mono(MONO_MIN, 700), col, col);
  setFont(g, F.mono(MONO_MIN, 700), 1); let cx = x + g.measureText(AGENCY.mark.map(p => typeof p === 'string' ? p : 'M').join(' ')).width + 30;
  if (t >= fd + 5) {   // the payoff: calm, mono, bone
    setFont(g, F.mono(MONO_MIN, 400), 2); g.fillStyle = rgba(ink ? PAL.ink : PAL.bone, clamp((t - fd - 5) * 1.5)); g.fillText('ANOMALY: NONE DETECTED', cx, y);
  } else {
    const n = 10, sw = 22, sh = 32, gap = 6, lit = v * n;
    for (let i = 0; i < n; i++) {
      const f = clamp(lit - i), bx = cx + i * (sw + gap);
      g.strokeStyle = rgba(col, 0.55); g.lineWidth = 2; g.strokeRect(bx, y - sh + 2, sw, sh);
      if (f > 0) { g.fillStyle = rgba(i >= 7 ? PAL.red : col, f * (0.75 + 0.25 * sp)); g.fillRect(bx + 3, y - sh + 5, sw - 6, sh - 6); }
    }
    if (sp > 0.3) { setFont(g, F.mono(MONO_MIN, 700), 2); g.fillStyle = rgba(col, clamp((sp - 0.3) * 2) * (0.6 + 0.4 * Math.sin(t * 30))); g.fillText('ANOMALY', cx + n * (sw + gap) + 18, y); }
  }
  g.restore();
}

// ---- global HUD overlay (the proof's UI): ATTEMPT top-left, eval bar left edge, timecode top-right ----
// shot.hud = {attempt, failed, eval: v | [v0, v1], mate, tc (true | 'song' | number offset), alpha, label}
export function hudOverlay(g, t, shot, T) {
  const h = shot.hud, a = h.alpha ?? 1, lt = t - shot.t0, u = clamp(lt / Math.max(0.001, shot.t1 - shot.t0));
  if (h.attempt != null) {
    g.save(); g.textBaseline = 'alphabetic';
    setFont(g, F.mono(MONO_MIN, 400), 2); g.fillStyle = rgba(h.ink ? PAL.ink : PAL.boneDim, a); g.fillText(h.label ?? 'ATTEMPT', 96, 96);
    const lw = g.measureText(h.label ?? 'ATTEMPT').width;
    setFont(g, F.mono(64, 700), 1); g.fillStyle = rgba(h.ink ? PAL.ink : PAL.bone, a);
    const n = typeof h.attempt === 'function' ? h.attempt(t) : h.attempt;
    g.fillText(String(n).padStart(2, '0'), 96 + lw + 18, 96);
    if (h.failed || h.ok) { const nw = g.measureText(String(n).padStart(2, '0')).width; g.fillStyle = rgba(h.ok ? PAL.cyan : PAL.red, a); g.fillText(h.ok ? '✓' : '✗', 96 + lw + 30 + nw, 96); }
    g.restore();
  }
  if (h.attempt != null && h.anomaly !== false) anomalyMeter(g, t, T, { ink: h.ink, alpha: a });
  if (h.eval != null || h.mate != null) {
    const v = Array.isArray(h.eval) ? lerp(h.eval[0], h.eval[1], u * u) : typeof h.eval === 'function' ? h.eval(t) : h.eval;
    evalBar(g, h.mate != null && (h.mateAt == null || lt >= h.mateAt) ? { mate: h.mate, alpha: a, ink: h.ink } : { value: v, alpha: a, inf: v === Infinity, ink: h.ink });
  }
  if (h.tc) {
    let tcT = typeof h.tc === 'number' ? t + h.tc : t;
    const rwA = shot.params && shot.params.rwA;
    if (rwA != null) {   // inside a rewind the timecode runs BACKWARDS: fast, kick-stepped (each kick knocks it back further)
      const nk = T && T.kicksIn ? T.kicksIn(rwA, t + 1e-6).length : 0;
      tcT = Math.max(0, rwA - (t - rwA) * 4 - nk * 0.75);
    }
    g.save(); setFont(g, F.mono(46, 400), 1); g.fillStyle = rgba(h.ink ? PAL.ink : rwA != null ? PAL.cyan : PAL.boneDim, a); g.textAlign = 'right'; g.textBaseline = 'alphabetic';
    g.fillText((rwA != null ? '\u25c0\u25c0 ' : '') + timecode(tcT), DW - 72, 96); g.restore();
  }
  // corner tag after each world card: TIMESTREAM 2010 · ITERATION 0N (small, beside the eval label)
  const it = T && T.iterations ? T.iterations.find(r => t >= r.t0 && t < r.t1) : null;
  if (it && h.iterTag !== false) {
    g.save(); setFont(g, F.mono(MONO_MIN, 400), 1); g.textBaseline = 'alphabetic'; g.fillStyle = rgba(h.ink ? PAL.ink : PAL.boneDim, a * 0.85);
    g.fillText(`TIMESTREAM 2010 \u00b7 ITERATION ${String(it.n).padStart(2, '0')}`, 250, 224); g.restore();
  }
  // final drop: the coin never lands tails — HEADS k/k beside the meter (from the first chop on)
  if (T && T.heads && T.heads.length && t >= T.heads[0] && h.attempt != null) {
    let k = 0; for (const c of T.heads) if (t >= c) k++;
    const n = Math.max(1, Math.round(k / T.heads.length * 64));
    g.save(); setFont(g, F.mono(MONO_MIN, 700), 2); g.textBaseline = 'alphabetic'; g.fillStyle = rgba(h.ink ? PAL.ink : PAL.cyan, a);
    g.fillText(`HEADS ${n}/${n}`, 96, 286); g.restore();
  }
}
