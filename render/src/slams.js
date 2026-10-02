// slams.js: designed drop-typography variants (the restrained centred slam() in type.js is kept for the biggest moment).
//   behind  — depth sandwich: the word sits BEHIND the subject; the roto matte occludes it (editorial / K-pop cover)
//   mirror  — palindromic REWIND: the right half is the horizontally flipped left half (time reading back), cyan
//   bars    — the word printed ON redaction bars: black bars on bone paper with the letters knocked out
//   stack   — stutter-stack: the word repeated in rows, each row a frame-step further back in time (motion echo)
import { DW, DH, PAL, clamp, lerp, inv, smooth, easeOutExpo, easeOutCubic, hash, hsig, rgba } from './core.js';
import { F, setFont } from './type.js';

function fit(g, text, fam, px, maxW, maxH, track = 0) {
  setFont(g, fam(px), track); let w = g.measureText(text).width;
  if (w > maxW) { px *= maxW / w; setFont(g, fam(px), track); w = g.measureText(text).width; }
  if (maxH && px * 0.74 > maxH) { px = maxH / 0.74; setFont(g, fam(px), track); w = g.measureText(text).width; }
  return { px, w };
}
const hitScale = dt => (dt < 0.15 ? lerp(1.14, 1, easeOutExpo(dt / 0.15)) : 1);

// (a) depth sandwich. drawSubject(g) paints the occluder (e.g. roto.suits) after the word.
export function behind(g, o, drawSubject) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase();
  g.save(); g.textBaseline = 'alphabetic';
  const { px, w } = fit(g, text, F.slam, 900, o.maxW ?? 1840, o.maxH ?? 640);
  const s = hitScale(dt), cx = DW / 2, by = o.y ?? 640;
  g.translate(cx, by); g.scale(s, s); g.translate(-cx, -by);
  g.fillStyle = o.color || PAL.bone; g.fillText(text, cx - w / 2, by);
  g.restore();
  drawSubject && drawSubject(g);
}

// (b) palindromic mirror: left half as set, right half = the left half flipped about the centre axis
export function mirror(g, o) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase();
  g.save(); g.textBaseline = 'alphabetic';
  const { px, w } = fit(g, text, F.slam, 800, (o.maxW ?? 1780), o.maxH ?? 560);
  const cx = DW / 2, by = o.y ?? 760, x0 = cx - w / 2;
  const open = easeOutCubic(clamp(dt / 0.25));            // the mirrored half unfolds from the axis
  g.save(); g.beginPath(); g.rect(0, 0, cx, DH); g.clip(); g.fillStyle = o.color || PAL.bone; g.fillText(text, x0, by); g.restore();
  g.save(); g.translate(cx, 0); g.scale(-open, 1); g.translate(-cx, 0);
  g.beginPath(); g.rect(0, 0, cx, DH); g.clip(); g.fillStyle = o.mirrorColor || PAL.cyan; g.fillText(text, x0, by); g.restore();
  g.fillStyle = o.mirrorColor || PAL.cyan; g.fillRect(cx - 2, by - px * 0.95, 4, px * 1.1);   // the axis
  setFont(g, F.mono(44, 700), 6); g.textAlign = 'center';
  g.fillStyle = rgba(PAL.bone, 0.9); g.fillText(text, cx / 2, by + 120);
  g.fillStyle = rgba(o.mirrorColor || PAL.cyan, 0.9); g.fillText(text.split('').reverse().join(''), cx * 1.5, by + 120);
  g.restore();
}

// (c) redaction bars carrying the word: stepped printer-head reveal, the letters knocked out of the bar
export function bars(g, o) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase();
  g.save(); g.textBaseline = 'alphabetic';
  const paper = o.paper || PAL.bone, ink = '#000000';
  const { px, w } = fit(g, text, F.slam, 640, 1500, 460);
  const cx = DW / 2, by = o.y ?? 690, barH = px * 0.86, barY = by - px * 0.78, padX = 60;
  // document rows: thin bars of varying length above and below (a redacted page), revealed in steps
  const rows = [[150, 0.62], [235, 0.81], [890, 0.74], [975, 0.43]];
  for (let i = 0; i < rows.length; i++) {
    const [y, len] = rows[i], u = Math.floor(clamp((dt - i * 0.03) / 0.12) * 6) / 6;
    g.fillStyle = ink; g.fillRect(150, y, (DW - 300) * len * u, 52);
  }
  // the carrying bar
  const u = Math.floor(clamp(dt / 0.1) * 5) / 5, bw = (w + padX * 2) * u;
  g.fillStyle = ink; g.fillRect(cx - w / 2 - padX, barY, bw, barH);
  g.save(); g.beginPath(); g.rect(cx - w / 2 - padX, barY, bw, barH); g.clip();
  g.fillStyle = paper; g.fillText(text, cx - w / 2, by); g.restore();
  // exemption code, like the margin of a released file
  setFont(g, F.mono(44, 700), 2); g.fillStyle = PAL.red; g.textAlign = 'right';
  if (dt > 0.12) g.fillText(o.code ?? '(b)(7)(C)', DW - 150, barY - 24);
  g.restore();
}

// (d) stutter-stack: rows of the word; row k shows where the word was k·step seconds ago as it slides into place
export function stack(g, o) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase(), n = o.rows ?? 5, step = o.step ?? 2 / 30;
  g.save(); g.textBaseline = 'alphabetic';
  const { px, w } = fit(g, text, F.slam, 300, 1500, o.rowH ?? 196);
  const rowH = px * 0.8, top = (DH - rowH * n) / 2 + px * 0.74;
  const pos = tt => lerp(DW * 0.62, 0, easeOutExpo(clamp(tt / 0.2)));   // slide-in offset over time
  for (let k = n - 1; k >= 0; k--) {
    const tk = dt - k * step; if (tk < 0) continue;
    const y = top + (n - 1 - k) * rowH * 1.04, x = DW / 2 - w / 2 + pos(tk);
    if (k === 0) { g.fillStyle = o.color || PAL.bone; g.fillText(text, x, y); }
    else { g.strokeStyle = rgba(k === 1 ? PAL.red : PAL.bone, 1 - k / n); g.lineWidth = 3; g.strokeText(text, x, y); }
  }
  g.restore();
}
