// hud.js: the nightmare's UI — chess-engine eval bar, ATTEMPT counter, search tree with pruned ✗ leaves,
// move annotations (?!, ??, !!), FOIA banners, rewind transport (◀◀, ×N badge, timecode). Vector glyphs only
// (no reliance on font coverage for ✗ ◀ etc.).
import { DW, DH, PAL, clamp, lerp, inv, smooth, easeOutCubic, easeOutExpo, hash, hsig, rng, rgba, fin, timecode } from './core.js';
import { F, setFont } from './type.js';

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

// ---- chess-engine evaluation bar (left edge) ----
// value: pawns from Jade's side (+ good). mate: if set (e.g. -1) shows "−#1" and the bar empties.
export function evalBar(g, o) {
  const x = o.x ?? 46, y0 = o.y ?? 150, h = o.h ?? 780, w = o.w ?? 12, a = o.alpha ?? 1;
  const v = fin(o.value, 0), mate = o.mate;
  const p = mate != null ? (mate > 0 ? 1 : 0) : clamp(0.5 + Math.atan(v / 2.2) / Math.PI);   // share of the bar that is "hers"
  g.save();
  g.fillStyle = rgba('#000000', 0.9 * a); g.fillRect(x, y0, w, h);
  g.strokeStyle = rgba(PAL.boneDim, 0.5 * a); g.lineWidth = 1; g.strokeRect(x - 0.5, y0 - 0.5, w + 1, h + 1);
  const hb = h * p; g.fillStyle = rgba(PAL.bone, a); g.fillRect(x, y0 + h - hb, w, hb);
  g.fillStyle = rgba(PAL.boneDim, 0.7 * a); g.fillRect(x - 4, y0 + h / 2, 4, 1);    // zero tick
  const label = mate != null ? `${mate < 0 ? '−' : '+'}#${Math.abs(mate)}` : `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`;
  setFont(g, F.mono(17, 700), 0.5); g.textBaseline = 'alphabetic';
  g.fillStyle = mate != null && mate < 0 ? rgba(PAL.red, a) : rgba(PAL.bone, a);
  g.fillText(label, x - 4, y0 - 14);
  if (o.caption) { setFont(g, F.mono(12), 2); g.fillStyle = rgba(PAL.boneDim, 0.8 * a); g.save(); g.translate(x + w + 16, y0 + h); g.rotate(-Math.PI / 2); g.fillText(o.caption, 0, 0); g.restore(); }
  g.restore();
}

// ---- ATTEMPT counter (top right) ----
export function attempt(g, o) {
  const n = o.n ?? 1, x = o.x ?? DW - 72, y = o.y ?? 96, a = o.alpha ?? 1;
  g.save(); g.textBaseline = 'alphabetic'; g.textAlign = 'right';
  setFont(g, F.mono(14), 3); g.fillStyle = rgba(PAL.boneDim, 0.9 * a); g.fillText(o.label ?? 'ATTEMPT', x, y - 34);
  setFont(g, F.mono(o.size ?? 40, 700), 2); g.fillStyle = rgba(PAL.bone, a);
  const s = String(n).padStart(2, '0'); g.fillText(s, x, y);
  if (o.failed) { const w = g.measureText(s).width; cross(g, x - w - 34, y - 15, 13, PAL.red, 4, o.failed); }
  if (o.sub) { setFont(g, F.mono(13), 1.5); g.fillStyle = rgba(PAL.boneDim, 0.75 * a); g.fillText(o.sub, x, y + 26); }
  g.restore();
}

// ---- move annotation: "1. pull over" + "?!" ----
const NAG_COL = { '?!': PAL.sodium, '?': PAL.sodium, '??': PAL.red, '!!': PAL.cyan, '!': PAL.bone };
export function annotation(g, o) {
  const a = o.alpha ?? 1, x = o.x, y = o.y;
  g.save(); g.textBaseline = 'alphabetic';
  setFont(g, F.mono(o.size ?? 26, 400), 1); g.fillStyle = rgba(PAL.bone, a);
  const mv = `${o.n ?? 1}. ${o.move}`; g.fillText(mv, x, y);
  const w = g.measureText(mv).width;
  if (o.nag) { setFont(g, F.mono((o.size ?? 26) * 1.1, 700), 0); g.fillStyle = rgba(NAG_COL[o.nag] || PAL.bone, a); g.fillText(o.nag, x + w + 6, y); }
  g.restore();
}

// ---- FOIA / classification banner ----
export function foiaBanner(g, o = {}) {
  const a = o.alpha ?? 1, y = o.y ?? 34;
  g.save(); g.textBaseline = 'middle'; g.textAlign = 'center';
  setFont(g, F.mono(14, 700), 4); g.fillStyle = rgba(o.color || PAL.boneDim, a);
  g.fillText(o.text ?? 'UNCLASSIFIED//FOR OFFICIAL USE ONLY', DW / 2, y);
  if (o.case) { g.textAlign = 'left'; setFont(g, F.mono(13), 1.5); g.fillText(o.case, 72, y); }
  if (o.page) { g.textAlign = 'right'; setFont(g, F.mono(13), 1.5); g.fillText(o.page, DW - 72, y); }
  g.restore();
}

// ---- rewind transport HUD: ◀◀ REWIND  ×4  ·  timecode running backwards ----
export function rewindHud(g, o) {
  const a = o.alpha ?? 1, x = o.x ?? 120, y = o.y ?? 120;
  g.save(); g.textBaseline = 'alphabetic';
  transport(g, x + 26, y - 18, 34, rgba(PAL.cyan, a), -1, 2);
  setFont(g, F.mono(30, 700), 6); g.fillStyle = rgba(PAL.cyan, a); g.fillText('REWIND', x + 70, y - 6);
  const sp = `×${o.speed ?? 2}`; setFont(g, F.mono(30, 700), 1);
  const bx = x + 290, bw = g.measureText(sp).width + 22;
  g.fillStyle = rgba(PAL.cyan, a); g.fillRect(bx, y - 36, bw, 40); g.fillStyle = PAL.ink; g.fillText(sp, bx + 11, y - 6);
  setFont(g, F.mono(26, 400), 2); g.fillStyle = rgba(PAL.cyan, a * 0.9);
  g.textAlign = 'right'; g.fillText(timecode(o.tc ?? 0), DW - 110, y - 6);
  setFont(g, F.mono(12), 3); g.fillStyle = rgba(PAL.cyan, a * 0.6); g.fillText(o.tcLabel ?? 'SRC TC', DW - 110, y - 46);
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
    g.strokeStyle = isLit && lit > 0 ? rgba(o.litColor || PAL.bone, a * lerp(0.35, 1, lit)) : rgba(PAL.boneDim, a * 0.38);
    g.lineWidth = isLit && lit > 0 ? lerp(1.2, 3, lit) : 1.1;
    // elbow connector (engine-tree look): horizontal, vertical, horizontal; partially drawn by u
    const L1 = mx - p0[0], L2 = Math.abs(p1[1] - p0[1]), L3 = p1[0] - mx, Lt = L1 + L2 + L3, s = u * Lt;
    g.beginPath(); g.moveTo(p0[0], p0[1]);
    if (s <= L1) g.lineTo(p0[0] + s, p0[1]);
    else if (s <= L1 + L2) { g.lineTo(mx, p0[1]); g.lineTo(mx, p0[1] + Math.sign(p1[1] - p0[1]) * (s - L1)); }
    else { g.lineTo(mx, p0[1]); g.lineTo(mx, p1[1]); g.lineTo(mx + (s - L1 - L2), p1[1]); }
    g.stroke();
    if (u >= 1) {
      if (!n.kids.length && !alive.has(n.i)) {
        const st = clamp((grow - n.d - (n.r ?? 0) * 0.35) * 2.2);
        if (st > 0) cross(g, p1[0] + 9, p1[1], 5.5, rgba(PAL.red, a * 0.95), 1.8, st);
      } else { g.fillStyle = isLit && lit > 0 ? rgba(PAL.bone, a) : rgba(PAL.boneDim, a * 0.7); g.fillRect(p1[0] - 2, p1[1] - 2, 4, 4); }
    }
  }
  const r0 = P(nodes[0]); g.fillStyle = rgba(PAL.bone, a); g.fillRect(r0[0] - 3, r0[1] - 3, 6, 6);
  if (o.labels) {
    setFont(g, F.mono(15), 1); g.textBaseline = 'alphabetic';
    for (const lb of o.labels) {
      const n = nodes[lb.node]; if (!n) continue; const p = P(n);
      if (grow - n.d < 0.6) continue;
      g.fillStyle = rgba(lb.color || PAL.bone, a * clamp((grow - n.d - 0.6) * 3));
      g.fillText(lb.text, p[0] + 10, p[1] - 8);
    }
  }
  g.restore();
  return { P };
}
