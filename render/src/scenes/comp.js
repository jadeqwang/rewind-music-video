// comp: a shot built from a stack of layers (see layers.js). params: {layers:[...], post: {...} | env => {...}, bg}
import { DW, DH, PAL, clamp } from '../core.js';
import { drawLayers } from '../layers.js';

export async function draw(ctx, lt, t, shot, data) {
  const p = shot.params, T = data.T, dur = shot.t1 - shot.t0;
  const env = { lt, t, dur, u: clamp(lt / dur), T, k: T.kick(t, 0.08), b: T.beatPhase(t), shot, ctx };
  ctx.g.fillStyle = p.bg || PAL.ink; ctx.g.fillRect(-10, -10, DW + 20, DH + 20);
  await drawLayers(ctx, p.layers || [], env, data);
  const po = typeof p.post === 'function' ? p.post(env) : p.post;
  if (po) Object.assign(ctx.post, po);
}
