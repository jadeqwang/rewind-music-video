// freeze: the shot. The source shot is held on its last drawing (Superhot stillness), two impact frames
// (two-tone invert), then the bullet hangs in the air as one drawn line. ✗ is stamped on the ATTEMPT counter.
// params: {source (shot id), bullet:{x,y,len,angle}, attempt, caption}
import { DW, DH, PAL, clamp, smooth, lerp } from '../core.js';
import { bullet } from '../fx.js';
import { attempt } from '../hud.js';
import { setFont, F } from '../type.js';

export async function draw(ctx, lt, t, shot, { drawShot, shotById }) {
  const { g, ty } = ctx, p = shot.params, src = shotById(p.source);
  const hold = src.t1 - 1 / 30, f = Math.floor(lt * 30 + 1e-3);
  const P = ctx.post;
  if (f < 2) {
    // muzzle flash: two frames of flat siren red, the silhouettes punched out in ink
    await drawShot(src, hold, g, ty, {}, { mode: 'print' });
    g.save(); g.globalCompositeOperation = 'multiply'; g.fillStyle = PAL.red; g.fillRect(0, 0, DW, DH); g.restore();
    ty.clearRect(0, 0, DW, DH);
    P.shakeX = f ? -8 : 10; P.shakeY = f ? 5 : -6; P.zoom = 1.04; P.ca = 6; P.bloom = 0; P.grain = 0.06;
    return;
  }
  // then the file photograph: bone stock, ink contours, black redactions, the bullet hanging in the air
  await drawShot(src, hold, g, ty, {}, { mode: 'print' });
  const b = p.bullet || { x: 760, y: 470, len: 1100, angle: 0.03 };
  bullet(g, { ...b, x: b.x - 4 * lt, color: PAL.ink, comp: 'source-over' });
  ty.clearRect(0, 0, DW, DH);
  attempt(ty, { n: p.attempt ?? 1, failed: smooth(0.1, 0.3, lt), sub: 'TERMINATED', ink: true });
  if (p.caption) { setFont(ty, F.mono(22), 6); ty.fillStyle = PAL.ink; ty.textAlign = 'center'; ty.fillText(p.caption, DW / 2, 1010); ty.textAlign = 'left'; }
  P.zoom = 1.0 + 0.025 * smooth(0, shot.t1 - shot.t0, lt);
  P.ca = 1.2; P.bloom = 0; P.grain = 0.06; P.vignette = 0.15;
}
