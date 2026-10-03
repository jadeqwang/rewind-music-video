// freeze → VARIANCE REPORT, written by the field agent (copy: docs/COPY_v9.md). Two frames of muzzle-flash red, then the
// death becomes the agency's form: bone paper, the frozen frame as a halftone print, the bullet hanging in it, typed rows,
// a redacted agent name + signature, a red ✗ / PRUNED stamp. params: {source, case, report:{case, sub, classif, anomaly,
// what, rows:[[key, value, kind('field'|'text'|'action'|'agent')]]}, ghostRows, bullet, unwrite:[t0, t1]}
import { DW, DH, PAL, clamp, smooth, lerp, easeOutBack, rgba, layer, resetCtx, fin } from '../core.js';
import { bullet, fillInk } from '../fx.js';
import { setFont, F, redactedLine } from '../type.js';
import { AGENCY } from '../agency.js';

export const PH = { x: 100, y: 205, w: 640, h: 360 };    // the photo print (16:9)
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
  // UN-WRITING: complete at the shot; through the silence it erases itself (p.unwrite = [t0, t1], song time), stepped on
  // twos with a stutter on each kick. Order (COPY_v9): the PRUNED stamp + every pruned/terminated indicator FIRST, then the
  // signature retracts, text rows backspace (bottom-up), redaction bars retract RIGHT→LEFT, the photo un-develops, the
  // fields empty last. The pre-printed form (header, CASE 0001, keys) never erases: they're still on case 1.
  const uw = p.unwrite || [Infinity, Infinity];
  let w = clamp((Math.floor(t * 15) / 15 - uw[0]) / Math.max(0.05, uw[1] - uw[0]));
  if (w > 0 && w < 1 && data.T) w = clamp(w - 0.04 * data.T.kick(t, 0.06));
  const seg = (a, b) => clamp((w - a) / (b - a));   // 0 = still written, 1 = gone
  const typ = (s_, a, b) => { const r = seg(a, b), n = Math.round(s_.length * (1 - r)); return { s: s_.slice(0, n), cur: r > 0 && r < 1 }; };
  const CUR = '▌', R = p.report || {}, rows = R.rows || [];
  const photoGone = seg(0.6, 0.82);
  ctx.overAlpha = 1 - photoGone;
  g.fillStyle = `rgba(7,8,10,${0.13 * (1 - photoGone)})`; g.fillRect(PH.x + 8, PH.y + 10, PH.w, PH.h);
  g.globalAlpha = 1 - photoGone; g.drawImage(L, 0, 0, L.width, L.height, PH.x, PH.y, PH.w, PH.h); g.globalAlpha = 1;
  g.strokeStyle = PAL.ink; g.lineWidth = 3; g.strokeRect(PH.x, PH.y, PH.w, PH.h);
  P.htRect = [PH.x, PH.y, PH.w, PH.h]; P.htAmt = 1 - photoGone; P.htCell = 5.5;
  const ink = PAL.ink, KX = 100, VX = 375, RY0 = 652, RDY = 48, xr = 800, FM = F.mono(42, 400);
  // palimpsest: the re-opened case carries a faint ghost of the first, erased report's typing
  if (p.ghostRows) { ty.save(); ty.globalAlpha = 0.07; setFont(ty, FM, 1); ty.fillStyle = ink; p.ghostRows.forEach((v, i) => ty.fillText(v, VX + 8, RY0 + i * RDY + 5)); ty.restore(); }
  // header + sub line (pre-printed)
  ty.textBaseline = 'alphabetic'; ty.fillStyle = ink;
  redactedLine(ty, [...AGENCY.header, '·', 'VARIANCE REPORT'], KX, 106, F.mono(42, 700), ink, '#000');
  setFont(ty, F.mono(42, 700), 2); ty.textAlign = 'right'; ty.fillText(R.case || 'CASE 0001', DW - 90, 106); ty.textAlign = 'left';
  setFont(ty, F.mono(42, 400), 1); ty.fillText(R.sub || '', KX, 160);
  if (R.classif) { setFont(ty, F.mono(42, 700), 3); ty.textAlign = 'right'; ty.fillText(R.classif, DW - 90, 1045); ty.textAlign = 'left'; }   // classification at the page foot
  ty.fillRect(KX, 180, DW - 190, 3);
  const tw = (str, x, y, font, col, a, b, track = 1) => { const o = typ(str, a, b); setFont(ty, font, track); ty.fillStyle = col; ty.fillText(o.s + (o.cur ? CUR : ''), x, y); return o; };
  // ANOMALY 0n + what (fields: empty last / text)
  tw(R.anomaly || `ANOMALY ${pad2(p.case ?? 1)}`, xr, 285, F.mono(76, 700), ink, 0.88, 0.97, 2);
  { const wt = R.what || 'suspected unauthorized rewind', k = wt.indexOf(' \u00b7 ');   // long subtitles wrap after the first ' · '
    if (wt.length > 34 && k > 0) { tw(wt.slice(0, k + 2), xr, 350, F.mono(44, 700), PAL.amber, 0.54, 0.58); tw(wt.slice(k + 3), xr, 402, F.mono(44, 700), PAL.amber, 0.5, 0.54); }
    else tw(wt, xr, 350, F.mono(44, 700), PAL.amber, 0.5, 0.58); }
  // rows: keys pre-printed; values erase by kind — action first, text bottom-up, fields last
  const texts = rows.map((r, i) => i).filter(i => rows[i][2] === 'text').reverse();
  rows.forEach(([k, v, kind], i) => {
    const y = RY0 + i * RDY; setFont(ty, FM, 1); ty.fillStyle = rgba(ink, 0.6); ty.fillText(k, KX, y);
    if (kind === 'action') { const o = tw(v, VX, y, FM, ink, 0.02, 0.1); const tag = typ('[PRUNED]', 0, 0.04); setFont(ty, F.mono(42, 700), 1); ty.fillStyle = PAL.red; ty.textAlign = 'right'; ty.fillText(tag.s, DW - 90, y); ty.textAlign = 'left'; }
    else if (kind === 'agent') {   // redacted agent name (bar retracts right→left) + signature retracting along its stroke
      const bw = 1 - seg(0.55, 0.62); if (bw > 0) redactedLine(ty, [{ bar: 9 * bw }], VX, y, FM, ink, '#000');   // 9 cells, retracting right→left
      const keep = 1 - seg(0.1, 0.2), pts = sigPath(p.case ?? 1), n = Math.floor(pts.length * keep);
      if (n > 1) { ty.save(); ty.strokeStyle = '#1B2A6B'; ty.lineWidth = 3.2; ty.lineCap = 'round'; ty.lineJoin = 'round'; ty.beginPath();
        for (let q = 0; q < n; q++) { const [sx, sy] = pts[q]; q ? ty.lineTo(VX + 300 + sx, y - 12 + sy) : ty.moveTo(VX + 300 + sx, y - 12 + sy); } ty.stroke(); ty.restore(); }
    } else if (kind === 'field') tw(v, VX, y, FM, ink, 0.86 + 0.03 * i / rows.length, 0.94 + 0.03 * i / rows.length);
    else { const r = texts.indexOf(i), a = 0.2 + r * (0.3 / Math.max(1, texts.length)); tw(v, VX, y, FM, ink, a, a + 0.3 / Math.max(1, texts.length)); }
  });
  // the stamp: ✗ + boxed PRUNED over the print — lifts off FIRST (scales up, ink fades)
  const lift = seg(0, 0.06);
  if (lift < 1) {
    const sc = 0.62 * (1 + 0.25 * lift);
    ty.save(); ty.globalAlpha = 0.92 * (1 - lift); ty.translate(PH.x + PH.w - 150, PH.y + PH.h - 170 - 30 * lift); ty.rotate(-0.12); ty.scale(sc, sc);
    setFont(ty, F.mono(300, 700)); ty.fillStyle = PAL.red; ty.textAlign = 'center'; ty.textBaseline = 'middle'; ty.fillText('✗', 0, 0);
    setFont(ty, F.mono(56, 700), 6); const sw = ty.measureText('PRUNED').width;
    ty.strokeStyle = PAL.red; ty.lineWidth = 7; ty.strokeRect(-sw / 2 - 22, 150, sw + 44, 86); ty.fillText('PRUNED', 0, 195);
    ty.restore();
  }
  // the player's prompt (blinks while the form erases itself)
  if (w > 0) { setFont(ty, F.mono(46, 700), 2); ty.fillStyle = rgba(PAL.cyan, Math.floor(t * 3) % 2 ? 1 : 0.4); ty.fillText('hold ◀◀ to rewind', xr, 545); }
  P.zoom = 1.0 + 0.02 * smooth(0, shot.t1 - shot.t0, lt);
  P.ca = 0.8; P.bloom = 0; P.grain = 0.05; P.vignette = 0.18; P.typeCA = 0.1;
}
