// pencil.js: the colored-pencil stroke engine.
//
// Pen collects strokes in batches keyed by (pencil, width, alpha) and strokes each batch once.
// analyzePlate() reads a reference frame into fields (tone, color, flow direction, edges);
// hatchField() and contourField() redraw those fields as pencil strokes.
// Nothing here draws the plate itself: only strokes derived from it.

// ---------------------------------------------------------------- Pen
class Pen {
  constructor() { this.b = new Map(); this.n = 0; }
  _batch(col, w, a) {
    const k = col + '|' + (Math.round(w * 4) / 4) + '|' + (Math.round(a * 20) / 20);
    let B = this.b.get(k);
    if (!B) { B = { col, w: Math.round(w * 4) / 4, a: Math.round(a * 20) / 20, p: new Path2D() }; this.b.set(k, B); }
    return B;
  }
  // quadratic stroke
  q(x0, y0, cx, cy, x1, y1, col, w = 1.6, a = .8) {
    const B = this._batch(col, w, a); B.p.moveTo(x0, y0); B.p.quadraticCurveTo(cx, cy, x1, y1); this.n++;
  }
  l(x0, y0, x1, y1, col, w = 1.6, a = .8) { const B = this._batch(col, w, a); B.p.moveTo(x0, y0); B.p.lineTo(x1, y1); this.n++; }
  // polyline with tapered ends (drawn as three widths)
  poly(pts, col, w = 1.8, a = .85, taper = .22) {
    const n = pts.length; if (n < 2) return;
    const cut = Math.max(1, Math.floor(n * taper));
    const draw = (i0, i1, ww) => { if (i1 <= i0) return; const B = this._batch(col, ww, a); B.p.moveTo(pts[i0][0], pts[i0][1]); for (let i = i0 + 1; i <= i1; i++) B.p.lineTo(pts[i][0], pts[i][1]); };
    if (n < 5) { draw(0, n - 1, w * .8); this.n++; return; }
    draw(0, cut, w * .45); draw(cut, n - 1 - cut, w); draw(n - 1 - cut, n - 1, w * .45); this.n++;
  }
  dot(x, y, r, col, a = .9) { const B = this._batch(col, r * 2, a); B.p.moveTo(x, y); B.p.lineTo(x + .01, y); this.n++; }
  flush(g, order) {
    g.save(); g.lineCap = 'round'; g.lineJoin = 'round';
    const bs = [...this.b.values()];
    if (order) bs.sort((A, B) => order(A.col) - order(B.col));
    for (const B of bs) { g.globalAlpha = B.a; g.strokeStyle = P[B.col] || B.col; g.lineWidth = B.w; g.stroke(B.p); }
    g.restore(); this.b.clear(); const n = this.n; this.n = 0; return n;
  }
}
// draw order: dark pencils first, light on top (on black paper light pencils sit over dark ones)
const ORDER_NIGHT = c => ({ ultra: 0, crimson: 1, cobalt: 2, verm: 3, lead: 3, brown: 3, green: 3, silver: 4, sky: 5, orange: 6, gold: 7, cream: 8, white: 9 })[c] ?? 5;
const ORDER_SNOW = c => ({ sky: 0, gold: 1, orange: 2, silver: 2, cobalt: 3, verm: 4, green: 4, brown: 5, lead: 5, ultra: 6, crimson: 6, graphite: 7 })[c] ?? 4;

// ---------------------------------------------------------------- image fields
function blurF(src, w, h, sigma) { // separable gaussian on Float32Array
  if (sigma <= 0) return src.slice();
  const r = Math.max(1, Math.ceil(sigma * 2.5)), k = new Float32Array(2 * r + 1);
  let s = 0; for (let i = -r; i <= r; i++) { k[i + r] = Math.exp(-i * i / (2 * sigma * sigma)); s += k[i + r]; }
  for (let i = 0; i < k.length; i++) k[i] /= s;
  const tmp = new Float32Array(w * h), out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) { const o = y * w; for (let x = 0; x < w; x++) { let a = 0; for (let i = -r; i <= r; i++) { const xx = x + i < 0 ? 0 : x + i >= w ? w - 1 : x + i; a += src[o + xx] * k[i + r]; } tmp[o + x] = a; } }
  for (let y = 0; y < h; y++) { for (let x = 0; x < w; x++) { let a = 0; for (let i = -r; i <= r; i++) { const yy = y + i < 0 ? 0 : y + i >= h ? h - 1 : y + i; a += tmp[yy * w + x] * k[i + r]; } out[y * w + x] = a; } }
  return out;
}

const _anaCanvas = makeCanvas(8, 8), _anaCtx = _anaCanvas.getContext('2d', { willReadFrequently: true });
function analyzePlate(img, aw = 640, ah = 360, opt = {}, src = null) {
  _anaCanvas.width = aw; _anaCanvas.height = ah;
  if (src) _anaCtx.drawImage(img, src[0], src[1], src[2], src[3], 0, 0, aw, ah); else _anaCtx.drawImage(img, 0, 0, aw, ah);
  const d = _anaCtx.getImageData(0, 0, aw, ah).data, N = aw * ah, gain = (opt.gain ?? 1) / 255;
  const R = new Float32Array(N), Gc = new Float32Array(N), B = new Float32Array(N), L = new Float32Array(N);
  for (let i = 0; i < N; i++) { const r = Math.min(1, d[i * 4] * gain), g = Math.min(1, d[i * 4 + 1] * gain), b = Math.min(1, d[i * 4 + 2] * gain); R[i] = r; Gc[i] = g; B[i] = b; L[i] = .2126 * r + .7152 * g + .0722 * b; }
  const L1 = blurF(L, aw, ah, opt.s1 ?? .9);
  const gx = new Float32Array(N), gy = new Float32Array(N), mag = new Float32Array(N);
  for (let y = 1; y < ah - 1; y++) for (let x = 1; x < aw - 1; x++) {
    const i = y * aw + x;
    const a = L1[i - aw - 1], b = L1[i - aw], c = L1[i - aw + 1], e = L1[i - 1], f = L1[i + 1], g = L1[i + aw - 1], h2 = L1[i + aw], k = L1[i + aw + 1];
    const X = (c + 2 * f + k) - (a + 2 * e + g), Y = (g + 2 * h2 + k) - (a + 2 * b + c);
    gx[i] = X; gy[i] = Y; mag[i] = Math.hypot(X, Y);
  }
  // structure tensor → smooth flow (edge tangent) and coherence
  const Jxx = new Float32Array(N), Jxy = new Float32Array(N), Jyy = new Float32Array(N);
  for (let i = 0; i < N; i++) { Jxx[i] = gx[i] * gx[i]; Jxy[i] = gx[i] * gy[i]; Jyy[i] = gy[i] * gy[i]; }
  const sT = opt.sT ?? 3.2;
  const A = blurF(Jxx, aw, ah, sT), Bx = blurF(Jxy, aw, ah, sT), C = blurF(Jyy, aw, ah, sT);
  const ang = new Float32Array(N), coh = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const a = A[i], b = Bx[i], c = C[i];
    const th = .5 * Math.atan2(2 * b, a - c); // gradient direction
    ang[i] = th + Math.PI / 2;                  // tangent: along edges / isophotes
    const tr = a + c, det = Math.sqrt((a - c) * (a - c) + 4 * b * b);
    coh[i] = tr > 1e-6 ? (det / tr) * (det / tr) : 0;
  }
  // non-max suppressed edges on the gradient magnitude
  const edge = new Float32Array(N);
  let mmax = 0; for (let i = 0; i < N; i++) if (mag[i] > mmax) mmax = mag[i];
  for (let y = 2; y < ah - 2; y++) for (let x = 2; x < aw - 2; x++) {
    const i = y * aw + x, m = mag[i]; if (m < mmax * .04) continue;
    const dx = gx[i] / (m + 1e-9), dy = gy[i] / (m + 1e-9);
    const m1 = mag[Math.round(y + dy) * aw + Math.round(x + dx)], m2 = mag[Math.round(y - dy) * aw + Math.round(x - dx)];
    if (m >= m1 && m >= m2) edge[i] = m / mmax;
  }
  // tone (blurred luminance for hatching density), local detail, and a coarse color field
  const T = blurF(L, aw, ah, opt.sTone ?? 1.4);
  const dm = new Float32Array(N); for (let i = 0; i < N; i++) dm[i] = mag[i] / (mmax + 1e-9);
  const detail = blurF(dm, aw, ah, 3);
  let dmax = 1e-6; for (let i = 0; i < N; i++) if (detail[i] > dmax) dmax = detail[i];
  for (let i = 0; i < N; i++) detail[i] = Math.min(1, detail[i] / (dmax * .6));
  const Rb = blurF(R, aw, ah, 1.6), Gb = blurF(Gc, aw, ah, 1.6), Bb = blurF(B, aw, ah, 1.6);
  return { aw, ah, L, T, R: Rb, G: Gb, B: Bb, ang, coh, edge, mag, mmax, detail };
}

// bilinear sample of a field
function samp(F, arr, x, y) {
  const aw = F.aw, ah = F.ah;
  x = x < 0 ? 0 : x > aw - 1.001 ? aw - 1.001 : x; y = y < 0 ? 0 : y > ah - 1.001 ? ah - 1.001 : y;
  const xi = x | 0, yi = y | 0, fx = x - xi, fy = y - yi, i = yi * aw + xi;
  return (arr[i] * (1 - fx) + arr[i + 1] * fx) * (1 - fy) + (arr[i + aw] * (1 - fx) + arr[i + aw + 1] * fx) * fy;
}
function sampAng(F, x, y) { // nearest (angles do not interpolate linearly)
  const xi = clamp(Math.round(x), 0, F.aw - 1), yi = clamp(Math.round(y), 0, F.ah - 1); return F.ang[yi * F.aw + xi];
}

// ---------------------------------------------------------------- color → pencil
function hsv(r, g, b) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let h = 0; if (d > 1e-6) { if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4; h *= 60; if (h < 0) h += 360; }
  return [h, mx > 0 ? d / mx : 0, mx];
}
// Night paper: pick the pencil that re-creates this plate color as light on black.
function pencilNight(r, g, b, t, o = {}, rnd = .5) {
  const [h, s, v] = hsv(r, g, b);
  const warmBoost = o.warm ?? 1;
  if (s * warmBoost < .16 || v < .06) {            // neutral: whites and greys, cool in the shadows
    if (v > .6) return rnd < .12 ? 'silver' : 'white';
    if (v > .36) return rnd < .3 ? 'white' : 'silver';
    return o.coolShadow === false ? 'silver' : (rnd < .5 ? 'cobalt' : 'silver');
  }
  if ((h < 52 || h > 335) && s * warmBoost < .5) { // skin and warm-lit whites: white pencil with warm layers
    const warm = clamp((s * warmBoost - .12) * 2.2);
    if (rnd < warm * .7) return v > .62 ? (h > 28 ? 'gold' : 'orange') : (v > .4 ? 'orange' : 'verm');
    return v > .55 ? 'white' : v > .3 ? 'silver' : 'ultra';
  }
  if (h < 52 || h > 335) {                          // saturated warm light
    if (v > .78 && h > 30 && h < 60) return 'gold';
    if (v > .55 && h > 16) return 'orange';
    if (h > 335 || h < 12) return v > .45 ? 'verm' : 'crimson';
    return v > .4 ? 'orange' : 'verm';
  }
  if (h < 75) return v > .6 ? 'gold' : 'orange';
  if (h < 170) return v > .55 ? 'sky' : 'cobalt';   // greens/cyans read as atmosphere
  if (h < 262) return v > .62 ? 'sky' : v > .3 ? 'cobalt' : 'ultra';
  return v > .5 ? 'sky' : 'ultra';
}
// Snow paper: pencils darken; pick by hue of the dark.
function pencilSnow(r, g, b, t, o = {}, rnd = .5) {
  // White paper: graphite does the drawing; color only where the plate is genuinely colored.
  const [h, s, v] = hsv(r, g, b);
  const sat = s * (o.sat ?? 1);
  if (sat < .3 || v < .12) return v < .3 ? (rnd < .25 ? 'lead' : 'graphite') : (rnd < .3 ? 'graphite' : 'lead');
  if (rnd > clamp((sat - .25) * 2.2)) return v < .4 ? 'graphite' : 'lead';    // even colored areas are mostly graphite
  if (h >= 10 && h < 52) return v < .42 ? 'brown' : (h > 38 && v > .7 ? 'gold' : 'orange');   // skin, warm light: never crimson
  if (h < 10 || h > 335) return v < .35 ? 'crimson' : 'verm';
  if (h < 75) return 'gold';
  if (h < 170) return v < .4 ? 'green' : 'sky';
  if (h < 262) return v < .35 ? 'ultra' : v < .6 ? 'cobalt' : 'sky';
  return 'ultra';
}

// ---------------------------------------------------------------- view mapping
// A view maps plate uv (0..1) to screen: cover-fit, then zoom about (cx, cy) in uv, then rotate and offset.
function makeView(F, v = {}) {
  const zoom = v.zoom ?? 1, cx = v.cx ?? .5, cy = v.cy ?? .5, rot = v.rot ?? 0, ox = v.ox ?? 0, oy = v.oy ?? 0;
  const sx = W * zoom, sy = H * zoom, cs = Math.cos(rot), sn = Math.sin(rot);
  return {
    toScreen(u, vv) { const x = (u - cx) * sx, y = (vv - cy) * sy; return [W / 2 + ox + x * cs - y * sn, H / 2 + oy + x * sn + y * cs]; },
    toPlate(X, Y) { const x = X - W / 2 - ox, y = Y - H / 2 - oy; const xr = x * cs + y * sn, yr = -x * sn + y * cs; return [(xr / sx + cx) * F.aw, (yr / sy + cy) * F.ah]; },
    // canvas transform mapping plate pixels (pw x ph image) onto the screen
    matrix(pw, ph) { const a = sx / pw, d = sy / ph; return [cs * a, sn * a, -sn * d, cs * d, W / 2 + ox + (-cx * sx) * cs - (-cy * sy) * sn, H / 2 + oy + (-cx * sx) * sn + (-cy * sy) * cs]; },
    toUV(X, Y) { const x = X - W / 2 - ox, y = Y - H / 2 - oy; const xr = x * cs + y * sn, yr = -x * sn + y * cs; return [xr / sx + cx, yr / sy + cy]; },
    scale: W * zoom / F.aw, rot
  };
}

// ---------------------------------------------------------------- hatching
// o: { paper, seed, spacing, len:[a,b], w:[a,b], alpha:[a,b], tone:(L)=>0..1, angle (global hatch dir), follow 0..1,
//      cross (tone threshold for a crossing layer), pencil fn, mask(x,y)->0..1 in screen space, region [x0,y0,x1,y1], jit }
function hatchField(pen, F, view, o = {}) {
  const night = (o.paper ?? 'night') === 'night';
  const sp = o.spacing ?? 7, seed = o.seed ?? 1;
  const [l0, l1] = o.len ?? [9, 26], [w0, w1] = o.w ?? (night ? [1.1, 2.1] : [.9, 1.7]), [a0, a1] = o.alpha ?? (night ? [.35, .92] : [.22, .78]);
  const toneFn = o.tone ?? (night ? (L => Math.pow(smooth(clamp((L - (o.black ?? .07)) / ((o.white ?? .8) - (o.black ?? .07)))), o.contrast ?? 1.25))
                                   : (L => Math.pow(smooth(clamp(((o.white ?? .8) - L) / ((o.white ?? .8) - (o.black ?? .12)))), o.contrast ?? 1.55)));
  const gAng = o.angle ?? -0.95, follow = o.follow ?? .75, cross = o.cross ?? .72, gam = o.gamma ?? 1.15;
  const pick = o.pencil ?? (night ? pencilNight : pencilSnow), pOpt = o.pencilOpt ?? {};
  const [rx0, ry0, rx1, ry1] = o.region ?? [0, 0, W, H];
  const mask = o.mask, dens = o.density ?? 1;
  const reveal = o.reveal ?? 1, rKey = o.revealKey;   // draw-on: only strokes whose key < reveal
  let k = 0;
  for (let gy = ry0; gy < ry1; gy += sp) {
    for (let gx = rx0; gx < rx1; gx += sp) {
      k++;
      const hA = hash3(gx | 0, gy | 0, seed), hB = hash3(gx | 0, gy | 0, seed + 1), hC = hash3(gx | 0, gy | 0, seed + 2);
      const X = gx + (hA - .5) * sp * 1.4, Y = gy + (hB - .5) * sp * 1.4;
      if (reveal < 1 && rKey && rKey(X, Y, hash3(gx | 0, gy | 0, 77)) > reveal) continue;
      const [px, py] = view.toPlate(X, Y);
      if (px < 0 || py < 0 || px >= F.aw || py >= F.ah) continue;
      const fw = o.fill ? o.fill.w(X, Y) : 0;
      let t = toneFn(fw > 0 ? lerp(samp(F, F.T, px, py), o.fill.T, fw) : samp(F, F.T, px, py));
      let shadowStroke = false;
      if (night && F.M && o.shadow !== false) {       // the subject's shadow side: sparse cool strokes, never the void
        const m = samp(F, F.M, px, py);
        const sh = (o.shadowTone ?? .2) * clamp((m - .35) / .4);
        if (t < sh) { t = sh; shadowStroke = true; }
      }
      if (mask) t *= mask(X, Y);
      if (t <= .02) continue;
      const pr = Math.pow(t, gam) * dens;
      if (hC > pr) continue;
      let r = samp(F, F.R, px, py), g = samp(F, F.G, px, py), b = samp(F, F.B, px, py);
      if (fw > 0) { r = lerp(r, o.fill.rgb[0], fw); g = lerp(g, o.fill.rgb[1], fw); b = lerp(b, o.fill.rgb[2], fw); }
      const col = shadowStroke ? ((o.shadowCols ?? ['ultra', 'ultra', 'cobalt'])[Math.floor(hash3(gx | 0, gy | 0, seed + 4) * 3)]) : pick(r, g, b, t, pOpt, hash3(gx | 0, gy | 0, seed + 4));
      if (!col) continue;
      const c = samp(F, F.coh, px, py), det = samp(F, F.detail, px, py);
      const fa = sampAng(F, px, py) + view.rot;
      const ang = mixAngle(gAng, fa, clamp(c * 1.6) * follow);
      // long confident strokes across calm areas, short ones where the picture is busy
      const L = lerp(l1, l0, Math.sqrt(det)) * (.65 + .7 * hash3(gx | 0, gy | 0, seed + 3)) * (o.lenMul ?? 1);
      strokeAlong(pen, F, view, X, Y, ang, L, col, lerp(w0, w1, t), lerp(a0, a1, t), follow, seed + k);
      if (t > cross && hash3(gx | 0, gy | 0, seed + 5) < (t - cross) / (1 - cross) * 1.2) {
        const col2 = o.crossPencil ? o.crossPencil(col, t) : col;
        strokeAlong(pen, F, view, X + 1.5, Y - 1.5, ang + (o.crossAngle ?? 1.1), L * .8, col2, lerp(w0, w1, t) * .9, lerp(a0, a1, t) * .85, 0, seed + k + 7);
      }
    }
  }
}
function mixAngle(a, b, k) { // mix two axial angles (period π)
  let d = ((b - a) % Math.PI + Math.PI * 1.5) % Math.PI - Math.PI / 2;
  return a + d * k;
}
function strokeAlong(pen, F, view, X, Y, ang, L, col, w, a, follow, s) {
  const dx = Math.cos(ang), dy = Math.sin(ang);
  const x0 = X - dx * L / 2, y0 = Y - dy * L / 2, x1 = X + dx * L / 2, y1 = Y + dy * L / 2;
  // bend the stroke slightly toward the local flow at its far end, plus a hand-drawn bow
  let cx = X, cy = Y;
  const bow = (hash(s) - .5) * L * .18;
  cx += -dy * bow; cy += dx * bow;
  pen.q(x0, y0, cx, cy, x1, y1, col, w, a);
}

// ---------------------------------------------------------------- contours
// Chain thinned edges into polylines and draw them as confident, slightly doubled pencil lines.
function contourField(pen, F, view, o = {}) {
  const aw = F.aw, ah = F.ah, E = F.edge;
  const hi = o.hi ?? .16, lo = o.lo ?? .07, minLen = o.minLen ?? 7, seed = o.seed ?? 3;
  const used = new Uint8Array(aw * ah);
  const col = o.pencil ?? 'white', w = o.w ?? 1.7, a = o.alpha ?? .85, passes = o.passes ?? 2, jit = (o.jit ?? 1.1) * CJIT;
  const mask = o.mask, colorFn = o.colorFn;
  const nbr = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
  let chains = 0;
  const trace = (x, y, dir) => {
    const pts = [];
    let px = x, py = y, pa = null;
    for (let step = 0; step < 400; step++) {
      let best = -1, bs = 0;
      for (let k = 0; k < 8; k++) {
        const nx = px + nbr[k][0], ny = py + nbr[k][1];
        if (nx < 1 || ny < 1 || nx >= aw - 1 || ny >= ah - 1) continue;
        const j = ny * aw + nx; if (used[j] || E[j] < lo) continue;
        let sc = E[j];
        if (pa !== null) { const da = Math.abs(((Math.atan2(nbr[k][1], nbr[k][0]) - pa + 3 * Math.PI) % TAU) - Math.PI); sc *= da < .9 ? 1.5 : da < 1.7 ? .8 : 0; }
        if (sc > bs) { bs = sc; best = k; }
      }
      if (best < 0) break;
      pa = Math.atan2(nbr[best][1], nbr[best][0]);
      px += nbr[best][0]; py += nbr[best][1]; used[py * aw + px] = 1; pts.push([px, py]);
    }
    return pts;
  };
  const step = o.step ?? 1;
  for (let y = 2; y < ah - 2; y += step) for (let x = 2; x < aw - 2; x += step) {
    const i = y * aw + x; if (used[i] || E[i] < hi) continue;
    used[i] = 1;
    const f = trace(x, y), b = trace(x, y);
    let pts = b.reverse().concat([[x, y]], f);
    if (pts.length < minLen) continue;
    let es = 0; for (const [qx, qy] of pts) es += E[qy * aw + qx]; es /= pts.length;
    if (es < (o.minStrength ?? .1)) continue;
    // smooth the pixel staircase away, then resample by arc length
    for (let it = 0; it < (o.smooth ?? 3); it++) {
      const q = pts.map(p => p.slice());
      for (let k = 1; k < pts.length - 1; k++) { q[k][0] = (pts[k - 1][0] + 2 * pts[k][0] + pts[k + 1][0]) / 4; q[k][1] = (pts[k - 1][1] + 2 * pts[k][1] + pts[k + 1][1]) / 4; }
      pts = q;
    }
    const sp = [], stepA = o.resample ?? 2.2;
    let acc = 0; sp.push(view.toScreen(pts[0][0] / aw, pts[0][1] / ah));
    for (let k = 1; k < pts.length; k++) {
      acc += Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]);
      if (acc >= stepA || k === pts.length - 1) { sp.push(view.toScreen(pts[k][0] / aw, pts[k][1] / ah)); acc = 0; }
    }
    let m = 1; if (mask) { const mid = sp[sp.length >> 1]; m = mask(mid[0], mid[1]); if (m < .05) continue; }
    if (o.reveal !== undefined && o.reveal < 1) {
      const mid = sp[sp.length >> 1], key = o.revealKey ? o.revealKey(mid[0], mid[1], hash(i)) : hash(i);
      if (key > o.reveal) continue;
      // the stroke being drawn right now is only partly there
      const part = clamp((o.reveal - key) / .08);
      if (part < 1) sp.length = Math.max(2, Math.floor(sp.length * part));
    }
    const strength = es;
    let c = col;
    if (colorFn) { const pi = pts[pts.length >> 1]; c = colorFn(F, pi[0], pi[1]) || col; if (!c) continue; }
    else if (o.tint && F.R) { // take the pencil from the plate's color at this edge (rim light, sky light)
      const pi = pts[pts.length >> 1], r = samp(F, F.R, pi[0], pi[1]), g = samp(F, F.G, pi[0], pi[1]), b = samp(F, F.B, pi[0], pi[1]);
      const [h, s, v] = hsv(r, g, b);
      if (s > .32 && v > .45 && (h < 55 || h > 335)) c = h > 30 ? 'gold' : 'orange';
      else if (s > .3 && v > .35 && h > 185 && h < 250) c = 'sky';
    }
    chains++;
    for (let p = 0; p < passes; p++) {
      const s = seed * 131 + chains * 7 + p;
      // overshoot the ends a little and drift each pass
      const ox = (hash(s) - .5) * jit * 2, oy = (hash(s + 1) - .5) * jit * 2;
      const q = sp.map(([X, Y], k) => [X + ox + (hash(s + k * 3) - .5) * jit, Y + oy + (hash(s + k * 3 + 1) - .5) * jit]);
      if (q.length > 3) { // overshoot
        const n = q.length, e0 = q[0], e1 = q[1], z0 = q[n - 1], z1 = q[n - 2], os = .35 + hash(s + 9) * .6;
        q.unshift([e0[0] + (e0[0] - e1[0]) * os * 2, e0[1] + (e0[1] - e1[1]) * os * 2]);
        q.push([z0[0] + (z0[0] - z1[0]) * os * 2, z0[1] + (z0[1] - z1[1]) * os * 2]);
      }
      pen.poly(q, c, w * (p ? .7 : 1) * lerp(.7, 1.25, clamp(strength * 2)), a * (p ? .55 : 1) * m);
    }
  }
  return chains;
}

// ---------------------------------------------------------------- procedural pencil helpers
// Radial rays from a point (sunrise, impacts). energy 0..1
function raysFrom(pen, x, y, o = {}) {
  const n = o.n ?? 420, r0 = o.r0 ?? 20, r1 = o.r1 ?? 900, seed = o.seed ?? 9, cols = o.cols ?? ['gold', 'orange', 'orange', 'verm', 'white'];
  const a0 = o.a0 ?? 0, a1 = o.a1 ?? TAU, w = o.w ?? [1.2, 2.6], alpha = o.alpha ?? [.5, .95], energy = o.energy ?? 1;
  for (let i = 0; i < n; i++) {
    const h1 = hash2(i, seed), h2 = hash2(i, seed + 1), h3 = hash2(i, seed + 2), h4 = hash2(i, seed + 3);
    // o.jseed: the drawing index; the layout (seed) holds still and each drawing only nudges it
    const js = o.jseed, a = a0 + (a1 - a0) * h1 + (js !== undefined ? (hash2(i, js * 7 + 3) - .5) * (o.jit ?? .008) : 0);
    const inner = r0 + (r1 - r0) * Math.pow(h2, 1.8) * .35;
    const len = (r1 - inner) * Math.pow(h3, .7) * energy * (o.lenMul ? o.lenMul(a) : 1) * (js !== undefined ? 1 + (hash2(i, js * 7 + 4) - .5) * (o.ljit ?? .14) : 1);
    if (len < 4) continue;
    const bend = (h4 - .5) * .06;
    const x0 = x + Math.cos(a) * inner, y0 = y + Math.sin(a) * inner, x1 = x + Math.cos(a + bend) * (inner + len), y1 = y + Math.sin(a + bend) * (inner + len);
    const col = cols[Math.floor(hash2(i, seed + 4) * cols.length)];
    pen.q(x0, y0, (x0 + x1) / 2 + Math.cos(a + 1.57) * len * bend, (y0 + y1) / 2 + Math.sin(a + 1.57) * len * bend, x1, y1, col, lerp(w[0], w[1], h2), lerp(alpha[0], alpha[1], 1 - h3));
  }
}
// Flame tongues rising from (x, y): tapered curves that lean together toward the tip; a new seed each drawing = flicker
function flames(pen, x, y, o = {}) {
  const n = o.n ?? 40, s = o.size ?? 160, seed = o.seed ?? 3, cols = o.cols ?? ['gold', 'gold', 'orange', 'orange', 'verm', 'white', 'gold'];
  for (let i = 0; i < n; i++) {
    const h1 = hash2(i, seed), h2 = hash2(i, seed + 1), h3 = hash2(i, seed + 2);
    const bx = x + (h1 - .5) * s * .8, hgt = s * (.3 + .85 * h2) * (1 - Math.abs(h1 - .5) * 1.1), lean = (h3 - .5) * s * .3;
    const pts = [];
    for (let k = 0; k <= 7; k++) {
      const u = k / 7;
      pts.push([bx + (x - bx) * u * .7 + lean * u * u + Math.sin(u * 6 + h3 * 9) * s * .035 * u, y - hgt * u]);
    }
    pen.poly(pts, cols[Math.floor(hash2(i, seed + 3) * cols.length)], 1.3 + 2.4 * (1 - h2), .9, .35);
  }
}
// Scribble: looping stroke over a region (panic, smoke, fire)
function scribble(pen, x, y, rx, ry, o = {}) {
  const n = o.n ?? 60, seed = o.seed ?? 5, col = o.col ?? 'verm', w = o.w ?? 1.6, a = o.alpha ?? .8;
  let px = x, py = y, ang = hash(seed) * TAU;
  const pts = [[px, py]];
  for (let i = 0; i < n; i++) {
    ang += (hash2(i, seed) - .5) * 2.4 + .9;
    const st = (o.step ?? 26) * (.5 + hash2(i, seed + 1));
    px += Math.cos(ang) * st; py += Math.sin(ang) * st;
    // pull back toward the region
    px += (x - px) * .12; py += (y - py) * .12;
    px = clamp(px, x - rx, x + rx); py = clamp(py, y - ry, y + ry);
    pts.push([px, py]);
  }
  pen.poly(pts, col, w, a, .1);
}
// Stars: pencil dots and tiny crosses
function starfield(pen, seed, n, o = {}) {
  const region = o.region ?? [0, 0, W, H], cols = o.cols ?? ['white', 'white', 'silver', 'sky'];
  const tw = o.twinkle ?? 0;
  for (let i = 0; i < n; i++) {
    const x = lerp(region[0], region[2], hash2(i, seed)), y = lerp(region[1], region[3], hash2(i, seed + 1));
    if (o.mask && o.mask(x, y) < .5) continue;
    const s = Math.pow(hash2(i, seed + 2), 6), col = cols[Math.floor(hash2(i, seed + 3) * cols.length)];
    const a = .45 + .5 * hash2(i, seed + 4) - tw * hash2(i, seed + 5);
    if (s > .35) { const r = 3 + s * 7; pen.l(x - r, y, x + r, y, col, 1.2, a); pen.l(x, y - r, x, y + r, col, 1.2, a); }
    else pen.dot(x, y, .8 + s * 2.2, col, a);
  }
}

// A view onto a crop [u0, v0, u1, v1] of the plate, mapped through the parent view.
function cropView(parent, Fc, box) {
  const [u0, v0, u1, v1] = box, du = u1 - u0, dv = v1 - v0;
  return {
    toScreen(u, v) { return parent.toScreen(u0 + u * du, v0 + v * dv); },
    toPlate(X, Y) { const [u, v] = parent.toUV(X, Y); return [(u - u0) / du * Fc.aw, (v - v0) / dv * Fc.ah]; },
    scale: parent.scale, rot: parent.rot
  };
}

// ---------------------------------------------------------------- faces as line work
// fm = plate meta face array (see tools/plate_meta.py): [u0,v0,u1,v1,jaw,eyeLx,eyeLy,eyeRx,eyeRy,mx,my,{lines}]
// Draws eyelids, irises, brows, nose, lips and jaw from the plate's own landmarks, so faces stay readable
// and mouths keep the plate's lip-sync.
function catmull(pts, n = 3) { // smooth a polyline through its points
  if (pts.length < 3) return pts;
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      out.push([.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                .5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)]);
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}
function faceLines(pen, fm, view, o = {}) {
  if (!fm || !fm.face || !fm.face[11]) return;
  const Lf = fm.face[11], night = (o.paper ?? 'night') === 'night', seed = o.seed ?? 1;
  const ink = o.ink ?? (night ? 'white' : 'graphite'), soft = o.soft ?? (night ? 'silver' : 'lead');
  const [a0, , a1] = fm.face, sw = Math.abs(view.toScreen(a1, .5)[0] - view.toScreen(a0, .5)[0]);
  const k = clamp(sw / 420, .35, 2.2) * (o.weight ?? 1);          // line weight scales with face size
  const jit = .6 * k;
  const P2 = key => { const a = Lf[key]; if (!a) return null; const out = []; for (let i = 0; i < a.length; i += 2) out.push(view.toScreen(a[i], a[i + 1])); return out; };
  const line = (key, col, w, al, from = 0, to = 1) => {
    let p = P2(key); if (!p) return;
    const n = p.length, i0 = Math.floor(from * (n - 1)), i1 = Math.ceil(to * (n - 1)); p = p.slice(i0, i1 + 1);
    const s = catmull(p, 4).map(([x, y], i) => [x + (hash3(i, seed, key.length) - .5) * jit, y + (hash3(i, seed + 1, key.length) - .5) * jit]);
    pen.poly(s, col, w * k, al, .18);
  };
  line('eyeR_up', ink, 2.4, .95); line('eyeL_up', ink, 2.4, .95);
  line('eyeR_lo', soft, 1.2, .6, .1, .9); line('eyeL_lo', soft, 1.2, .6, .1, .9);
  for (const key of ['irisR', 'irisL']) {
    const ir = Lf[key]; if (!ir) continue;
    const [cx, cy] = view.toScreen(ir[0], ir[1]), r = Math.abs(view.toScreen(ir[0] + ir[2], ir[1])[0] - cx);
    if (r < 1.5) continue;
    const pts = []; for (let a = 0; a <= TAU + .01; a += .35) pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    pen.poly(pts, night ? 'sky' : 'graphite', 1.4 * k, .85, .02);
    if (night) { pen.dot(cx - r * .35, cy - r * .35, Math.max(1.2, r * .22), 'white', .95); }
    else { for (let i = 0; i < 6; i++) { const a = hash2(i, seed) * TAU; pen.l(cx, cy, cx + Math.cos(a) * r * .6, cy + Math.sin(a) * r * .6, 'graphite', 1.3 * k, .8); } }
  }
  // brows: a few strokes between the lower and upper brow lines
  for (const [lo, up] of [['browR', 'browRu'], ['browL', 'browLu']]) {
    const A = P2(lo), Bq = P2(up); if (!A || !Bq) continue;
    for (let i = 0; i < 9; i++) {
      const u = i / 8, ia = Math.min(A.length - 1, Math.round(u * (A.length - 1))), ib = Math.min(Bq.length - 1, Math.round(u * (Bq.length - 1)));
      const x0 = A[ia][0], y0 = A[ia][1], x1 = Bq[ib][0], y1 = Bq[ib][1];
      const dx = (Bq[Math.min(ib + 1, Bq.length - 1)][0] - Bq[ib][0]) * .6;
      pen.l(lerp(x0, x1, .15), lerp(y0, y1, .15), lerp(x0, x1, .9) + dx, lerp(y0, y1, .9), soft, 1.6 * k, .75);
    }
    line(up, ink, 1.3, .6);
  }
  line('nose', soft, 1.1, .45, .45, 1); line('noseB', ink, 1.8, .85, .15, .85);
  if (o.lips !== false) {
    line('lipO_up', ink, 1.5, .7); line('lipO_lo', soft, 1.4, .6, .15, .85);
    line('lipI_up', ink, 2.2, .95); line('lipI_lo', ink, 1.8, .85);
  }
  if (o.oval !== false) { line('oval', soft, 1.2, .35, .3, .7); }
}

// Silhouette: trace the matte outline as the strongest line of the drawing.
function silhouette(pen, F, view, o = {}) {
  if (!F.M || !F.matteImg) return 0;
  if (!F._matteF) F._matteF = analyzePlate(F.matteImg, F.aw, F.ah, { s1: 1.2, sT: 2, sTone: 1 });
  return contourField(pen, F._matteF, view, { hi: .22, lo: .08, minLen: 14, w: 2.5, alpha: .95, passes: 2, jit: 1.3, smooth: 5, resample: 3, minStrength: .15, ...o });
}
// The matte PNGs are greyscale with no alpha channel; compositing needs the grey level as alpha.
function matteAlpha(im) {
  if (im._alpha) return im._alpha;
  const c = makeCanvas(im.width, im.height), g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(im, 0, 0);
  const d = g.getImageData(0, 0, im.width, im.height), a = d.data;
  for (let i = 0; i < a.length; i += 4) { a[i + 3] = a[i]; a[i] = a[i + 1] = a[i + 2] = 255; }
  g.putImageData(d, 0, 0);
  return (im._alpha = c);
}
// Erase a layer where the subject is (for light that passes behind it)
function behindMatte(L, F, view, strength = 1) {
  if (!F.matteImg) return;
  const g = L.g, m = view.matrix(F.matteImg.width, F.matteImg.height);
  g.save(); g.globalCompositeOperation = 'destination-out'; g.globalAlpha = strength; g.setTransform(m[0], m[1], m[2], m[3], m[4], m[5]);
  g.drawImage(matteAlpha(F.matteImg), 0, 0); g.restore();
}

// ---------------------------------------------------------------- re-mouthing (singer shots)
// The lips are rebuilt from the vocal track, positioned by the plate's own lip landmarks.
function mouthOpen(t) {
  const M = TM.mouth; if (!M) return 0;
  const x = t * M.fps, i = Math.floor(x), f = x - i, a = M.open[clamp(i, 0, M.open.length - 1)], b = M.open[clamp(i + 1, 0, M.open.length - 1)];
  return a + (b - a) * f;
}
// geometry in screen space: corners, centre, angle, width, face height, lip thicknesses, and the synthesized lips for openness k
function mouthGeom(fm, view, k) {
  if (!fm || !fm.face || !fm.face[11]) return null;
  const Lf = fm.face[11], pts = key => { const a = Lf[key]; const o = []; for (let i = 0; i < a.length; i += 2) o.push(view.toScreen(a[i], a[i + 1])); return o; };
  const Iu = pts('lipI_up'), Il = pts('lipI_lo'), Ou = pts('lipO_up'), Ol = pts('lipO_lo');
  const cL = Iu[0], cR = Iu[Iu.length - 1], mx = (cL[0] + cR[0]) / 2, my = (cL[1] + cR[1]) / 2;
  const ang = Math.atan2(cR[1] - cL[1], cR[0] - cL[0]), wid = Math.hypot(cR[0] - cL[0], cR[1] - cL[1]);
  const [, v0, , v1] = fm.face, faceH = Math.abs(view.toScreen(.5, v1)[1] - view.toScreen(.5, v0)[1]);
  const mid = a => a[a.length >> 1];
  const thU = clamp(Math.hypot(mid(Ou)[0] - mid(Iu)[0], mid(Ou)[1] - mid(Iu)[1]), faceH * .02, faceH * .06);
  const thL = clamp(Math.hypot(mid(Ol)[0] - mid(Il)[0], mid(Ol)[1] - mid(Il)[1]), faceH * .025, faceH * .07);
  const gap = k * .13 * faceH, cs = Math.cos(ang), sn = Math.sin(ang);
  const P2 = (x, y) => [mx + x * cs - y * sn, my + x * sn + y * cs];
  const iu = [], il = [], ou = [], ol = [], N = 14;
  for (let j = 0; j <= N; j++) {
    const u = j / N, x = (u - .5) * wid, s = Math.pow(Math.sin(Math.PI * u), .7);
    const round = 1 - .18 * k * s;                        // open vowels pull the corners in a little
    iu.push(P2(x * round, -gap * .36 * s)); il.push(P2(x * round, gap * .64 * s));
    ou.push(P2(x * 1.05, -gap * .36 * s - thU * Math.pow(s, .45))); ol.push(P2(x * 1.02, gap * .64 * s + thL * Math.pow(s, .45)));
  }
  return { mx, my, ang, wid, faceH, gap, iu, il, ou, ol, thU, thL,
    mask: (X, Y) => { const dx = X - mx, dy = Y - my, xr = dx * cs + dy * sn, yr = -dx * sn + dy * cs;
      const rx = wid * .72, ry = Math.max(gap, faceH * .05) * .75 + thL * 1.6; return clamp(1.25 - Math.hypot(xr / rx, (yr - gap * .15) / ry)) ; } };
}
function drawMouth(pen, g, M, o = {}) {
  const night = (o.paper ?? 'night') === 'night', ink = night ? 'white' : 'graphite', soft = night ? 'silver' : 'lead', seed = o.seed ?? 1;
  const k = clamp(M.faceH / 420, .35, 2.2);
  const jit = p => p.map(([x, y], i) => [x + (hash2(i, seed) - .5) * .7 * k, y + (hash2(i, seed + 5) - .5) * .7 * k]);
  // interior: dark when open (hatched graphite on white paper; left as black paper at night, with a tooth line)
  if (M.gap > 2) {
    const poly = M.iu.concat(M.il.slice().reverse());
    if (!night) {
      g.save(); g.beginPath(); poly.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath(); g.clip();
      const p2 = new Pen(), x0 = M.mx - M.wid, x1 = M.mx + M.wid, y0 = M.my - M.gap, y1 = M.my + M.gap * 1.2;
      for (let y = y0; y < y1; y += 2.6) for (let x = x0; x < x1; x += 3) { if (hash3(x | 0, y | 0, seed) < .8) p2.l(x, y, x + 7, y - 5, hash3(x | 0, y | 0, seed + 1) < .3 ? 'crimson' : 'graphite', 1.4, .85); }
      p2.flush(g); g.restore();
    } else {
      const n = M.iu.length; pen.poly(jit(M.iu.slice(2, n - 2).map(([x, y]) => [x, y + M.gap * .12])), 'silver', 1.1 * k, .5, .2);
    }
  }
  pen.poly(jit(M.iu), ink, 2.2 * k, .95, .15); pen.poly(jit(M.il), ink, 1.8 * k, .9, .15);
  pen.poly(jit(M.ou), ink, 1.5 * k, .75, .2); pen.poly(jit(M.ol.slice(2, -2)), soft, 1.4 * k, .6, .2);
}

// ---------------------------------------------------------------- scanline hatching (tonal layers)
// The illustrator's method: long parallel hatch lines, one direction for light tones, cross-hatch for mid,
// a third direction for the darks. Runs break where the tone falls below the layer's threshold.
// o: { paper, seed, layers:[{ang, th, sp, w, a}], step, len:[a,b], tone(L,V)->0..1, pencil, mask, region, jitter }
const _QP = new URLSearchParams(location.search), NL_CONTRAST = _QP.has('nlc') ? +_QP.get('nlc') : 1.7, NL_BLACK = _QP.has('nlb') ? +_QP.get('nlb') : .09, NL_SCALE = _QP.has('nls') ? +_QP.get('nls') : 1.4, BOIL = _QP.has('boil') ? +_QP.get('boil') : .25, CJIT = _QP.has('cjit') ? +_QP.get('cjit') : 1;
function lineHatch(pen, F, view, o = {}) {
  const night = (o.paper ?? 'snow') === 'night';
  const seed = o.seed ?? 1, step = o.step ?? 3.2;
  const spK = (o.spacing ?? 7) / 7, reveal = o.reveal ?? 1, rKey = o.revealKey, ls = o.layoutSeed ?? 11, boil = o.boil ?? BOIL;
  const nb = o.black ?? NL_BLACK, nw = o.white ?? .85, nc = o.contrast ?? NL_CONTRAST;
  const toneFn = o.tone ?? (night ? ((L, V) => Math.pow(smooth(clamp((L - nb) / (nw - nb))), nc))
                                  : ((L, V) => Math.pow(smooth(clamp(((o.white ?? .82) - (.55 * L + .45 * V)) / ((o.white ?? .82) - .1))), o.contrast ?? 1.3)));
  const sc = o.scale ?? (night ? NL_SCALE : 1);   // bolder, sparser strokes survive being watched small
  const layers = o.layers ?? [
    { ang: -0.72, th: .13, sp: 7.5 * sc, w: 1.25 * sc, a: .6 },
    { ang: 0.85, th: .36, sp: 8 * sc, w: 1.2 * sc, a: .6 },
    { ang: -1.35, th: .58, sp: 7 * sc, w: 1.35 * sc, a: .7 },
    { ang: 0.1, th: .78, sp: 5.2 * sc, w: 1.6 * sc, a: .85, dark: true },
  ];
  const pick = o.pencil ?? (night ? pencilNight : pencilSnow);
  const [rx0, ry0, rx1, ry1] = o.region ?? [0, 0, W, H];
  const cxr = (rx0 + rx1) / 2, cyr = (ry0 + ry1) / 2, R = Math.hypot(rx1 - rx0, ry1 - ry0) / 2 + 10;
  const [lenA, lenB] = o.len ?? [18, 46], mask = o.mask, fill = o.fill;
  const V = F.R ? (px, py) => Math.max(samp(F, F.R, px, py), samp(F, F.G, px, py), samp(F, F.B, px, py)) : () => 0;
  let li = 0;
  for (const Ly of layers) {
    li++;
    const ca = Math.cos(Ly.ang), sa = Math.sin(Ly.ang), nx = -sa, ny = ca;   // along (ca, sa); lines offset along the normal
    // the hatch layout is stable from drawing to drawing (ls); each new drawing only nudges it (boil), so the page shimmers instead of strobing
    const lsp = Ly.sp * spK, phase = hash2(ls, li) * lsp + (hash2(seed, li) - .5) * lsp * boil;
    for (let d = -R + phase, k = 0; d < R; d += lsp, k++) {
      const jo = (hash3(k, li, ls) - .5) * lsp * (o.jitter ?? .45) + (hash3(k, li, seed) - .5) * lsp * boil * .5;
      const ox = cxr + nx * (d + jo), oy = cyr + ny * (d + jo);
      let run = null, runLen = 0, target = lenA + (lenB - lenA) * hash3(k, li, ls + 1);
      const flush = () => {
        if (!run || run.n < 2) { run = null; return; }
        const mx = (run.x0 + run.x1) / 2, my = (run.y0 + run.y1) / 2;
        if (reveal < 1 && rKey && rKey(mx, my, hash3(k, li, run.n)) > reveal) { run = null; return; }   // draw-on
        const col = run.col;
        // a slight bow and wobble like a hand-pulled line
        const bow = (hash3(k, run.n, ls + 7) - .5) * 1.6 + (hash3(k, run.n, seed + 7) - .5) * 3.2 * boil;
        pen.q(run.x0, run.y0, mx + nx * bow, my + ny * bow, run.x1, run.y1, col, Ly.w * (run.tw ?? 1), Ly.a * clamp(.55 + run.tmax));
        run = null;
      };
      for (let s = -R; s < R; s += step) {
        const X = ox + ca * s, Y = oy + sa * s;
        if (X < rx0 || Y < ry0 || X >= rx1 || Y >= ry1) { flush(); continue; }
        const [px, py] = view.toPlate(X, Y);
        if (px < 0 || py < 0 || px >= F.aw || py >= F.ah) { flush(); continue; }
        const fw = fill ? fill.w(X, Y) : 0;   // inpainting (e.g. under re-drawn lips): continue the surrounding skin
        let t = fw > 0 ? toneFn(lerp(samp(F, F.T, px, py), fill.T, fw), lerp(V(px, py), fill.V, fw)) : toneFn(samp(F, F.T, px, py), V(px, py));
        if (mask) t *= mask(X, Y);
        // dither the threshold a little so run ends are ragged, like real hatching
        const on = t > Ly.th + (hash3(Math.round(X), Math.round(Y), ls + li) - .5) * .12;
        if (on) {
          if (!run) {
            let r = samp(F, F.R, px, py), g = samp(F, F.G, px, py), b = samp(F, F.B, px, py);
            if (fw > 0) { r = lerp(r, fill.rgb[0], fw); g = lerp(g, fill.rgb[1], fw); b = lerp(b, fill.rgb[2], fw); }
            let col = pick(r, g, b, t, o.pencilOpt || {}, hash3(k, Math.round(s), ls + li * 3));
            if (Ly.dark && !night) col = ({ lead: 'graphite', sky: 'cobalt', orange: 'brown', gold: 'brown', verm: 'crimson' })[col] || col;
            run = { x0: X, y0: Y, x1: X, y1: Y, n: 1, tmax: t, col };
            runLen = 0;
          } else { run.x1 = X; run.y1 = Y; run.n++; run.tmax = Math.max(run.tmax, t); runLen += step; }
          if (runLen >= target) { flush(); target = lenA + (lenB - lenA) * hash3(k, Math.round(s), ls + 2); s += step * (1 + Math.floor(hash3(k, Math.round(s), ls + 3) * 2)); }
          if (!col_ok(run)) flush();
        } else flush();
      }
      flush();
    }
  }
}
function col_ok(run) { return !!run && !!run.col; }
