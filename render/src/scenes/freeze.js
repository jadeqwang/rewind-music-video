// freeze → VARIANCE REPORT (the agency's file on the anomaly). Two frames of muzzle-flash red, then the death becomes a page of the dossier: bone paper,
// the frozen frame as a halftone photo print (GL AM screen), the bullet hanging in it, mono annotations, redaction
// bars and a red ✗ / TERMINATED stamp. params: {source (shot id), case (n), move:{n,move,nag}, loc, eval, bullet, file}
import { DW, DH, PAL, clamp, smooth, lerp, easeOutBack, rgba, layer, resetCtx, fin } from '../core.js';
import { bullet, fillInk } from '../fx.js';
import { setFont, F, redactedLine } from '../type.js';
import { annotation } from '../hud.js';
import { AGENCY } from '../agency.js';

const PH = { x: 100, y: 190, w: 1150, h: 647 };    // the photo print (16:9)
const pad2 = n => String(n).padStart(2, '0');
// a deterministic signature: looping cursive strokes (polyline, ~170 points), different per case
function sigPath(seed) {
  const pts = []; let x = 0;
  for (let k = 0; k < 170; k++) { const u = k / 169, f = 5 + (seed % 3); x = u * 380;
    pts.push([x + 16 * Math.sin(u * f * Math.PI * 2 + seed), -18 * Math.sin(u * f * Math.PI * 2 * 0.5 + 0.7) * (1 - 0.5 * u) - 10 * Math.cos(u * 23 + seed) * Math.exp(-u * 2)]); }
  return pts;
}

export async function draw(ctx, lt, t, shot, data) {
  const { drawShot, shotById } = data;
  const { g, ty } = ctx, p = shot.params, src = shotById(p.source);
  const hold = src.t1 - 1 / 30, f = Math.floor(lt * 30 + 1e-3), P = ctx.post;
  if (f < 2) {   // muzzle flash: flat siren red, the silhouettes punched out
    await drawShot(src, hold, g, ty, {}, { mode: 'print' });
    g.save(); g.globalCompositeOperation = 'multiply'; g.fillStyle = PAL.red; g.fillRect(0, 0, DW, DH); g.restore();
    ty.clearRect(0, 0, DW, DH);
    P.shakeX = f ? -8 : 10; P.shakeY = f ? 5 : -6; P.zoom = 1.04; P.ca = 6; P.bloom = 0; P.grain = 0.06;
    return;
  }
  // the photo: the frozen frame exactly as it was lit, rendered off-screen, then printed into the page
  const L = layer('casefile_photo', g.canvas.width, g.canvas.height), lg = L.ctx, LT = layer('casefile_phototype', g.canvas.width, g.canvas.height);
  resetCtx(lg); lg.clearRect(0, 0, L.width, L.height); lg.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
  const lty = LT.ctx; resetCtx(lty); lty.clearRect(0, 0, LT.width, LT.height); lty.setTransform(ctx.S, 0, 0, ctx.S, 0, 0);
  await drawShot(src, hold, lg, lty, {}, { rewinding: true });
  const b = p.bullet || { x: 700, y: 452, len: 1300, angle: 0.025 };
  bullet(lg, { ...b, color: PAL.bone });
  fillInk(g, PAL.bone);
  // UN-WRITING (user): the report starts complete; as the rewind kicks in (p.unwrite = [t0, t1], song time) it erases itself
  // in reverse — stamp lifts, signature retracts, text backspaces, bars retract, the photo un-develops, fields empty last —
  // ending on a blank form that still says CASE 0001 (the case number never increments). Kick-stepped stutter, on twos.
  const uw = p.unwrite || [Infinity, Infinity];
  let w = clamp((Math.floor(t * 15) / 15 - uw[0]) / Math.max(0.05, uw[1] - uw[0]));
  if (w > 0 && w < 1 && data.T) w = clamp(w - 0.04 * data.T.kick(t, 0.06));   // each kick catches the eraser for a frame
  const seg = (a, b) => clamp((w - a) / (b - a));   // 0 = still written, 1 = gone
  const typ = (s_, a, b) => { const r = seg(a, b), n = Math.round(s_.length * (1 - r)); return { s: s_.slice(0, n), cur: r > 0 && r < 1 }; };
  const CUR = '▌';
  const photoGone = seg(0.38, 0.86);
  ctx.overAlpha = 1 - photoGone;   // the 'over' layers (Guernica planes, cubist clip) un-develop with the print
  const sh = 0.6 * (1 - photoGone);
  g.fillStyle = `rgba(7,8,10,${0.22 * sh})`; g.fillRect(PH.x + 10, PH.y + 12, PH.w, PH.h);
  g.globalAlpha = 1 - photoGone; g.drawImage(L, 0, 0, L.width, L.height, PH.x, PH.y, PH.w, PH.h); g.globalAlpha = 1;
  g.strokeStyle = PAL.ink; g.lineWidth = 3; g.strokeRect(PH.x, PH.y, PH.w, PH.h);   // the empty print box stays (a blank form)
  P.htRect = [PH.x, PH.y, PH.w, PH.h]; P.htAmt = 1 - photoGone; P.htCell = 6.5;
  // palimpsest: the re-filed case carries a faint ghost of the first, erased report's typing
  const ink = PAL.ink, x1 = 1320;
  if (p.ghost) {
    ty.save(); ty.globalAlpha = 0.1; setFont(ty, F.mono(46, 400), 1); ty.fillStyle = ink;
    ty.fillText(p.ghost.anomaly, x1 + 6, 268); ty.fillText(p.ghost.loc, x1 + 156, 486); ty.fillText(p.ghost.move, x1 + 6, 646); ty.fillText('∴ branch pruned. rewinding.', PH.x + 8, 946);
    ty.restore();
  }
  // header (pre-printed form: never erased): agency · VARIANCE REPORT, CASE 0001 right
  setFont(ty, F.mono(42, 700), 3); ty.fillStyle = ink; ty.textBaseline = 'alphabetic';
  redactedLine(ty, [...AGENCY.header, '·', 'VARIANCE REPORT'], PH.x, 110, F.mono(42, 700), ink, '#000');
  setFont(ty, F.mono(42, 700), 3); ty.textAlign = 'right'; ty.fillText('CASE 0001', DW - 90, 110); ty.textAlign = 'left';
  ty.fillRect(PH.x, 140, DW - 190, 3);
  // typed fields (written order: ANOMALY → type → values → move → agents → note → signature → stamp; erased in reverse)
  const tt = fin(src.t1), mm = Math.floor(tt / 60), ss = (tt - mm * 60).toFixed(2).padStart(5, '0');
  const tw = (str, x, y, font, col, a, b, track = 1) => { const o = typ(str, a, b); setFont(ty, font, track); ty.fillStyle = col; ty.fillText(o.s + (o.cur ? CUR : ''), x, y); };
  tw(`ANOMALY ${pad2(p.case ?? 1)}`, x1, 262, F.mono(76, 700), ink, 0.62, 0.74, 2);
  tw('unauthorized rewind', x1, 330, F.mono(44, 700), PAL.amber, 0.5, 0.62);
  const rows = [['t', `${pad2(mm)}:${ss}`], ['LOC', p.loc ?? 'LSD NB'], ['EVAL', p.eval ?? '−#1']];
  rows.forEach(([k, v], i) => { const y = 410 + i * 70; setFont(ty, F.mono(46, 400), 1); ty.fillStyle = rgba(ink, 0.6); ty.fillText(k, x1, y);   // labels are pre-printed
    tw(v, x1 + 150, y, F.mono(46, 400), k === 'EVAL' ? PAL.red : ink, 0.86 + i * 0.03, 0.93 + i * 0.03); });   // values empty last
  if (p.move) { const o = typ(`${p.move.n ?? 1}. ${p.move.move}`, 0.3, 0.42); setFont(ty, F.mono(46, 400), 1); ty.fillStyle = ink; ty.fillText(o.s + (o.cur ? CUR : ''), x1, 640);
    if (seg(0.3, 0.32) < 1 && o.s.length === `${p.move.n ?? 1}. ${p.move.move}`.length && p.move.nag) { const mw = ty.measureText(o.s).width; setFont(ty, F.mono(53, 700), 0); ty.fillStyle = p.move.nag === '??' ? PAL.red : PAL.sodium; ty.fillText(p.move.nag, x1 + mw + 10, 640); } }
  const bars = 1 - seg(0.24, 0.38);   // redaction bars retract to zero width
  { const o = typ('AGENTS', 0.42, 0.5); redactedLine(ty, [o.s || ' ', { bar: 5 * bars }], x1, 714, F.mono(46, 400), ink, '#000'); }
  { const o = typ('NO WARNING', 0.42, 0.5); redactedLine(ty, [{ bar: 3 * bars }, o.s || ' '], x1, 784, F.mono(46, 400), ink, '#000'); }
  tw('∴ branch pruned. rewinding.', PH.x, 940, F.mono(46, 400), ink, 0.16, 0.3);
  // signature: a light-pen scrawl on the AGENT line, retracting along its own stroke path (reverse write)
  const sgx = 720; setFont(ty, F.mono(42, 400), 2); ty.fillStyle = rgba(ink, 0.55); ty.fillText('AGENT', sgx, 1012); ty.fillRect(sgx + 150, 1016, 400, 2);
  { const keep = 1 - seg(0.07, 0.2), pts = sigPath(p.case ?? 1), n = Math.floor(pts.length * keep);
    if (n > 1) { ty.save(); ty.strokeStyle = '#1B2A6B'; ty.lineWidth = 3.2; ty.lineCap = 'round'; ty.lineJoin = 'round'; ty.beginPath();
      for (let k = 0; k < n; k++) { const [sx, sy] = pts[k]; k ? ty.lineTo(sgx + 170 + sx, 1000 + sy) : ty.moveTo(sgx + 170 + sx, 1000 + sy); } ty.stroke(); ty.restore(); } }
  // the stamp: big red ✗ + boxed PRUNED; it lifts off first (scales up, ink fades)
  const lift = seg(0, 0.1);
  if (lift < 1) {
    const sc = 1 + 0.25 * lift;
    ty.save(); ty.globalAlpha = 0.92 * (1 - lift); ty.translate(PH.x + PH.w - 230, PH.y + PH.h - 250 - 40 * lift); ty.rotate(-0.12); ty.scale(sc, sc);
    setFont(ty, F.mono(300, 700)); ty.fillStyle = PAL.red; ty.textAlign = 'center'; ty.textBaseline = 'middle'; ty.fillText('✗', 0, 0);
    setFont(ty, F.mono(52, 700), 6); const sw = ty.measureText('PRUNED').width;
    ty.strokeStyle = PAL.red; ty.lineWidth = 6; ty.strokeRect(-sw / 2 - 22, 150, sw + 44, 82); ty.fillText('PRUNED', 0, 193);
    ty.restore();
  }
  // the player's prompt (blinks while the form erases itself)
  if (w > 0) { setFont(ty, F.mono(46, 700), 2); ty.fillStyle = rgba(PAL.cyan, Math.floor(t * 3) % 2 ? 1 : 0.4); ty.fillText('hold ◀◀ to rewind', PH.x, 1012); }
  P.zoom = 1.0 + 0.02 * smooth(0, shot.t1 - shot.t0, lt);
  P.ca = 0.8; P.bloom = 0; P.grain = 0.05; P.vignette = 0.18; P.typeCA = 0.1;
}
