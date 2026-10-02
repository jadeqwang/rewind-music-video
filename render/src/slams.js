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

// (b) mirror: the whole word on the left of a vertical axis and its exact horizontal reflection on the right
//     (REWIND | ᗡNIWƎЯ) — time reflected, legible on the left, reversed on the right (cyan = reversed time)
export function mirror(g, o) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase();
  g.save(); g.textBaseline = 'alphabetic';
  const gap = 34, cx = DW / 2;
  const { px, w } = fit(g, text, F.slam, 600, (o.maxW ?? DW - 140) / 2 - gap, o.maxH ?? 520);
  const by = o.y ?? 700, open = easeOutCubic(clamp(dt / 0.22));
  g.fillStyle = o.color || PAL.bone; g.fillText(text, cx - gap - w, by);
  g.save(); g.translate(cx, 0); g.scale(-open, 1); g.translate(-cx, 0);
  g.fillStyle = o.mirrorColor || PAL.cyan; g.fillText(text, cx - gap - w, by); g.restore();
  g.fillStyle = o.mirrorColor || PAL.cyan; g.fillRect(cx - 3, by - px * 0.9, 6, px * 1.05);   // the axis
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

// (d) stutter-stack: rows of the word, each landing on the next 16th note (settled by the end of the beat); the newest
//     row is solid, older rows are outlines — a motion echo stepped in musical time
export function stack(g, o) {
  const dt = Math.max(0, o.t - o.t0), text = o.text.toUpperCase(), n = o.rows ?? 4, six = (o.beat ?? 60 / 130) / 4;
  g.save(); g.textBaseline = 'alphabetic';
  const { px, w } = fit(g, text, F.slam, 300, 1600, o.rowH ?? 210);
  const rowH = px * 0.8, top = (DH - rowH * 1.04 * n) / 2 + px * 0.74;
  const landed = Math.min(n, Math.floor(dt / six + 1e-6) + 1);
  for (let i = 0; i < landed; i++) {
    const tin = dt - i * six, slide = (1 - easeOutExpo(clamp(tin / 0.07))) * (i % 2 ? -1 : 1) * 700;
    const y = top + i * rowH * 1.04, x = DW / 2 - w / 2 + slide + (i - (n - 1) / 2) * 40;
    if (i === landed - 1) { g.fillStyle = o.color || PAL.bone; g.fillText(text, x, y); }
    else { g.strokeStyle = rgba(i === landed - 2 ? PAL.red : PAL.bone, 0.45 + 0.5 * (i / n)); g.lineWidth = 3; g.strokeText(text, x, y); }
  }
  g.restore();
}
