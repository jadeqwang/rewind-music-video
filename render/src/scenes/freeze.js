// freeze → CASE FILE. Two frames of muzzle-flash red, then the death becomes a page of the dossier: bone paper,
// the frozen frame as a halftone photo print (GL AM screen), the bullet hanging in it, mono annotations, redaction
// bars and a red ✗ / TERMINATED stamp. params: {source (shot id), case (n), move:{n,move,nag}, loc, eval, bullet, file}
import { DW, DH, PAL, clamp, smooth, lerp, easeOutBack, rgba, layer, resetCtx, fin } from '../core.js';
import { bullet, fillInk } from '../fx.js';
import { setFont, F, redactedLine } from '../type.js';
import { annotation } from '../hud.js';

const PH = { x: 100, y: 190, w: 1150, h: 647 };    // the photo print (16:9)
const pad2 = n => String(n).padStart(2, '0');

export async function draw(ctx, lt, t, shot, { drawShot, shotById }) {
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
  const sh = 0.6 * smooth(0, 0.2, lt);   // the print settles onto the page
  g.fillStyle = `rgba(7,8,10,${0.22 * sh})`; g.fillRect(PH.x + 10, PH.y + 12, PH.w, PH.h);
  g.drawImage(L, 0, 0, L.width, L.height, PH.x, PH.y, PH.w, PH.h);
  g.strokeStyle = PAL.ink; g.lineWidth = 3; g.strokeRect(PH.x, PH.y, PH.w, PH.h);
  P.htRect = [PH.x, PH.y, PH.w, PH.h]; P.htAmt = 1; P.htCell = 6.5;
  // page furniture (type layer: crisp, not screened)
  const ink = PAL.ink, x1 = 1320;
  setFont(ty, F.mono(42, 700), 3); ty.fillStyle = ink; ty.textBaseline = 'alphabetic';
  ty.fillText(p.file ?? 'FILE 65-HQ-', PH.x, 110); const fw = ty.measureText(p.file ?? 'FILE 65-HQ-').width;
  ty.fillRect(PH.x + fw + 6, 74, 230, 44);
  ty.textAlign = 'right'; ty.fillText(`PAGE ${pad2(p.case ?? 1)}`, DW - 90, 110); ty.textAlign = 'left';
  ty.fillRect(PH.x, 140, DW - 190, 3);
  setFont(ty, F.mono(76, 700), 2); ty.fillText(`CASE ${pad2(p.case ?? 1)}`, x1, 270);
  const tt = fin(src.t1), mm = Math.floor(tt / 60), ss = (tt - mm * 60).toFixed(2).padStart(5, '0');
  const rows = [['t', `${pad2(mm)}:${ss}`], ['LOC', p.loc ?? 'LSD NB'], ['EVAL', p.eval ?? '−#1']];
  setFont(ty, F.mono(46, 400), 1);
  rows.forEach(([k, v], i) => { const y = 370 + i * 74; ty.globalAlpha = smooth(0.05 + i * 0.05, 0.15 + i * 0.05, lt); ty.fillStyle = rgba(ink, 0.6); ty.fillText(k, x1, y); ty.fillStyle = k === 'EVAL' ? PAL.red : ink; ty.fillText(v, x1 + 150, y); });
  ty.globalAlpha = smooth(0.2, 0.3, lt);
  if (p.move) annotation(ty, { ...p.move, x: x1, y: 620, size: 46, ink: true });
  redactedLine(ty, ['AGENTS', { bar: 5 }], x1, 700, F.mono(46, 400), ink, '#000');
  redactedLine(ty, [{ bar: 3 }, 'NO WARNING'], x1, 774, F.mono(46, 400), ink, '#000');
  ty.globalAlpha = 1;
  setFont(ty, F.mono(46, 400), 1); ty.fillStyle = ink; ty.fillText('∴ attempt terminated. rewinding.', PH.x, 940);
  // the stamp: big red ✗ over the print + boxed TERMINATED, slammed in with a small overshoot
  const su = clamp((lt - 0.12) / 0.12);
  if (su > 0) {
    const sc = lerp(1.35, 1, easeOutBack(su));
    ty.save(); ty.globalAlpha = clamp(su * 2) * 0.92; ty.translate(PH.x + PH.w - 230, PH.y + PH.h - 250); ty.rotate(-0.12); ty.scale(sc, sc);
    setFont(ty, F.mono(300, 700)); ty.fillStyle = PAL.red; ty.textAlign = 'center'; ty.textBaseline = 'middle'; ty.fillText('✗', 0, 0);
    setFont(ty, F.mono(52, 700), 6); const tw = ty.measureText('TERMINATED').width;
    ty.strokeStyle = PAL.red; ty.lineWidth = 6; ty.strokeRect(-tw / 2 - 22, 150, tw + 44, 82); ty.fillText('TERMINATED', 0, 193);
    ty.restore();
  }
  P.zoom = 1.0 + 0.02 * smooth(0, shot.t1 - shot.t0, lt);
  P.ca = 0.8; P.bloom = 0; P.grain = 0.05; P.vignette = 0.18; P.typeCA = 0.1;
}
