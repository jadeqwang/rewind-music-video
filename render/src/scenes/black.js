// black: absolute black with an optional tiny mono caption (silence, the cut to Q.E.D.).
import { DW, PAL } from '../core.js';
import { setFont, F } from '../type.js';
export function draw(ctx, lt, t, shot) {
  const { g, ty } = ctx, p = shot.params;
  g.fillStyle = '#000'; g.fillRect(0, 0, DW, 1080);
  if (p.caption) { setFont(ty, F.mono(p.size ?? 22), 6); ty.fillStyle = PAL.boneDim; ty.textAlign = 'center'; ty.fillText(p.caption, DW / 2, p.y ?? 548); }
  ctx.post.bloom = 0; ctx.post.grain = 0.02; ctx.post.vignette = 0;
}
