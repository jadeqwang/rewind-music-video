// layers.js: composable shot layers for the `comp` scene. A shot is a stack of layers drawn in order:
//   { id, t0, t1, scene: 'comp', params: { layers: [ {type, ...}, ... ] } }
// Any numeric layer field may be a function of env ({lt, t, u, dur, T, k (kick env), b (beat phase)}) for animation.
// Layers draw into ctx.g (scene: bloom/CA/grade) unless `onType: true` (type/HUD layer, crisp, after the grade).
import { DW, DH, PAL, clamp, lerp, inv, smooth, fract, easeOutCubic, easeInOutCubic, easeOutExpo, easeOutBack, hash, hsig, rng, rgba, layer, clearLayer, resetCtx, fin, noise1, timecode } from './core.js';
import { page as pageType, slam, subtitle, redact, redactedLine, revisions, setFont, F } from './type.js';
import * as V from './slams.js';
import { searchTree, buildTree, glyph, evalBar, annotation } from './hud.js';
import { sirens, sodiumSweep, sodiumWash, rain, bullet, headlights, fillInk } from './fx.js';
import * as CAR from './car.js';

export const A = (v, env, d) => (typeof v === 'function' ? v(env) : v ?? d);

// camera: {from:[u,v,s], to:[u,v,s], ease} → design rect for a full-frame roto (u,v = focus point 0..1, s = zoom)
export function camRect(cam, env) {
  if (!cam) return { x: 0, y: 0, w: DW, h: DH };
  const e = (cam.ease || easeInOutCubic)(clamp(env.u));
  const f = cam.from || [0.5, 0.5, 1], t = cam.to || f;
  const u = lerp(f[0], t[0], e), v = lerp(f[1], t[1], e), s = lerp(f[2], t[2], e);
  const w = DW * s, h = DH * s;
  return { x: DW / 2 - u * w + (cam.dx ?? 0), y: DH / 2 - v * h + (cam.dy ?? 0), w, h };
}
const words = (T, L, shot) => {
  let ws = L.words || [].concat(...(L.lines || []).map(i => T.lineWords(i)));
  if (L.from != null) ws = ws.filter(w => w.start >= L.from - 1e-6);
  if (L.until != null) ws = ws.filter(w => w.start < L.until);
  return ws.map(w => ({ ...w, note: L.notes && L.notes[w.key] }));
};

// ---------------------------------------------------------------------------------------------------------------
export const LAYERS = {
  fill(ctx, L, env) { const g = ctx.g; g.save(); g.globalAlpha = clamp(A(L.alpha, env, 1)); g.fillStyle = L.color || PAL.ink; g.fillRect(-10, -10, DW + 20, DH + 20); g.restore(); },

  // luminous world contours of a roto/base clip + its own lights; optional lake black-mirror (road reflected upside down)
  world(ctx, L, env, { roto }) {
    const id = L.roto, m = roto.meta(id); if (!m) return;
    const ct = roto.clipTime(id, env.lt, { speed: A(L.speed, env, 1), offset: A(L.offset, env, 0), loop: L.loop ?? true });
    const rect = camRect(L.cam, env);
    // paper: bone stock, ink lines (the file-photo inversion used as a recurring device)
    if (L.paper) { const g = ctx.g; g.fillStyle = PAL.bone; g.fillRect(-10, -10, DW + 20, DH + 20); }
    const draw = (g) => {
      roto.contours(g, id, ct, { color: L.paper ? PAL.ink : (L.color || PAL.bone), alpha: A(L.alpha, env, 0.95), rect, boil: ctx.seed, boilAmp: L.boilAmp ?? 1, fog: L.fog, double: L.double, comp: L.paper ? 'source-over' : L.comp, exclude: L.exclude ? id : null });
      const la = L.paper ? 0 : A(L.lights, env, 0.9); if (la > 0) roto.lights(g, id, ct, { rect, alpha: la });
    };
    if (!L.mirror) return draw(ctx.g);
    const Ly = layer('world_mirror', ctx.g.canvas.width, ctx.g.canvas.height), lg = clearLayer(Ly); lg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    draw(lg); resetCtx(lg);
    const g = ctx.g, y = A(L.mirror.y, env, 620), sy = y * ctx.S;
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'lighter';
    g.save(); g.beginPath(); g.rect(0, 0, Ly.width, sy); g.clip(); g.drawImage(Ly, 0, 0); g.restore();
    // reflection: flipped about the waterline, rippled in bands, fading
    g.globalAlpha = A(L.mirror.alpha, env, 0.45);
    const bands = 18, bh = (Ly.height - sy) / bands;
    for (let i = 0; i < bands; i++) {
      const y0 = sy + i * bh, srcY = sy - (i + 1) * bh, dx = Math.sin(env.t * 2 + i * 0.9) * (2 + i * 0.6) * ctx.S;
      g.globalAlpha = A(L.mirror.alpha, env, 0.45) * (1 - i / bands);
      g.save(); g.translate(dx, y0 + bh); g.scale(1, -1); g.drawImage(Ly, 0, Math.max(0, srcY), Ly.width, bh, 0, 0, Ly.width, bh); g.restore();
    }
    g.restore();
  },

  sirens(ctx, L, env) { sirens(ctx.g, env.T, env.t, { amount: A(L.amount, env, 1), side: L.side || 'pair', base: L.base ?? 0.35, peak: L.peak ?? 0.5, decay: L.decay ?? 1.8 }); },
  headlights(ctx, L, env) { headlights(ctx.g, A(L.x, env, DW / 2), A(L.y, env, 480), A(L.r, env, 1000), A(L.amount, env, 0.4), L.color || PAL.bone); },
  sodium(ctx, L, env) {
    const sw = sodiumSweep(env.t, { period: L.period ?? 0.92, amount: A(L.amount, env, 0.5) });
    sodiumWash(ctx.g, sw, L.alpha ?? 0.12);
    if (L.kick) { const k = env.k; if (k > 0.05) { const g = ctx.g; g.save(); g.globalCompositeOperation = 'source-over'; g.fillStyle = rgba(PAL.sodium, L.kick * 0.3 * k); g.fillRect(0, 0, DW, DH); g.restore(); } }
    env.sweep = sw;
  },
  kickflash(ctx, L, env) { const k = env.k; if (k < 0.03) return; const g = ctx.g; g.save(); g.globalCompositeOperation = L.comp || 'source-over'; g.fillStyle = rgba(L.color || PAL.bone, (L.amount ?? 0.2) * k); g.fillRect(0, 0, DW, DH); g.restore(); },
  flash(ctx, L, env) { const a = A(L.amount, env, 0); if (a <= 0) return; const g = ctx.g; g.save(); g.globalCompositeOperation = L.comp || 'lighter'; g.fillStyle = rgba(L.color || PAL.bone, a); g.fillRect(0, 0, DW, DH); g.restore(); },
  rain(ctx, L, env) { rain(ctx.g, ctx.boil, env.t * (L.slow ?? 1), { n: L.n ?? 140, alpha: A(L.alpha, env, 0.2) }); },

  // infinite streetlights receding to a vanishing point (visual Shepard tone): they never arrive
  streetlights(ctx, L, env) {
    const g = ctx.g, vx = L.vx ?? 1040, vy = L.vy ?? 470, n = L.n ?? 14, sp = A(L.speed, env, 1.2);
    g.save(); g.globalCompositeOperation = 'lighter';
    for (const side of L.sides || [-1, 1]) for (let i = 0; i < n; i++) {
      const z = fract(i / n + env.t * sp * 0.25), d = Math.pow(z, 2.4);   // 0 = horizon → 1 = passing
      const x = vx + side * d * (L.spread ?? 1500), y = vy - d * (L.rise ?? 520), r = 2 + d * 26;
      const a = smooth(0, 0.15, z) * (1 - smooth(0.9, 1, z));
      const gr = g.createRadialGradient(x, y, 0, x, y, r * 4); gr.addColorStop(0, rgba(PAL.sodium, a)); gr.addColorStop(0.25, rgba(PAL.sodium, a * 0.4)); gr.addColorStop(1, rgba(PAL.sodium, 0));
      g.fillStyle = gr; g.fillRect(x - r * 4, y - r * 4, r * 8, r * 8);
      g.fillStyle = rgba('#FFE2B0', a); g.beginPath(); g.arc(x, y, r * 0.35, 0, Math.PI * 2); g.fill();
    }
    g.restore();
  },
  speedlines(ctx, L, env) {
    const g = ctx.g, vx = L.vx ?? DW / 2, vy = L.vy ?? 480, n = L.n ?? 70, a = A(L.amount, env, 0.5);
    if (a <= 0) return;
    g.save(); g.strokeStyle = rgba(L.color || PAL.bone, a); g.lineWidth = 2; g.beginPath();
    for (let i = 0; i < n; i++) {
      const ang = hash(i, 1) * Math.PI * 2, ph = fract(hash(i, 2) + env.t * (1.5 + hash(i, 3) * 2)), r0 = 200 + ph * 1400, len = 60 + ph * 260;
      g.moveTo(vx + Math.cos(ang) * r0, vy + Math.sin(ang) * r0 * 0.6); g.lineTo(vx + Math.cos(ang) * (r0 + len), vy + Math.sin(ang) * (r0 + len) * 0.6);
    }
    g.stroke(); g.restore();
  },

  jade(ctx, L, env, { roto }) {
    const id = L.roto, m = roto.meta(id); if (!m) return;
    const ct = roto.clipTime(id, env.lt, { speed: L.speed ?? 1, offset: L.offset ?? 0, loop: L.loop ?? 'pingpong' });
    const rect = camRect(L.cam, env);
    const light = L.light === 'sodium' ? (env.sweep || sodiumSweep(env.t, { amount: 0.32 })) : L.light === 'siren'
      ? { color: (env.b.i & 1) ? PAL.blue : PAL.red, amount: 0.35 * Math.exp(-env.b.phase * 2), from: (env.b.i & 1) ? [DW, 0, DW * 0.3, 0] : [0, 0, DW * 0.7, 0] } : null;
    if (L.late && !roto.meta(id).faceData) {   // the ghost outline that moves a beat late (dream lag); stand-in only (real mattes have holes)
      const ct2 = roto.clipTime(id, env.lt - L.late, { speed: L.speed ?? 1, offset: L.offset ?? 0, loop: L.loop ?? 'pingpong' });
      roto.jade(ctx.g, id, ct2, { rect: { ...rect, x: rect.x + (L.lateDx ?? 26) }, ghost: true, ghostColor: L.lateColor || PAL.cyan, boil: ctx.seed, alpha: 0.75 });
    }
    if (roto.meta(id).layers.includes('cel') && !L.v1) { ctx.post.bloom = Math.min(ctx.post.bloom ?? 0.3, 0.1); }
    if (ctx.rewinding && !L.ghost) {   // time-immune (Braid's green shimmer): she keeps a cyan outline that ignores the rewind
      const sh = 0.55 + 0.45 * Math.sin(env.t * 21);
      roto.jade(ctx.g, id, ct, { rect, ghost: true, ghostColor: PAL.cyan, alpha: sh, v1: true });
    }
    roto.jade(ctx.g, id, ct, L.ghost ? { rect, ghost: true, ghostColor: L.ghostColor || PAL.cyan, boil: ctx.seed, alpha: A(L.alpha, env, 1) }
      : { rect, v1: L.v1, boil: ctx.seed, mouth: L.mouth === false ? 0 : clamp((env.T.e('vocal', env.t) - 0.18) * 1.6), light, rim: { color: L.rimColor || PAL.bone, alpha: 0.55, w: 1.4 }, alpha: A(L.alpha, env, 1) });
  },

  suits(ctx, L, env, { roto }) {
    const id = L.roto, m = roto.meta(id); if (!m) return;
    const ct = roto.clipTime(id, env.lt, { speed: A(L.speed, env, 1), offset: L.offset ?? 0, loop: L.loop ?? 'pingpong' });
    const rect = camRect(L.cam, env);
    const b = env.b, glint = L.glint != null ? A(L.glint, env) : ((b.i % 4 === 1) ? Math.exp(-b.phase * 5) : 0);
    roto.suits(ctx.g, id, ct, { rect, boil: ctx.seed, rimL: L.rimL ?? PAL.red, rimR: L.rimR ?? PAL.blue, rimAmt: 1, glint, glintSeed: b.i, barLabel: null, bars: L.bars });
  },

  // world contours of a base clip with the interim suits stand-in placed into it (until real mattes exist)
  bullet(ctx, L, env) { bullet(ctx.g, { x: A(L.x, env, 760), y: A(L.y, env, 470), len: L.len ?? 1100, angle: L.angle ?? 0.03, color: L.color, comp: L.comp }); },
  dot(ctx, L, env) { const g = ctx.g; g.fillStyle = L.color || PAL.bone; g.beginPath(); g.arc(A(L.x, env, DW / 2), A(L.y, env, DH / 2), A(L.r, env, 6), 0, Math.PI * 2); g.fill(); },

  // the rear-view mirror: an inset that shows its own layers (possibly at a different time: dream continuity)
  async mirror(ctx, L, env, data) {
    const [x, y, w, h] = L.rect || [560, 70, 800, 240];
    const Lm = layer('mirror_inner', ctx.g.canvas.width, ctx.g.canvas.height), mg = clearLayer(Lm); mg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    const sub = { ...ctx, g: mg };
    const env2 = { ...env, lt: env.lt + (L.timeOffset ?? 0), t: env.t + (L.timeOffset ?? 0) };
    await drawLayers(sub, L.layers || [], env2, data);
    resetCtx(mg);
    const g = ctx.g, r = h * 0.28;
    g.save();
    g.fillStyle = '#020203'; roundRect(g, x - 18, y - 18, w + 36, h + 36, r + 14); g.fill();
    roundRect(g, x, y, w, h, r); g.clip();
    g.fillStyle = PAL.ink; g.fillRect(x, y, w, h);
    // the inset is a horizontally flipped crop of the full-frame layer stack
    const sc = L.zoom ?? 1, cw = DW / sc, ch = cw * h / w, cx = (L.focus?.[0] ?? 0.5) * DW - cw / 2, cy = (L.focus?.[1] ?? 0.5) * DH - ch / 2;
    g.translate(x + w, y); g.scale(-1, 1);
    g.drawImage(Lm, cx * ctx.S, cy * ctx.S, cw * ctx.S, ch * ctx.S, 0, 0, w, h);
    g.restore();
    g.save(); g.strokeStyle = rgba(PAL.boneDim, 0.7); g.lineWidth = 3; roundRect(g, x, y, w, h, r); g.stroke();
    const gr = g.createLinearGradient(x, y, x + w, y + h); gr.addColorStop(0, 'rgba(236,230,216,0.06)'); gr.addColorStop(0.5, 'rgba(236,230,216,0)'); gr.addColorStop(1, 'rgba(236,230,216,0.04)');
    g.fillStyle = gr; roundRect(g, x, y, w, h, r); g.fill(); g.restore();
  },

  // -------- type --------
  page(ctx, L, env) {
    const ws = words(env.T, L, env.shot);
    const fns = (L.footnotes || []).map(f => ({ ...f, at: f.at ?? (ws.find(w => w.key === f.word)?.start ?? 0) }));
    pageType(ctx.ty, ws, env.t, { x: L.x ?? 150, y: L.y ?? 470, w: L.measure ?? 1060, size: L.size ?? 140, maxLines: L.maxLines ?? 3, header: L.header, headerX: env.shot.hud ? 560 : undefined, folio: L.folio, footnotes: fns, furniture: smooth(0, 0.4, env.lt), settle: L.settle, color: L.color, hybrid: L.hybrid, drift: L.drift });
  },
  subtitle(ctx, L, env) { const ws = words(env.T, L, env.shot).filter(w => w.start < env.shot.t1 + (L.tail ?? 0.01)); subtitle(ctx.ty, ws, env.t, { y: L.y ?? 1010, x: L.x, lit: L.lit, color: L.color, upper: L.upper }); },
  mono(ctx, L, env) {
    const at = L.at ?? 0; if (env.lt < at) return;
    let s = L.text; if (L.typed) s = s.slice(0, Math.floor((env.lt - at) * L.typed + 1));
    const g = L.onScene ? ctx.g : ctx.ty; g.save(); setFont(g, F.mono(Math.max(42, L.size ?? 44), L.weight ?? 400), L.track ?? 2);
    g.fillStyle = rgba(L.color || PAL.bone, A(L.alpha, env, 1) * smooth(at, at + 0.12, env.lt)); g.textAlign = L.align || 'center'; g.textBaseline = 'alphabetic';
    g.fillText(s + (L.typed && fract(env.t * 2) < 0.5 ? '▌' : ''), A(L.x, env, DW / 2), A(L.y, env, 560)); g.restore();
  },
  cm(ctx, L, env) {   // a line of Computer Modern (title-page/theorem setting); bold lead-in in roman
    const at = L.at ?? 0; if (env.lt < at) return;
    const g = ctx.ty, a = A(L.alpha, env, 1) * smooth(at, at + (L.fade ?? 0.3), env.lt), x = A(L.x, env, 150), y = A(L.y, env, 600), px = L.size ?? 96;
    g.save(); g.textBaseline = 'alphabetic'; g.textAlign = L.align || 'left';
    let cx = x;
    if (L.lead) { g.font = `700 ${px}px CMUB`; g.fillStyle = rgba(L.leadColor || PAL.bone, a); if (g.textAlign === 'left') { g.fillText(L.lead, cx, y); cx += g.measureText(L.lead + ' ').width; } }
    g.font = F.cmu(px); g.fillStyle = rgba(L.color || PAL.bone, a); g.fillText(L.text, cx, y);
    g.restore();
  },
  redact(ctx, L, env) {
    const t0 = env.shot.t0 + (L.at ?? 0);
    if (L.hold) { redactedLine(ctx.ty, L.parts, L.x ?? 150, L.y ?? 700, L.font || F.cmu(L.size ?? 110), L.color || PAL.bone, L.barColor || PAL.bone); return; }
    redact(ctx.ty, { text: L.text, x: L.x ?? DW / 2, y: L.y ?? 600, font: L.font || F.cmu(L.size ?? 120), t: env.t, t0, dur: L.dur ?? 0.5, color: L.color, barColor: L.barColor, align: L.align ?? 'left' });
  },
  revisions(ctx, L, env) {
    const ws = words(env.T, L, env.shot);
    const revs = (L.revs || [{ dx: 0, dy: 0 }, { dx: 22, dy: 46 }, { dx: 44, dy: 92 }]).map((r, i) => ({ ...r, words: ws.map((w, j) => ({ ...w, start: w.start + i * (L.stagger ?? 0.12), del: r.del && r.del.includes(w.key), ins: r.ins && r.ins.includes(w.key) })) }));
    revisions(ctx.ty, revs, env.t, { x: L.x ?? 150, y: L.y ?? 420, size: L.size ?? 120, measure: L.measure ?? 1100 });
  },
  slam(ctx, L, env, data) {
    const hits = (L.hits || [{ t: env.shot.t0 + (L.at ?? 0), text: L.text, variant: L.variant }]).filter(h => h.t <= env.t + 1e-6);
    if (!hits.length) return; const h = hits[hits.length - 1], g = L.onType ? ctx.ty : ctx.g, v = h.variant || L.variant || 'center';
    const o = { t: env.t, t0: h.t, text: h.text, color: h.color || L.color || PAL.bone, y: L.y, cx: L.cx };
    if (v === 'assemble') V.assemble(g, { ...o, beat: env.T.period, maxH: L.maxH }); else if (v === 'behind') V.behind(g, o, null); else if (v === 'mirror') V.mirror(g, o); else if (v === 'bars') V.bars(g, { ...o, code: h.code }); else if (v === 'stack') V.stack(g, { ...o, beat: env.T.period });
    else slam(g, { ...o, stutter: L.stutter ?? 1, seed: hits.length, maxW: L.maxW ?? 1780, maxH: L.maxH ?? 680, y: L.y ?? 830, plates: L.plates, x: L.x, align: L.align });
  },

  // -------- HUD-ish graphics --------
  tree(ctx, L, env) {
    const key = `${L.seed}:${L.depth}:${L.kids ?? 3}`;
    TREES.has(key) || TREES.set(key, buildTree(L.seed ?? 3, L.depth ?? 5, L.kids ?? 3));
    const TR = TREES.get(key), g = L.onType ? ctx.ty : ctx.g;
    const geo = { x: A(L.x, env, 300), y: A(L.y, env, 560), w: A(L.w, env, 1300), h: A(L.h, env, 760) };
    const { P } = searchTree(g, TR, { ...geo, progress: A(L.progress, env, 1), lit: A(L.lit, env, 0), labels: L.labels, alpha: A(L.alpha, env, 1), litColor: L.litColor, leafSize: L.leafSize, ink: L.ink, labelSize: L.labelSize });
    for (const d of [].concat(L.dead ?? [])) {
      const a = P(TR.nodes[0]), b = P(TR.nodes[d]), u = A(L.deadU, env, 1);
      g.save(); g.strokeStyle = rgba(PAL.red, 0.95 * u); g.lineWidth = 7; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(lerp(a[0], b[0], u), lerp(a[1], b[1], u)); g.stroke(); g.restore();
      if (u >= 1) glyph(g, '✗', b[0], b[1], 120, rgba(PAL.red, 1));
    }
    env.treeP = P; env.tree = TR;
  },
  // brute force: thousands of branches flung out from a root, all dying (✗) but one lit line
  explode(ctx, L, env) {
    const g = ctx.g, n = Math.floor(A(L.n, env, 400)), x0 = L.x ?? 260, y0 = L.y ?? 560, R0 = rng(L.seed ?? 9), lit = A(L.lit, env, 0), kill = A(L.kill, env, 0);
    g.save(); g.lineWidth = 3; g.lineCap = 'round';
    const segs = [];
    for (let i = 0; i < n; i++) {
      let x = x0, y = y0, a = (R0() - 0.5) * 1.6; const pts = [[x, y]]; const len = 4 + Math.floor(R0() * 5);
      for (let k = 0; k < len; k++) { a += (R0() - 0.5) * 0.9; const s = 60 + R0() * 120; x += Math.cos(a) * s; y += Math.sin(a) * s * 1.2; pts.push([x, y]); }
      segs.push(pts);
    }
    const dead = 0.25 + 0.6 * (1 - kill);
    g.strokeStyle = rgba(PAL.boneDim, dead); g.beginPath();
    for (const p of segs) { g.moveTo(p[0][0], p[0][1]); for (const q of p.slice(1)) g.lineTo(q[0], q[1]); }
    g.stroke();
    setFont(g, F.mono(30, 700)); g.fillStyle = rgba(PAL.red, 0.9 * (1 - kill * 0.5)); g.textAlign = 'center'; g.textBaseline = 'middle';
    for (let i = 0; i < Math.min(segs.length, 900); i++) { const q = segs[i][segs[i].length - 1]; if (q[0] > 0 && q[0] < DW && q[1] > 0 && q[1] < DH) g.fillText('✗', q[0], q[1]); }
    if (lit > 0) {   // the surviving line: a clean S toward the right edge
      g.strokeStyle = rgba(PAL.bone, lit); g.lineWidth = 8; g.beginPath(); g.moveTo(x0, y0);
      g.bezierCurveTo(x0 + 500, y0 - 260, x0 + 900, y0 + 240, DW + 40, y0 - 60); g.stroke();
    }
    g.restore();
  },
  counter(ctx, L, env) {
    const g = ctx.ty, v = A(L.value, env, 1); g.save(); setFont(g, F.mono(L.size ?? 120, 700), 2); g.fillStyle = A(L.color, env, PAL.bone); g.textAlign = L.align || 'right'; g.textBaseline = 'alphabetic';
    g.fillText(typeof v === 'string' ? v : String(Math.floor(v)).padStart(2, '0'), A(L.x, env, DW - 80), A(L.y, env, 200)); g.restore();
  },
  evalbar(ctx, L, env) { evalBar(ctx.ty, { value: A(L.value, env, 0), mate: A(L.mate, env, null) }); },
  annotation(ctx, L, env) { if (env.lt < (L.at ?? 0)) return; annotation(ctx.ty, { ...L, alpha: smooth(L.at ?? 0, (L.at ?? 0) + 0.2, env.lt) }); },

  // top-down chessboard map: her zigzag path and the suits' pursuit curves converging (drawn mathematically)
  map(ctx, L, env) {
    const g = ctx.g, p = A(L.progress, env, env.u), x0 = 360, y0 = 120, cs = 105, n = 8;
    g.save();
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { if ((i + j) % 2) { g.fillStyle = 'rgba(236,230,216,0.07)'; g.fillRect(x0 + i * cs * 1.5, y0 + j * cs, cs * 1.5, cs); } }
    g.strokeStyle = rgba(PAL.boneDim, 0.6); g.lineWidth = 2; g.strokeRect(x0, y0, cs * 1.5 * n, cs * n);
    // her zigzag (the knight's tour of a frightened person)
    const her = s => [x0 + 60 + s * 1080, y0 + cs * n - 60 - s * (cs * n - 160) + Math.sin(s * 22) * 120];
    const N = 120, k = Math.floor(N * p);
    g.strokeStyle = PAL.bone; g.lineWidth = 6; g.beginPath();
    for (let i = 0; i <= k; i++) { const q = her(i / N); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); } g.stroke();
    const hq = her(k / N); g.fillStyle = PAL.bone; g.beginPath(); g.arc(hq[0], hq[1], 14, 0, Math.PI * 2); g.fill();
    // pursuers: pure pursuit (always steer at her current position), faster than her
    const starts = [[x0 + 1200, y0 + 40], [x0 + 1240, y0 + cs * n - 40], [x0 + 20, y0 + 30]];
    g.lineWidth = 4;
    for (let s = 0; s < starts.length; s++) {
      let [px, py] = starts[s]; g.strokeStyle = rgba(s % 2 ? PAL.blue : PAL.red, 0.95); g.beginPath(); g.moveTo(px, py);
      for (let i = 0; i <= k; i++) { const q = her(i / N); const dx = q[0] - px, dy = q[1] - py, d = Math.hypot(dx, dy) || 1, v = 16; px += dx / d * Math.min(v, d); py += dy / d * Math.min(v, d); g.lineTo(px, py); }
      g.stroke(); g.fillStyle = '#000'; g.fillRect(px - 12, py - 12, 24, 24); g.strokeStyle = rgba(PAL.bone, 0.9); g.lineWidth = 2; g.strokeRect(px - 12, py - 12, 24, 24); g.lineWidth = 4;
    }
    g.restore();
  },
  // mini Lake Shore Drive route map drawing itself in a corner
  routemap(ctx, L, env) {
    const g = ctx.ty, x = L.x ?? 1440, y = L.y ?? 640, w = L.w ?? 380, h = L.h ?? 330, p = A(L.progress, env, env.u);
    const pts = LSD.map(([u, v]) => [x + u * w, y + v * h]), k = Math.max(1, Math.floor((pts.length - 1) * p));
    g.save(); g.strokeStyle = rgba(PAL.boneDim, 0.7); g.lineWidth = 2; g.strokeRect(x - 20, y - 20, w + 40, h + 40);
    g.fillStyle = 'rgba(7,8,10,0.6)'; g.fillRect(x - 20, y - 20, w + 40, h + 40);
    g.strokeStyle = PAL.sodium; g.lineWidth = 6; g.beginPath(); pts.slice(0, k + 1).forEach((q, i) => (i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.stroke();
    g.fillStyle = PAL.bone; g.beginPath(); g.arc(pts[k][0], pts[k][1], 10, 0, Math.PI * 2); g.fill();
    setFont(g, F.mono(42, 700), 2); g.fillStyle = PAL.bone; g.fillText(L.label ?? 'LSD N', x, y - 34); g.restore();
  },
  grass(ctx, L, env) {
    const g = ctx.g, n = L.n ?? 900, y0 = L.y ?? 560, wind = env.t * 1.3;
    g.save(); g.strokeStyle = rgba(L.color || PAL.bone, A(L.alpha, env, 0.55)); g.lineWidth = 1.6; g.beginPath();
    for (let i = 0; i < n; i++) {
      const z = hash(i, 1), x = fract(hash(i, 2) + (L.scroll ? env.t * L.scroll * (0.2 + z) : 0)) * (DW + 200) - 100, base = y0 + Math.pow(z, 1.6) * (DH - y0 + 80);
      const hgt = 30 + z * z * 260, bend = Math.sin(wind + x * 0.004 + i) * (10 + z * 40) + (L.part ? L.part(x, base, env) : 0);
      g.moveTo(x, base); g.quadraticCurveTo(x + bend * 0.4, base - hgt * 0.6, x + bend, base - hgt);
    }
    g.stroke(); g.restore();
  },
  // a running figure (stand-in for J7 until the roto exists): bone cut-out, legs/arms on a run cycle
  runner(ctx, L, env) {
    const g = ctx.g, x = A(L.x, env, 960), y = A(L.y, env, 760), s = A(L.scale, env, 1), ph = env.t * (L.cadence ?? 3.2) * Math.PI * 2;
    g.save(); g.translate(x, y); g.scale(s * (L.dir ?? 1), s); g.fillStyle = L.ghost ? 'rgba(0,0,0,0)' : PAL.bone; g.strokeStyle = L.ghost ? PAL.cyan : PAL.bone; g.lineCap = 'round';
    g.lineWidth = 34; const limb = (a, l1, l2, bend, ox, oy) => { const k = [ox + Math.sin(a) * l1, oy + Math.cos(a) * l1]; g.beginPath(); g.moveTo(ox, oy); g.lineTo(k[0], k[1]); g.lineTo(k[0] + Math.sin(a + bend) * l2, k[1] + Math.cos(a + bend) * l2); g.stroke(); };
    limb(Math.sin(ph) * 0.9, 120, 120, -0.9, 0, -60); limb(-Math.sin(ph) * 0.9, 120, 120, -0.9, 0, -60);
    g.lineWidth = 60; g.beginPath(); g.moveTo(0, -60); g.lineTo(18, -250); g.stroke();
    g.lineWidth = 26; limb(Math.PI - Math.sin(ph) * 1.1, 90, 80, 1.3, 18, -230); limb(Math.PI + Math.sin(ph) * 1.1, 90, 80, 1.3, 18, -230);
    g.beginPath(); g.arc(30, -305, 40, 0, Math.PI * 2); L.ghost ? (g.lineWidth = 4, g.stroke()) : g.fill();
    g.fillStyle = PAL.ink; g.beginPath(); g.moveTo(-6, -350); g.quadraticCurveTo(60, -360, 76, -300); g.lineTo(80, -200); g.lineTo(50, -205); g.lineTo(46, -300); g.quadraticCurveTo(20, -330, -10, -300); g.closePath(); if (!L.ghost) g.fill();
    g.restore();
  },
  beams(ctx, L, env) {
    const g = ctx.g, n = L.n ?? 3, a = A(L.amount, env, 0.35);
    g.save(); g.globalCompositeOperation = 'lighter';
    for (let i = 0; i < n; i++) {
      const ox = hash(i, 4) < 0.5 ? -100 : DW + 100, oy = 300 + hash(i, 5) * 300, ang = (ox < 0 ? 0 : Math.PI) + Math.sin(env.t * (0.8 + i * 0.3) + i * 2) * 0.35;
      const gr = g.createLinearGradient(ox, oy, ox + Math.cos(ang) * 2000, oy + Math.sin(ang) * 2000);
      gr.addColorStop(0, rgba(PAL.bone, a)); gr.addColorStop(1, rgba(PAL.bone, 0));
      g.fillStyle = gr; g.beginPath(); g.moveTo(ox, oy); g.lineTo(ox + Math.cos(ang - 0.08) * 2400, oy + Math.sin(ang - 0.08) * 2400); g.lineTo(ox + Math.cos(ang + 0.08) * 2400, oy + Math.sin(ang + 0.08) * 2400); g.closePath(); g.fill();
    }
    g.restore();
  },
  dash(ctx, L, env) { const g = ctx.g, a = A(L.amount, env, 0.3); const gr = g.createLinearGradient(0, DH, 0, DH * 0.55); gr.addColorStop(0, rgba(L.color || PAL.sodium, a)); gr.addColorStop(1, rgba(L.color || PAL.sodium, 0)); g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = gr; g.fillRect(0, 0, DW, DH); g.restore(); },

  // her driver license: a generic horizontal card (no real state design, seals or logos), held by a bone hand
  badge(ctx, L, env) {
    const g = ctx.g, x = A(L.x, env, 1240), y = A(L.y, env, 560), s = A(L.scale, env, 1), r = A(L.rot, env, -0.06);
    g.save(); g.translate(x, y); g.rotate(r); g.scale(s, s);
    const W0 = 640, H0 = 404;
    g.fillStyle = PAL.bone; roundRect(g, -W0 / 2, -H0 / 2, W0, H0, 24); g.fill();
    g.fillStyle = PAL.ink; g.fillRect(-W0 / 2, -H0 / 2 + 22, W0, 70);
    setFont(g, F.mono(46, 700), 6); g.fillStyle = PAL.bone; g.textAlign = 'left'; g.textBaseline = 'alphabetic'; g.fillText('DRIVER LICENSE', -W0 / 2 + 30, -H0 / 2 + 74);
    // portrait: her as a tiny bone figure (ink hair, bone face, glasses)
    const px = -W0 / 2 + 36, py = -H0 / 2 + 116, pw = 190, ph = 240;
    g.fillStyle = '#B9B3A7'; g.fillRect(px, py, pw, ph);
    g.fillStyle = PAL.ink; g.beginPath(); g.ellipse(px + pw / 2, py + 108, 70, 84, 0, 0, Math.PI * 2); g.fill(); g.fillRect(px + 26, py + 108, 138, 132);
    g.fillStyle = PAL.bone; g.beginPath(); g.ellipse(px + pw / 2, py + 120, 46, 58, 0, 0, Math.PI * 2); g.fill();
    g.fillRect(px + 52, py + 196, 86, 44);
    g.strokeStyle = '#1C2E31'; g.lineWidth = 3; g.strokeRect(px + 58, py + 108, 34, 16); g.strokeRect(px + 98, py + 108, 34, 16);
    // fields: label + value, sensitive ones redacted
    setFont(g, F.mono(26, 700), 1); const fx = px + pw + 30;
    const fields = [['DL', null, 'K4471'], ['EXP', null, null], ['DOB', null, null], ['CLASS', 'D'], ['NAME', 'WANG, J.']];
    fields.forEach(([k, v, tail], i) => {
      const fy = py + 30 + i * 46; g.fillStyle = 'rgba(7,8,10,0.55)'; g.fillText(k, fx, fy);
      const vx = fx + 100;
      if (v) { g.fillStyle = PAL.ink; g.fillText(v, vx, fy); }
      else { g.fillStyle = '#000'; g.fillRect(vx, fy - 24, 150, 30); if (tail) { g.fillStyle = PAL.ink; g.fillText(tail, vx + 160, fy); } }
    });
    setFont(g, F.mono(20, 700), 2); g.fillStyle = PAL.red; g.fillText('DONOR', fx, py + ph - 4);
    // hand: thumb over the edge
    g.fillStyle = PAL.bone; g.strokeStyle = PAL.ink; g.lineWidth = 4;
    g.beginPath(); g.moveTo(-W0 / 2 - 40, H0 / 2 - 60); g.quadraticCurveTo(-W0 / 2 - 70, H0 / 2 + 80, -W0 / 2 + 50, H0 / 2 + 150); g.lineTo(-W0 / 2 + 230, H0 / 2 + 150); g.quadraticCurveTo(-W0 / 2 + 250, H0 / 2 + 60, -W0 / 2 + 140, H0 / 2 + 20); g.lineTo(-W0 / 2 + 40, H0 / 2 - 40); g.closePath(); g.fill(); g.stroke();
    g.beginPath(); g.moveTo(-W0 / 2 + 40, H0 / 2 - 20); g.quadraticCurveTo(-W0 / 2 + 90, H0 / 2 - 60, -W0 / 2 + 140, H0 / 2 + 20); g.stroke();
    g.restore();
  },
  // self-drawing pen stroke (the winning line / the theorem's road) with a moving light at the head
  pathdraw(ctx, L, env) {
    const g = ctx.g, p = clamp(A(L.progress, env, env.u)), pts = (L.pts || LSD_AERIAL).map(([u, v]) => [u * DW, v * DH]);
    const N = pts.length - 1, k = p * N, ki = Math.floor(k);
    g.save(); g.globalCompositeOperation = 'lighter'; g.strokeStyle = L.color || PAL.bone; g.lineWidth = L.width ?? 5; g.lineCap = 'round';
    g.beginPath(); g.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i <= ki; i++) g.lineTo(pts[i][0], pts[i][1]);
    const hd = ki < N ? [lerp(pts[ki][0], pts[ki + 1][0], k - ki), lerp(pts[ki][1], pts[ki + 1][1], k - ki)] : pts[N];
    g.lineTo(hd[0], hd[1]); g.stroke();
    if (L.head !== false) { headlights(g, hd[0], hd[1], 120, 0.9, L.headColor || PAL.bone); g.fillStyle = PAL.bone; g.beginPath(); g.arc(hd[0], hd[1], 7, 0, Math.PI * 2); g.fill(); }
    g.restore(); env.head = hd;
  },
  // Jade's attempts as a formation of ghost outlines (2 → 4 → 8)
  ghosts(ctx, L, env, { roto }) {
    const id = L.roto, n = Math.floor(A(L.n, env, 4)); if (!roto.meta(id)) return;
    const cols = Math.min(n, 4), rows = Math.ceil(n / 4), sc = n <= 2 ? 0.8 : n <= 4 ? 0.62 : 0.5;
    for (let i = 0; i < n; i++) {
      const c = i % 4, r = Math.floor(i / 4), w = DW * sc, h = DH * sc;
      const x = DW / 2 - w * 0.75 + (c - (cols - 1) / 2) * w * 0.34, y = DH * 0.08 + r * h * 0.42 + (DH - h) * 0.4 - (rows - 1) * h * 0.2;
      const ct = roto.clipTime(id, env.lt - i * 0.12, { loop: 'pingpong' });   // each copy a step later in time
      if (i === 0) { roto.jade(ctx.g, id, ct, { rect: { x, y, w, h }, boil: ctx.seed, mouth: 0 }); continue; }
      // Gjon Mili light drawing: the past run as one luminous line, long exposure (soft glow + crisp core), brightness travelling
      const g = ctx.g; g.save(); g.globalCompositeOperation = 'lighter';
      g.filter = 'blur(6px)'; roto.jade(g, id, ct, { rect: { x, y, w, h }, ghost: true, ghostColor: i % 2 ? PAL.cyan : PAL.bone, mouth: 0, alpha: 0.7, v1: true });
      g.filter = 'none'; roto.jade(g, id, ct, { rect: { x, y, w, h }, ghost: true, ghostColor: '#FFFFFF', mouth: 0, alpha: 0.4 + 0.5 * (0.5 + 0.5 * Math.sin(env.t * 6 + i)), v1: true });
      g.restore();
    }
  },
  // A Beautiful Mind wall: pinned death photos, timestamps, red string
  wall(ctx, L, env) {
    const g = ctx.g, p = A(L.progress, env, env.u);
    const pins = L.pins || [[300, 260, '42.89'], [700, 600, '102.28'], [1180, 300, '13.45'], [1500, 700, '∞'], [480, 820, '45.20'], [1640, 240, '171.54']];
    const cs = L.card ?? 1;
    g.save();
    const n = Math.ceil(pins.length * clamp(p * 1.4));
    g.strokeStyle = PAL.red; g.lineWidth = 3;
    for (let i = 1; i < n; i++) { const a = pins[i - 1], b = pins[i]; g.beginPath(); g.moveTo(a[0], a[1]); g.quadraticCurveTo((a[0] + b[0]) / 2, Math.max(a[1], b[1]) + 60, b[0], b[1]); g.stroke(); }
    for (let i = 0; i < n; i++) {
      const [x, y, lab] = pins[i];
      g.save(); g.translate(x, y); g.rotate(hsig(i, 3) * 0.12); g.scale(cs, cs);
      g.fillStyle = PAL.bone; g.fillRect(-130, -90, 260, 180); g.fillStyle = PAL.ink; g.fillRect(-114, -74, 228, 120);
      g.fillStyle = '#000'; for (let k = 0; k < 3; k++) { g.beginPath(); g.ellipse(-60 + k * 60, -10, 18, 22, 0, 0, Math.PI * 2); g.fill(); g.fillRect(-82 + k * 60, 10, 44, 40); }
      setFont(g, F.mono(42, 700), 1); g.fillStyle = PAL.ink; g.textAlign = 'center'; g.fillText(lab, 0, 86);
      g.fillStyle = PAL.red; g.beginPath(); g.arc(0, -92, 9, 0, Math.PI * 2); g.fill();
      if (lab !== '∞' && lab !== '13.45') { setFont(g, F.mono(90, 700)); g.fillStyle = rgba(PAL.red, 0.9); g.fillText('✗', 80, -10); }
      g.restore();
    }
    g.restore();
  },
  // extreme close-up of her glasses: two thin rectangular lenses reflecting the scrolling tree
  glasses(ctx, L, env) {
    const g = ctx.g, sc = env.t * 300;
    for (const [cx, cy] of [[600, 520], [1320, 520]]) {
      g.save(); g.beginPath(); roundRect(g, cx - 330, cy - 170, 660, 340, 40); g.clip();
      g.fillStyle = '#05090A'; g.fillRect(cx - 340, cy - 180, 680, 360);
      g.strokeStyle = rgba(PAL.cyan, 0.65); g.lineWidth = 3; g.beginPath();
      for (let i = 0; i < 40; i++) { const y = cy - 170 + fract(i / 40 + sc / 2000) * 340, x = cx - 300 + hash(i, 1) * 200; g.moveTo(x, y); g.lineTo(x + 140, y - 30 + hash(i, 2) * 60); g.lineTo(x + 300, y - 50 + hash(i, 3) * 100); }
      g.stroke();
      setFont(g, F.mono(30, 700)); g.fillStyle = rgba(PAL.red, 0.8); for (let i = 0; i < 30; i++) g.fillText('✗', cx - 320 + hash(i, 7) * 640, cy - 170 + fract(hash(i, 8) + sc / 1500) * 340);
      g.restore();
      g.save(); g.strokeStyle = '#3F5A5C'; g.lineWidth = 14; roundRect(g, cx - 330, cy - 170, 660, 340, 40); g.stroke(); g.restore();
    }
    g.save(); g.strokeStyle = '#3F5A5C'; g.lineWidth = 14; g.beginPath(); g.moveTo(930, 470); g.quadraticCurveTo(960, 440, 990, 470); g.stroke(); g.restore();
  },
  // RELOAD: frame slices re-assemble + a progress bar "loading save"
  reload(ctx, L, env) {
    const g = ctx.ty, u = clamp(env.lt / (L.dur ?? 0.6));
    setFont(g, F.slam(300)); g.save(); g.fillStyle = PAL.bone; g.textAlign = 'center'; g.textBaseline = 'alphabetic';
    const n = 8, hgt = 300 * 0.78 / n, top = 560 - 300 * 0.74;
    for (let i = 0; i < n; i++) { g.save(); g.beginPath(); g.rect(0, top + i * hgt, DW, hgt + 1); g.clip(); g.fillText('RELOAD', DW / 2 + (1 - easeOutExpo(clamp(u * 1.6 - i * 0.07))) * (i % 2 ? 900 : -900), 560); g.restore(); }
    g.fillStyle = 'rgba(236,230,216,0.25)'; g.fillRect(560, 690, 800, 26); g.fillStyle = PAL.cyan; g.fillRect(560, 690, 800 * (Math.floor(u * 6) / 6), 26);
    setFont(g, F.mono(46, 400), 2); g.fillStyle = PAL.bone; g.fillText(L.text ?? 'loading save 00:13.45', DW / 2, 790);
    g.restore();
  },
  // the committee: seated redaction figures appearing one per braam
  committee(ctx, L, env) {
    const g = ctx.g, n = Math.floor(A(L.n, env, 0)), seats = L.seats || [[600, 470], [780, 470], [960, 470], [1140, 470], [1320, 470]];
    for (let i = 0; i < Math.min(n, seats.length); i++) {
      const [x, y] = seats[i], s = L.scale ?? 1;
      g.save(); g.translate(x, y); g.scale(s, s);
      g.fillStyle = '#000'; g.beginPath(); g.ellipse(0, -110, 30, 38, 0, 0, Math.PI * 2); g.fill();
      g.beginPath(); g.moveTo(-60, -60); g.quadraticCurveTo(0, -84, 60, -60); g.lineTo(70, 40); g.lineTo(-70, 40); g.closePath(); g.fill();
      g.fillRect(-64, -122, 128, 22);   // the face bar, wider than the head
      g.strokeStyle = rgba(PAL.red, 0.8); g.lineWidth = 3; g.beginPath(); g.moveTo(-60, -60); g.quadraticCurveTo(0, -84, 60, -60); g.stroke();
      g.restore();
    }
  },
  // redaction bars sweeping the whole frame
  sweepbars(ctx, L, env) {
    const g = L.onType ? ctx.ty : ctx.g, p = A(L.progress, env, env.u), n = L.n ?? 7;
    g.save(); g.fillStyle = L.color || '#000';
    for (let i = 0; i < n; i++) { const y = (i + 0.5) / n * DH - 50, x = lerp(-DW, DW * 1.2, clamp(p * 1.3 - hash(i, 2) * 0.3)); g.fillRect(x, y, DW * (0.4 + hash(i, 3) * 0.5), 70 + hash(i, 4) * 40); }
    g.restore();
  },
  // the frozen frame of another shot, optionally as a small pinned print
  async freezeOf(ctx, L, env, data) {
    const sh = L.shot ? data.shotById(L.shot) : data.shotAt(L.time);
    if (!sh) return;
    const tt = L.time ?? sh.t1 - 1 / 30, Lf = layer('freeze_' + (L.slot ?? 0), ctx.g.canvas.width, ctx.g.canvas.height), LT = layer('freezeT_' + (L.slot ?? 0), ctx.g.canvas.width, ctx.g.canvas.height);
    const fg = clearLayer(Lf), ft = clearLayer(LT); fg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0); ft.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    await data.drawShot(sh, tt, fg, ft, {}, { rewinding: true, mode: L.mode, noHud: true });
    resetCtx(fg); if (L.withType !== false) fg.drawImage(LT, 0, 0);
    const r = L.rect || [0, 0, DW, DH], g = ctx.g;
    g.save(); g.globalAlpha = A(L.alpha, env, 1);
    if (L.rect) { g.translate(r[0] + r[2] / 2, r[1] + r[3] / 2); g.rotate(L.rot ?? 0); g.fillStyle = PAL.bone; g.fillRect(-r[2] / 2 - 10, -r[3] / 2 - 10, r[2] + 20, r[3] + 20); g.drawImage(Lf, -r[2] / 2, -r[3] / 2, r[2], r[3]); }
    else g.drawImage(Lf, 0, 0, Lf.width, Lf.height, 0, 0, DW, DH);
    g.restore();
  },
  // FOIA pages flying past (internet brutalism): redacted text blocks
  foia(ctx, L, env) {
    const g = ctx.g, n = L.n ?? 5;
    for (let i = 0; i < n; i++) {
      const sp = 0.7 + hash(i, 1), x = lerp(DW + 400, -900, fract(env.t * sp * 0.35 + hash(i, 2))), y = 120 + hash(i, 3) * 600, r = hsig(i, 4) * 0.25;
      g.save(); g.translate(x, y); g.rotate(r); g.fillStyle = PAL.bone; g.fillRect(0, 0, 520, 680);
      setFont(g, F.mono(30, 700), 1); g.fillStyle = PAL.ink; g.fillText('FEDERAL BUREAU OF ████████', 30, 60);
      for (let k = 0; k < 12; k++) { const w = 120 + hash(i, k, 5) * 330; g.fillStyle = hash(i, k, 6) < 0.45 ? '#000' : 'rgba(7,8,10,0.35)'; g.fillRect(30, 100 + k * 44, w, hash(i, k, 6) < 0.45 ? 30 : 8); }
      g.restore();
    }
  },
};
Object.assign(LAYERS, {
  // the REWIND hand gesture: a counter-clockwise circular trail around her (until J5 roto exists)
  circle(ctx, L, env) {
    const g = ctx.g, cx = A(L.x, env, 960), cy = A(L.y, env, 540), r = A(L.r, env, 330), a0 = -env.t * (L.speed ?? 5);
    g.save(); g.globalCompositeOperation = 'lighter'; g.lineCap = 'round';
    for (let i = 0; i < 24; i++) { const a = a0 + i * 0.09; g.strokeStyle = rgba(L.color || PAL.cyan, (1 - i / 24) * 0.9); g.lineWidth = 14 * (1 - i / 24) + 2; g.beginPath(); g.arc(cx, cy, r, a, a + 0.1); g.stroke(); }
    g.restore();
  },
  // muzzle flash frozen as a drawn star
  star(ctx, L, env) {
    const g = ctx.g, x = A(L.x, env, 1300), y = A(L.y, env, 460), R = A(L.r, env, 160), n = L.n ?? 9;
    g.save(); g.globalCompositeOperation = 'lighter'; g.fillStyle = L.color || PAL.bone; g.beginPath();
    for (let i = 0; i < n * 2; i++) { const a = i / (n * 2) * Math.PI * 2, rr = i % 2 ? R * (0.12 + 0.1 * hash(i, 3)) : R * (0.6 + 0.4 * hash(i, 2)); g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
    g.closePath(); g.fill(); headlights(g, x, y, R * 2.2, 0.5); g.restore();
  },
  // an outline car (rear 3/4): the ghost of an earlier attempt
  ghostcar(ctx, L, env) {
    const g = ctx.g, x = A(L.x, env, 960), y = A(L.y, env, 600), s = A(L.scale, env, 1), a = A(L.alpha, env, 0.9);
    if (CAR.has('rear')) { CAR.drawView(g, 'rear', x, y + 40 * s, 400 * s, { color: L.color || PAL.cyan, alpha: a, outline: true, lights: null, seed: Math.floor(env.lt * 10) }); return; }
    g.save(); g.translate(x, y); g.scale(s, s); g.strokeStyle = rgba(L.color || PAL.cyan, a); g.lineWidth = 4; g.lineJoin = 'round';
    g.beginPath(); g.moveTo(-200, 40); g.lineTo(-190, -20); g.lineTo(-120, -40); g.lineTo(-80, -100); g.lineTo(80, -100); g.lineTo(120, -40); g.lineTo(190, -20); g.lineTo(200, 40); g.closePath(); g.stroke();
    g.beginPath(); g.moveTo(-70, -90); g.lineTo(70, -90); g.lineTo(100, -45); g.lineTo(-100, -45); g.closePath(); g.stroke();
    g.fillStyle = rgba(PAL.red, a); g.fillRect(-185, -12, 50, 16); g.fillRect(135, -12, 50, 16);
    g.restore();
  },
  // an over-everything vignette of black (drain), amount 0..1
  drain(ctx, L, env) { const g = ctx.g, a = A(L.amount, env, env.u); const gr = g.createRadialGradient(DW / 2, DH / 2, lerp(1200, 4, a), DW / 2, DH / 2, lerp(1400, 30, a)); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,1)'); g.fillStyle = gr; g.fillRect(0, 0, DW, DH); },
});
Object.assign(LAYERS, {
  // NEVER STOP painted on the asphalt as the lane dashes, rushing at camera in perspective (ground plane)
  lanewords(ctx, L, env) {
    const g = ctx.g, vx = L.vx ?? 960, vy = L.vy ?? 430, sp = A(L.speed, env, 1.6), words = L.words || ['NEVER', 'STOP'];
    // road surface edges + centre band, bright
    g.save(); g.strokeStyle = rgba(PAL.bone, 0.95); g.lineWidth = 5;
    for (const sx of [-1, 1]) { g.beginPath(); g.moveTo(vx + sx * 30, vy); g.lineTo(vx + sx * 2400, DH + 200); g.stroke(); }
    const n = L.n ?? 7;
    setFont(g, F.slam(200)); g.textAlign = 'center'; g.textBaseline = 'alphabetic';
    for (let i = n - 1; i >= 0; i--) {
      const z = fract(i / n + env.t * sp * 0.22), d = Math.pow(z, 2.2);          // 0 = horizon, 1 = under the car
      const y = vy + d * (DH + 300 - vy), sc = 0.04 + d * 2.6;
      if (y > DH + 260) continue;
      const w = words[(i + Math.floor(env.t * sp * 0.22 * n)) % words.length];
      g.save(); g.translate(vx, y); g.scale(sc, sc * 0.42);
      g.fillStyle = rgba(L.color || PAL.bone, smooth(0, 0.12, z)); g.fillText(w, 0, 0); g.restore();
    }
    g.restore();
  },
  // case-file pages of the deaths flying out of the car window (from the centre outward, tumbling)
  casepages(ctx, L, env) {
    const g = ctx.g, n = L.n ?? 7;
    for (let i = 0; i < n; i++) {
      const ph = fract(env.t * (0.45 + hash(i, 1) * 0.35) + hash(i, 2)), ang = hash(i, 3) * Math.PI * 2;
      const r = lerp(60, 1500, Math.pow(ph, 1.4)), x = 960 + Math.cos(ang) * r, y = 520 + Math.sin(ang) * r * 0.6, sc = lerp(0.25, 1.7, ph), rot = hsig(i, 4) * 3 * ph;
      g.save(); g.translate(x, y); g.rotate(rot); g.scale(sc, sc); g.globalAlpha = 1 - smooth(0.85, 1, ph);
      g.fillStyle = PAL.bone; g.fillRect(-200, -260, 400, 520);
      setFont(g, F.mono(40, 700), 2); g.fillStyle = PAL.ink; g.fillText(`CASE 0${1 + (i % 2)}`, -170, -200);
      g.fillStyle = '#0b0b0c'; g.fillRect(-170, -170, 340, 210);
      g.fillStyle = '#000'; for (let k = 0; k < 6; k++) g.fillRect(-170, 70 + k * 30, 120 + hash(i, k) * 210, 16);
      setFont(g, F.mono(220, 700)); g.fillStyle = PAL.red; g.textAlign = 'center'; g.fillText('✗', 60, 40);
      g.restore();
    }
  },
  // the search tree collapsing into the road: thousands of branches fold into one line (the LSD curve)
  collapse(ctx, L, env) {
    const g = ctx.g, p = clamp(A(L.progress, env, env.u)), n = L.n ?? 900, R0 = rng(L.seed ?? 11), x0 = 260, y0 = 560;
    const curve = s => { const q = LSD_AERIAL, k = s * (q.length - 1), i = Math.min(q.length - 2, Math.floor(k)), f = k - i; return [lerp(q[i][0], q[i + 1][0], f) * DW, lerp(q[i][1], q[i + 1][1], f) * DH]; };
    const e = easeInOutCubic(p);
    g.save(); g.lineCap = 'round';
    g.strokeStyle = rgba(PAL.bone, lerp(0.35, 0.9, e)); g.lineWidth = lerp(2.5, 4, e); g.beginPath();
    for (let i = 0; i < n; i++) {
      let x = x0, y = y0, a = (R0() - 0.5) * 1.6; const len = 5;
      for (let k = 0; k <= len; k++) {
        if (k) { a += (R0() - 0.5) * 0.9; const st = 60 + R0() * 120; x += Math.cos(a) * st; y += Math.sin(a) * st * 1.2; }
        const c = curve(k / len), px = lerp(x, c[0], e), py = lerp(y, c[1], e);
        k ? g.lineTo(px, py) : g.moveTo(px, py);
      }
    }
    g.stroke();
    if (e > 0.85) { g.strokeStyle = rgba(PAL.cyan, (e - 0.85) / 0.15); g.lineWidth = 10; g.beginPath(); for (let k = 0; k <= 40; k++) { const c = curve(k / 40); k ? g.lineTo(c[0], c[1]) : g.moveTo(c[0], c[1]); } g.stroke(); }
    g.restore();
  },
  // the defense room lit by its projector: a bone screen, a big bone wedge of light, the committee as solid black
  projector(ctx, L, env) {
    const g = ctx.g, fl = A(L.flicker, env, 0), sx = 520, sy = 110, sw = 880, sh = 500, px = L.px ?? 1760, py = L.py ?? 900;
    g.save();
    g.fillStyle = rgba(PAL.bone, 0.92 - fl * 0.5); g.fillRect(sx, sy, sw, sh);                     // the screen
    g.globalCompositeOperation = 'lighter';
    const gr = g.createLinearGradient(px, py, sx + sw / 2, sy + sh / 2); gr.addColorStop(0, rgba(PAL.bone, 0.75 - fl * 0.4)); gr.addColorStop(1, rgba(PAL.bone, 0.18));
    g.fillStyle = gr; g.beginPath(); g.moveTo(px, py); g.lineTo(sx + sw, sy); g.lineTo(sx + sw, sy + sh); g.closePath(); g.fill();
    g.beginPath(); g.moveTo(px, py); g.lineTo(sx + sw, sy + sh); g.lineTo(sx + sw * 0.5, sy + sh); g.closePath(); g.fill();
    g.restore();
    if (L.title) { setFont(g, F.cmu(70)); g.fillStyle = PAL.ink; g.textAlign = 'center'; g.fillText(L.title, sx + sw / 2, sy + 150); setFont(g, F.cmu(40)); g.fillText(L.sub ?? 'a dissertation defense', sx + sw / 2, sy + 220); }
  },
  // too many chairs: rows of chair outlines repeating into infinity (on bone paper)
  chairs(ctx, L, env) {
    const g = ctx.g, vx = 960, vy = 300, ink = L.color || PAL.ink;
    g.save(); g.strokeStyle = ink; g.lineCap = 'round';
    for (let r = 14; r >= 0; r--) {
      const z = fract(r / 15 + env.t * 0.05), d = Math.pow(z, 2), y = vy + d * 900, sc = 0.05 + d * 1.4;
      for (let c = -6; c <= 6; c++) {
        const x = vx + c * 220 * sc * 1.4; g.lineWidth = Math.max(1.5, 5 * sc);
        g.save(); g.translate(x, y); g.scale(sc, sc);
        g.beginPath(); g.moveTo(-50, -160); g.lineTo(-50, 0); g.lineTo(50, 0); g.lineTo(50, -160); g.moveTo(-60, 0); g.lineTo(-60, 110); g.moveTo(60, 0); g.lineTo(60, 110); g.moveTo(-50, -160); g.lineTo(50, -160); g.stroke();
        g.restore();
      }
    }
    g.restore();
  },
  // the thesis' last page: bone paper, running head, the proof's closing line and the tombstone
  qedpage(ctx, L, env) {
    const g = ctx.g, ty = ctx.ty;
    g.fillStyle = PAL.bone; g.fillRect(-10, -10, DW + 20, DH + 20);
    ty.save(); ty.textBaseline = 'alphabetic';
    setFont(ty, F.cmu(34)); ty.fillStyle = PAL.ink; ty.fillText('Chapter 3.  Proof by Exhaustion', 150, 120); setFont(ty, F.cmuR(34)); ty.textAlign = 'right'; ty.fillText(L.folio ?? '232', 1770, 120); ty.textAlign = 'left';
    ty.fillRect(150, 142, 1620, 2);
    setFont(ty, F.cmu(64)); ty.fillText(L.line1 ?? 'Case 3 holds: she does not stop.', 150, 380);
    setFont(ty, F.cmu(64)); ty.fillText(L.line2 ?? 'Every other line was checked and pruned.', 150, 470);
    ty.font = '700 220px CMUB'; ty.fillText('Q.E.D.', 150, 780);
    setFont(ty, F.mono(240, 700)); ty.textAlign = 'right'; ty.fillText('∎', 1770, 790);
    ty.fillRect(150, 900, 540, 2); setFont(ty, F.cmu(36)); ty.textAlign = 'left'; ty.fillStyle = PAL.ink; ty.fillText('³ attempts 01, 02: terminated. attempt 03: line found.', 150, 960);
    ty.restore();
  },
});
Object.assign(LAYERS, {
  // her car (white 2001 Acura TL) from the car kit. Tracked: give the same roto/cam/speed/offset/loop as the world layer;
  // the clip's track (assets/car/tracks/<clip>.json) places it and the Seedance car underneath is erased with ink.
  // Untracked: {x, y (ground point), w}. view: chase|rear34|rear|side|front34|top
  car(ctx, L, env, { roto }) {
    const g = ctx.g; let cx, by, w;
    if (L.roto) {
      const id = L.roto, tr = CAR.trackFor(id); if (!tr || !roto.meta(id)) return;
      const ct = roto.clipTime(id, env.lt, { speed: A(L.speed, env, 1), offset: A(L.offset, env, 0), loop: L.loop ?? true });
      const b = CAR.trackBox(tr, ct, camRect(L.cam, env)); if (!b) return;
      cx = (b.x0 + b.x1) / 2; by = b.y1; w = (b.x1 - b.x0) * (L.wScale ?? 1);
    } else { cx = A(L.x, env, 960); by = A(L.y, env, 800); w = A(L.w, env, 500); }
    CAR.drawView(g, L.view || 'chase', cx, by, w, { color: L.color, alpha: A(L.alpha, env, 1), seed: Math.floor(env.lt * 10), lights: L.lights ?? 'tail', rot: L.rot, outline: L.outline, fill: L.fill, erase: !!L.roto });
    if (L.trail) { g.save(); g.globalCompositeOperation = 'lighter'; headlights(g, cx, by - w * 0.2, w * 0.9, 0.25, PAL.red); g.restore(); }
  },
});
Object.assign(LAYERS, {
  rect(ctx, L, env) { const g = L.onType ? ctx.ty : ctx.g; g.fillStyle = L.color || PAL.ink; g.fillRect(A(L.x, env, 0), A(L.y, env, 0), A(L.w, env, DW), A(L.h, env, DH)); },
  glyph(ctx, L, env) { glyph(L.onType === false ? ctx.g : ctx.ty, L.ch, A(L.x, env, 960), A(L.y, env, 540), L.size ?? 200, L.color || PAL.red, L.weight ?? 700); },
});
Object.assign(LAYERS, {
  // MANY RUNS: Monte Carlo rollouts / phase-space trajectories from 'now'. Thin luminous noisy curves, density-shaded;
  // deaths are red terminal ticks at the kill points, the survivor (if any) is cyan. Labels attach to bundles.
  // L: {n, seed, x, y, w, h, kills:[{at (0..1 along x), share, dy (bundle offset), label}], survive (share of runs that reach the end),
  //     survivor (draw the one surviving run), kill (0..1: kill everything but the survivor), progress, ink (paper), alpha, rect}
  rollouts(ctx, L, env) {
    const g = L.onType ? ctx.ty : ctx.g, n = Math.max(0, Math.floor(A(L.n, env, 60))), R0 = rng(L.seed ?? 5);
    const x0 = A(L.x, env, 240), y0 = A(L.y, env, 560), W0 = A(L.w, env, 1500), H0 = A(L.h, env, 760), prog = clamp(A(L.progress, env, 1)), killAll = clamp(A(L.kill, env, 0));
    const kills = L.kills || [{ at: 0.45, share: 0.85, dy: -0.25, label: 'pull over ??' }];
    const ink = !!L.ink, aBase = A(L.alpha, env, 1) * clamp(2.6 / Math.sqrt(Math.max(1, n)) + 0.04, 0.05, 0.6);
    const STEPS = 28, ends = [];
    g.save(); g.lineCap = 'round'; g.lineJoin = 'round';
    g.globalCompositeOperation = ink ? 'source-over' : 'lighter';
    const runs = [];
    for (let i = 0; i < n; i++) {
      const r = R0(); let acc = 0, fate = -1;
      for (let k = 0; k < kills.length; k++) { acc += kills[k].share; if (r < acc) { fate = k; break; } }
      const seed = R0() * 1000, amp = 0.12 + R0() * 0.3, drift = (R0() - 0.5) * 0.9, spread = (R0() + R0() + R0() - 1.5) * (L.spread ?? 0.32);
      let end = fate >= 0 ? kills[fate].at * (0.88 + R0() * 0.2) : 1;
      if (fate < 0 && killAll > 0 && i > 0) end = Math.min(end, 0.25 + R0() * 0.75 * (1 - killAll) + killAll * R0() * 0.6);
      runs.push({ fate, seed, amp, drift, end, dy: (fate >= 0 ? (kills[fate].dy ?? 0) : (L.surviveDy ?? 0.22)) + spread });
    }
    const path = (ru, upto) => {
      const pts = [], m = Math.max(2, Math.ceil(STEPS * upto));
      for (let s = 0; s <= m; s++) {
        const u = Math.min(upto, s / STEPS), fan = Math.pow(u, 0.65);
        const yy = (ru.dy * fan + ru.drift * fan * fan + noise1(u * 3 + ru.seed, 3) * ru.amp * fan + noise1(u * 9 + ru.seed, 4) * ru.amp * 0.3 * fan) * H0;
        pts.push([x0 + u * W0, y0 + yy]);
      }
      return pts;
    };
    // density-shaded bundles
    g.lineWidth = L.lw ?? 1.6;
    for (const ru of runs) {
      const upto = Math.min(ru.end, prog); if (upto <= 0) continue;
      const pts = path(ru, upto);
      g.strokeStyle = rgba(ink ? PAL.ink : PAL.bone, ink ? aBase * 1.4 : aBase);
      g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
      if (ru.end < 1 && prog >= ru.end) ends.push(pts[pts.length - 1]);
    }
    g.globalCompositeOperation = 'source-over';
    // deaths: red terminal ticks
    g.strokeStyle = rgba(PAL.red, Math.min(1, 0.5 + aBase * 2)); g.lineWidth = L.tick ?? 3;
    g.beginPath(); for (const [x, y] of ends) { g.moveTo(x - 6, y - 6); g.lineTo(x + 6, y + 6); g.moveTo(x + 6, y - 6); g.lineTo(x - 6, y + 6); } g.stroke();
    // the survivor
    if (L.survivor && prog > 0) {
      const ru = { seed: 77.7, amp: 0.06, drift: -0.05, dy: L.surviveDy ?? 0.22, end: 1 };
      const pts = path(ru, prog); g.strokeStyle = PAL.cyan; g.lineWidth = L.survivorW ?? 6;
      g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
      env.survivorHead = pts[pts.length - 1];
    }
    // origin + bundle labels (at most 3)
    g.fillStyle = ink ? PAL.ink : PAL.bone; g.beginPath(); g.arc(x0, y0, 9, 0, Math.PI * 2); g.fill();
    if (L.labels !== false) {
      setFont(g, F.mono(L.labelSize ?? 48, 700), 0); g.textBaseline = 'alphabetic';
      for (const k of kills.slice(0, 3)) if (k.label && prog > k.at * 0.8) {
        const lx = x0 + k.at * W0 + 26, ly = y0 + (k.dy ?? 0) * Math.pow(k.at, 0.8) * H0 - 30;
        g.fillStyle = PAL.red; g.fillText(k.label, lx, ly);
      }
      if (L.surviveLabel && prog > 0.85) { g.fillStyle = PAL.cyan; g.fillText(L.surviveLabel, x0 + W0 * 0.86, y0 + (L.surviveDy ?? 0.22) * H0 + 70); }
    }
    g.restore();
  },
  // continuous reverse playback of earlier footage as the base of a rewind section: kick-stepped, with motion echo,
  // graded rewind-cyan (on dark) or multiplied as ink (on paper / red fills). Spans a whole section: the source time is
  // a function of the global time, so consecutive shots continue the same reverse motion.
  async rewindbase(ctx, L, env, data) {
    let t = env.t;
    if (L.kick) { const ks = env.T.kicksIn(L.a, t + 1e-6); if (ks.length) t = ks[ks.length - 1] + Math.min(t - ks[ks.length - 1], 0.12) * (L.slide ?? 1); }
    const p = clamp((t - L.a) / (L.b - L.a));
    const Lr = layer('rwbase', ctx.g.canvas.width, ctx.g.canvas.height), rg = clearLayer(Lr); rg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    rg.fillStyle = PAL.ink; rg.fillRect(0, 0, DW, DH);
    await data.rewindOf({ ...ctx, g: rg }, null, L.from, L.to, p, { echo: L.echo ?? 3, echoDt: L.echoDt ?? 0.12, echoAlpha: 0.55 });
    resetCtx(rg);
    if (L.mode !== 'multiply') { rg.globalCompositeOperation = 'color'; rg.fillStyle = L.tint || '#1FA9A1'; rg.fillRect(0, 0, Lr.width, Lr.height); rg.globalCompositeOperation = 'source-over'; }
    const g = ctx.g; g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalAlpha = A(L.alpha, env, L.mode === 'multiply' ? 0.45 : 0.85); g.globalCompositeOperation = L.mode === 'multiply' ? 'multiply' : 'source-over';
    g.drawImage(Lr, 0, 0); g.restore();
    env.rewindTs = L.from + (L.to - L.from) * p;
  },
});
Object.assign(LAYERS, {
  // storybook page (Braid-like world books): bone paper, serif lines set like a book, small ornament
  storypage(ctx, L, env) {
    const g = ctx.g, ty = ctx.ty; g.fillStyle = PAL.bone; g.fillRect(-10, -10, DW + 20, DH + 20);
    const lines = L.lines || [], px = L.size ?? 64, lead = px * 1.5, x0 = L.x ?? 260;
    let y = (L.y ?? (DH / 2 - (lines.length - 1) * lead / 2 + px * 0.3));
    ty.save(); ty.textBaseline = 'alphabetic';
    lines.forEach((ln, i) => {
      if (ln === '') { y += lead * 0.5; return; }
      const at = (L.stagger ?? 0.35) * i, a = smooth(at, at + 0.5, env.lt);
      setFont(ty, L.italic === false ? F.cmuR(px) : F.cmu(px)); ty.fillStyle = rgba(PAL.ink, a); ty.fillText(ln, x0, y); y += lead;
    });
    // ornament: a small rule with a centred diamond
    const oy = (L.y ?? 0) ? y + 10 : y + 10; ty.fillStyle = rgba(PAL.ink, 0.7 * smooth(0, 0.6, env.lt)); ty.fillRect(DW / 2 - 120, oy, 240, 2);
    ty.save(); ty.translate(DW / 2, oy + 1); ty.rotate(Math.PI / 4); ty.fillRect(-7, -7, 14, 14); ty.restore();
    ty.restore();
  },
  // world card (per attempt): "1 · Time and Compliance", with ATTEMPT 0N small beneath
  worldcard(ctx, L, env) {
    const ty = ctx.ty, a = smooth(0, 0.25, env.lt) * (L.fadeOut ? 1 - smooth(L.fadeOut, L.fadeOut + 0.3, env.lt) : 1);
    ty.save(); ty.textAlign = 'center'; ty.textBaseline = 'alphabetic';
    setFont(ty, F.cmu(L.size ?? 120)); ty.fillStyle = rgba(L.color || PAL.bone, a); ty.fillText(L.title, DW / 2, L.y ?? 540);
    setFont(ty, F.mono(44, 700), 8); ty.fillStyle = rgba(L.sub2 || PAL.boneDim, a); ty.fillText(L.sub ?? '', DW / 2, (L.y ?? 540) + 110);
    ty.restore();
  },
});
Object.assign(LAYERS, {
  // CUBIST SIMULTANEITY: her face (style B) fractured into angular planes that combine the frontal view (J6) and the
  // side view (J1, its nose/cheek aligned onto the frontal face) — multiple attempts at once. Elegant (late-1930s portrait
  // logic), never grotesque: the frontal eyes stay whole and full size; planes offset a little, shift tone, ink seams.
  // L: {front, side, planes (0..6), resolve (0..1: planes converge into one whole face), cx, cy, scale, beatCycle}
  async cubist(ctx, L, env, { roto }) {
    const F = L.front || 'J6', Sd = L.side || 'J1', mf = roto.meta(F), ms = roto.meta(Sd); if (!mf || !mf.celData) return;
    const ctF = roto.clipTime(F, env.lt * (L.speed ?? 0.4) + (L.offset ?? 2.0), { loop: 'pingpong' }), fiF = roto.frameIndex(mf, ctF);
    const cdF = mf.celData[fiF] || mf.celData[String(fiF)]; if (!cdF || !cdF.nose) return;
    const iod = cdF.iod || 160, nose = cdF.nose;
    // place the face: scale so the face is big in frame, centred at (cx, cy)
    const sc = (L.scale ?? 2.3), cx = L.cx ?? 960, cy = L.cy ?? 520;
    const rect = { x: cx - nose[0] * sc, y: cy - nose[1] * sc, w: 1920 * sc, h: 1080 * sc };
    const Lf = layer('cub_front', ctx.g.canvas.width, ctx.g.canvas.height), fg = clearLayer(Lf); fg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    roto.jade(fg, F, ctF, { rect, mouth: clamp((env.T.e('vocal', env.t) - 0.18) * 1.6) });
    let haveSide = false; const Ls = layer('cub_side', ctx.g.canvas.width, ctx.g.canvas.height), sg = clearLayer(Ls); sg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
    if (ms && ms.celData) {
      const ctS = roto.clipTime(Sd, env.lt * 0.4 + 1.5, { loop: 'pingpong' }), fiS = roto.frameIndex(ms, ctS), cdS = ms.celData[fiS] || ms.celData[String(fiS)];
      if (cdS && cdS.N && cdS.E) {   // align the profile's nose tip onto the frontal nose, scaled by eye–nose distance
        const dd = Math.hypot(cdS.N[0] - cdS.E[0], cdS.N[1] - cdS.E[1]), k = sc * (iod * 0.62) / dd;
        const rs = { x: cx - cdS.N[0] * k + iod * sc * 0.06, y: cy - cdS.N[1] * k, w: 1920 * k, h: 1080 * k };
        roto.jade(sg, Sd, ctS, { rect: rs, mouth: 0 }); haveSide = true;
      }
    }
    resetCtx(fg); resetCtx(sg);
    const res = clamp(A(L.resolve, env, 0)), nP = Math.max(0, Math.round(A(L.planes, env, 3) * (1 - res)));
    const g = ctx.g, S = ctx.S, cyc = L.beatCycle ? env.b.i : 0;
    g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
    if (L.clip) { const [qx, qy, qw, qh] = L.clip; g.beginPath(); g.rect(qx * S, qy * S, qw * S, qh * S); g.clip(); g.fillStyle = L.bg || PAL.ink; g.fillRect(qx * S, qy * S, qw * S, qh * S); }
    g.drawImage(Lf, 0, 0);                        // the whole frontal face is the base (eyes stay whole)
    if (nP > 0) {
      const R0 = rng((L.seed ?? 3) + cyc * 7.31), u = iod * sc * S;
      const C = [cx * S, cy * S];
      for (let p = 0; p < nP; p++) {
        // an angular plane: a wedge from near the face centre outward (avoid covering both eyes)
        const a0 = (p / nP) * Math.PI * 2 + R0() * 0.6 + 0.4, a1 = a0 + 0.7 + R0() * 0.6, r0 = u * (0.15 + R0() * 0.25), r1 = u * (2.2 + R0());
        const poly = [[C[0] + Math.cos(a0) * r0, C[1] + Math.sin(a0) * r0 + u * 0.25], [C[0] + Math.cos(a0) * r1, C[1] + Math.sin(a0) * r1], [C[0] + Math.cos(a1) * r1, C[1] + Math.sin(a1) * r1], [C[0] + Math.cos(a1) * r0, C[1] + Math.sin(a1) * r0 + u * 0.25]];
        const src = haveSide && (p % 2 === 0) ? Ls : Lf, off = (1 - res) * u * 0.06;
        g.save(); g.beginPath(); poly.forEach((q, i) => (i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.closePath(); g.clip();
        g.drawImage(src, (R0() - 0.5) * off, (R0() - 0.5) * off);
        // tone shift per plane (flat): warm shadow / sodium / cyan light / grey
        const tones = ['rgba(150,120,100,0.28)', 'rgba(255,159,28,0.16)', 'rgba(61,242,230,0.14)', 'rgba(120,120,120,0.22)'];
        g.globalCompositeOperation = 'multiply'; g.fillStyle = tones[(p + cyc) % tones.length]; g.fillRect(0, 0, g.canvas.width, g.canvas.height);
        g.restore();
        // ink seam along the plane edge
        g.strokeStyle = 'rgba(7,8,10,0.9)'; g.lineWidth = 3 * S; g.beginPath(); poly.forEach((q, i) => (i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]))); g.closePath(); g.stroke();
      }
    }
    g.restore();
  },
  // Guernica-inflected freeze: angular planes in ink/bone/greys + the bare-bulb lamp-eye (spiky radiant shape) above
  guernica(ctx, L, env) {
    const g = ctx.g, R0 = rng(L.seed ?? 9), n = L.n ?? 7, [x, y, w, h] = L.rect || [0, 0, DW, DH];
    g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
    for (let i = 0; i < n; i++) {
      const px = x + R0() * w, py = y + R0() * h, a = R0() * Math.PI, r1 = w * (0.25 + R0() * 0.4), r2 = h * (0.2 + R0() * 0.4);
      g.beginPath(); g.moveTo(px, py); g.lineTo(px + Math.cos(a) * r1, py + Math.sin(a) * r1); g.lineTo(px + Math.cos(a + 1.9) * r2, py + Math.sin(a + 1.9) * r2); g.closePath();
      g.globalCompositeOperation = 'multiply'; g.fillStyle = ['rgba(120,118,112,0.35)', 'rgba(60,58,56,0.3)', 'rgba(200,196,186,0.4)'][i % 3]; g.fill();
      g.globalCompositeOperation = 'source-over'; g.strokeStyle = 'rgba(7,8,10,0.85)'; g.lineWidth = 3; g.stroke();
    }
    g.restore();
    // the lamp-eye: a spiky radiant bulb in bone with an ink pupil
    const bx = L.bx ?? x + w * 0.5, by = L.by ?? y + 70, R = L.br ?? 70;
    g.save(); g.fillStyle = PAL.bone; g.strokeStyle = PAL.ink; g.lineWidth = 4; g.beginPath();
    for (let k = 0; k < 28; k++) { const a = k / 28 * Math.PI * 2, rr = k % 2 ? R * 0.55 : R * (1 + 0.25 * hash(k, 3)); g.lineTo(bx + Math.cos(a) * rr, by + Math.sin(a) * rr * 0.75); }
    g.closePath(); g.fill(); g.stroke();
    g.fillStyle = PAL.ink; g.beginPath(); g.ellipse(bx, by, R * 0.32, R * 0.2, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = PAL.bone; g.beginPath(); g.arc(bx - R * 0.08, by - R * 0.04, R * 0.07, 0, Math.PI * 2); g.fill();
    g.restore();
  },
});
const TREES = new Map();

// normalised Lake Shore Drive outline (lake to the right) and the aerial-curve stroke
const LSD = [[0.35, 1], [0.4, 0.85], [0.42, 0.7], [0.5, 0.58], [0.55, 0.45], [0.52, 0.32], [0.6, 0.2], [0.7, 0.1], [0.72, 0]];
const LSD_AERIAL = [[0.45, 1.02], [0.38, 0.85], [0.32, 0.68], [0.3, 0.55], [0.33, 0.4], [0.4, 0.28], [0.5, 0.19], [0.65, 0.11], [0.82, 0.06], [1.0, 0.03]];

function roundRect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }

export async function drawLayers(ctx, list, env, data) {
  for (const L of list) {
    if (L.when && !L.when(env)) continue;
    if (L.t0 != null && env.lt < L.t0) continue; if (L.t1 != null && env.lt >= L.t1) continue;
    const f = LAYERS[L.type]; if (!f) throw new Error('unknown layer ' + L.type);
    ctx.g.save(); ctx.ty.save();
    await f(ctx, L, env, data);
    ctx.g.restore(); ctx.ty.restore();
  }
}
