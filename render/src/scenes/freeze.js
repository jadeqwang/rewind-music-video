// freeze: the shot. The source shot is held on its last drawing (Superhot stillness), two impact frames
// (two-tone invert), then the bullet hangs in the air as one drawn line. ✗ is stamped on the ATTEMPT counter.
// params: {source (shot id), bullet:{x,y,len,angle}, attempt, caption}
import { DW, DH, PAL, clamp, smooth, lerp } from '../core.js';
import { bullet } from '../fx.js';
import { attempt } from '../hud.js';
import { setFont, F } from '../type.js';

export async function draw(ctx, lt, t, shot, { drawShot, shotById }) {
  const { g, ty } = ctx, p = shot.params, src = shotById(p.source);
  const hold = src.t1 - 1 / 30;
  const dummy = {};
  await drawShot(src, hold, g, ty, dummy, { rewinding: false, frozen: true });
  // the world desaturates toward bone/ink while frozen (light stops moving)
  g.save(); g.globalCompositeOperation = 'saturation'; g.fillStyle = `rgba(0,0,0,${0.55 * smooth(0.05, 0.35, lt)})`; g.fillRect(0, 0, DW, DH); g.restore();
  const b = p.bullet || { x: 760, y: 470, len: 1100, angle: 0.03 };
  if (lt >= 2 / 30) bullet(g, { ...b, x: b.x - 6 * lt });
  if (p.attempt) { ty.save(); ty.clearRect(DW - 400, 0, 400, 180); ty.restore(); attempt(ty, { n: p.attempt, failed: smooth(0.08, 0.3, lt), sub: 'TERMINATED' }); }
  if (p.caption) { setFont(ty, F.mono(22), 6); ty.fillStyle = `rgba(236,230,216,${smooth(0.15, 0.3, lt)})`; ty.textAlign = 'center'; ty.fillText(p.caption, DW / 2, 1010); ty.textAlign = 'left'; }
  const P = ctx.post;
  P.invert = lt < 2 / 30 ? 1 : 0;
  P.flash = lt < 1 / 30 ? 0.0 : (lt < 3 / 30 ? 0.35 : 0);
  P.zoom = 1 + 0.03 * smooth(0, shot.t1 - shot.t0, lt);
  P.ca = 2.2; P.bloom = 0.7; P.grain = 0.07; P.shakeX = lt < 3 / 30 ? 6 : 0; P.shakeY = lt < 3 / 30 ? -4 : 0;
}
