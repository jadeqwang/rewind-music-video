// core.js: math, randomness, timing, palette, paper and the layer compositor.
// Everything is a pure function of song time t. Frames render out of order in parallel workers,
// so nothing may carry state from one frame to the next (caches are fine; results must not depend on them).

const W = 1920, H = 1080, TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => x < a ? a : x > b ? b : x;
const lerp = (a, b, k) => a + (b - a) * k;
const inv = (a, b, x) => (x - a) / (b - a);
const seg = (t, a, b) => clamp((t - a) / (b - a));
const smooth = k => k * k * (3 - 2 * k);
const ease = smooth;
const easeIn = k => k * k * k;
const easeOut = k => 1 - Math.pow(1 - k, 3);
const easeInOut = k => k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
const expoOut = k => k >= 1 ? 1 : 1 - Math.pow(2, -10 * k);
const expoIn = k => k <= 0 ? 0 : Math.pow(2, 10 * k - 10);
const backOut = (k, s = 1.70158) => 1 + (s + 1) * Math.pow(k - 1, 3) + s * Math.pow(k - 1, 2);
const frac = x => x - Math.floor(x);
const mix = (a, b, k) => Array.isArray(a) ? a.map((v, i) => lerp(v, b[i], k)) : lerp(a, b, k);

// keyframes: kf(t, [[t0, v0], [t1, v1], ...], easeFn) — values may be numbers or arrays
function kf(t, keys, fn = ease) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (t <= keys[i][0]) {
      const [a, va] = keys[i - 1], [b, vb] = keys[i];
      return mix(va, vb, fn((t - a) / (b - a)));
    }
  }
  return keys[keys.length - 1][1];
}

// ---------- deterministic randomness ----------
function hash(n) { // int → [0,1)
  n = (n | 0) ^ 0x9e3779b9; n = Math.imul(n ^ (n >>> 16), 0x85ebca6b); n = Math.imul(n ^ (n >>> 13), 0xc2b2ae35); n ^= n >>> 16;
  return (n >>> 0) / 4294967296;
}
const hash2 = (a, b) => hash(Math.imul(a | 0, 0x27d4eb2d) ^ (b | 0) * 0x165667b1);
const hash3 = (a, b, c) => hash(Math.imul(a | 0, 0x27d4eb2d) ^ Math.imul(b | 0, 0x165667b1) ^ Math.imul(c | 0, 0x9e3779b1));
function rng(seed) { // mulberry32
  let s = (seed | 0) ^ 0x6d2b79f5;
  return () => { s = (s + 0x6d2b79f5) | 0; let x = Math.imul(s ^ (s >>> 15), 1 | s); x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x; return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
}
function strSeed(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

// smooth value noise
function vnoise(x, y, seed = 0) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash3(xi, yi, seed), b = hash3(xi + 1, yi, seed), c = hash3(xi, yi + 1, seed), d = hash3(xi + 1, yi + 1, seed);
  return lerp(lerp(a, b, u), lerp(c, d, u), v);
}
function fbm(x, y, seed = 0, oct = 4) {
  let s = 0, a = .5, f = 1, n = 0;
  for (let i = 0; i < oct; i++) { s += a * vnoise(x * f, y * f, seed + i * 17); n += a; a *= .5; f *= 2.03; }
  return s / n;
}
// 1D wobble for slow drifts
const wob = (t, f = 1, ph = 0) => Math.sin(t * f * TAU + ph) * .6 + Math.sin(t * f * 1.73 * TAU + ph * 2.1) * .4;

// ---------- timing (filled from data/timing.json) ----------
const TM = { bpm: 162, beat: 60 / 162, t0: 0, beats: [], words: [], sections: [] };
function beatPos(t) { // continuous beat index using the measured beat list
  const b = TM.beats;
  if (!b.length) return (t - TM.t0) / TM.beat;
  if (t <= b[0]) return (t - b[0]) / TM.beat;
  let lo = 0, hi = b.length - 1;
  if (t >= b[hi]) return hi + (t - b[hi]) / TM.beat;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (b[m] <= t) lo = m; else hi = m; }
  return lo + (t - b[lo]) / (b[lo + 1] - b[lo]);
}
const beatN = t => Math.floor(beatPos(t) + 1e-6);
const beatTime = n => { const b = TM.beats; if (!b.length) return TM.t0 + n * TM.beat; if (n < 0) return b[0] + n * TM.beat; if (n >= b.length) return b[b.length - 1] + (n - b.length + 1) * TM.beat; return b[n]; };
function pulse(t, k = 6, every = 1) { // 1 on each beat (or every Nth), exponential decay
  const bp = beatPos(t) / every; if (bp < 0) return 0;
  return Math.exp(-k * frac(bp) * TM.beat * every);
}
function sincePrevBeat(t) { const n = beatN(t); return t - beatTime(n); }

// ---------- palette (the pencil box) ----------
const P = {
  night: '#0d0c10', snow: '#f3efe6',
  white: '#f4efe6', silver: '#a9b0bd', sky: '#7fb3ff', cobalt: '#3d63dd', ultra: '#26318f',
  gold: '#ffc53d', orange: '#ff7a1a', verm: '#ef3b24', crimson: '#a8122a',
  graphite: '#2b2a2e', lead: '#6e6c72', brown: '#7a4a2a', green: '#3f6f4a', cream: '#fff6dc'
};
function hexRgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function rgbHex(r, g, b) { return '#' + ((1 << 24) | (clamp(Math.round(r), 0, 255) << 16) | (clamp(Math.round(g), 0, 255) << 8) | clamp(Math.round(b), 0, 255)).toString(16).slice(1); }
function mixHex(a, b, k) { const A = hexRgb(a), B = hexRgb(b); return rgbHex(lerp(A[0], B[0], k), lerp(A[1], B[1], k), lerp(A[2], B[2], k)); }
function rgba(h, a) { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; }

// ---------- canvases ----------
function makeCanvas(w = W, h = H) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
const OUT = document.getElementById('out'); OUT.width = W; OUT.height = H;
const G = OUT.getContext('2d');

const LAYERS = [];
function layer(i) { // pooled full-frame layers, cleared on request
  if (!LAYERS[i]) { const c = makeCanvas(); LAYERS[i] = { c, g: c.getContext('2d', { willReadFrequently: false }) }; }
  const L = LAYERS[i]; L.g.setTransform(1, 0, 0, 1, 0, 0); L.g.globalAlpha = 1; L.g.globalCompositeOperation = 'source-over'; L.g.clearRect(0, 0, W, H);
  return L;
}

// ---------- paper ----------
// Tooth: an alpha tile; pencil pigment only sticks to the peaks of the grain.
const TOOTH_N = 512;
const TOOTH_MIN = new URLSearchParams(location.search).has('toothMin') ? +new URLSearchParams(location.search).get('toothMin') : 70;   // alpha in the grain's valleys
let TOOTH = null, TOOTH_FIBER = null;
function buildTooth() {
  const c = makeCanvas(TOOTH_N, TOOTH_N), g = c.getContext('2d'), im = g.createImageData(TOOTH_N, TOOTH_N);
  for (let y = 0; y < TOOTH_N; y++) for (let x = 0; x < TOOTH_N; x++) {
    // periodic grain: mix of fine hash noise and a slightly larger blotch, tiled seamlessly via wrap
    const f = hash2(x, y), m = vnoise(x / 3.1, y / 3.1, 5) * .5 + vnoise((x % TOOTH_N) / 11, (y % TOOTH_N) / 11, 9) * .5;
    let v = .55 * f + .45 * m;
    v = clamp((v - .18) / .6);
    const i = (y * TOOTH_N + x) * 4; im.data[i] = im.data[i + 1] = im.data[i + 2] = 255; im.data[i + 3] = Math.round(lerp(TOOTH_MIN, 255, v));
  }
  g.putImageData(im, 0, 0);
  TOOTH = c;
  // a lighter tooth for printed type: mostly solid, a little grain
  const c2 = makeCanvas(TOOTH_N, TOOTH_N), g2 = c2.getContext('2d'), im2 = g2.createImageData(TOOTH_N, TOOTH_N);
  for (let y = 0; y < TOOTH_N; y++) for (let x = 0; x < TOOTH_N; x++) {
    const v = hash2(x + 7, y + 3) * .6 + vnoise(x / 2.3, y / 2.3, 21) * .4;
    const i = (y * TOOTH_N + x) * 4; im2.data[i] = im2.data[i + 1] = im2.data[i + 2] = 255; im2.data[i + 3] = Math.round(lerp(200, 255, clamp((v - .15) / .5)));
  }
  g2.putImageData(im2, 0, 0);
  TOOTH_LIGHT = c2;
}
let TOOTH_LIGHT = null;
const TOOTH_BOIL = new URLSearchParams(location.search).has('toothBoil');
function toothIn(L, drawIdx, strength = 1) { // make everything on layer L grainy
  const g = L.g, pat = g.createPattern(TOOTH, 'repeat');
  // the paper's tooth does not move between drawings (only the strokes boil), unless ?toothBoil
  const tb = TOOTH_BOIL ? drawIdx : 0, ox = Math.floor(hash(tb * 7 + 1) * TOOTH_N), oy = Math.floor(hash(tb * 7 + 2) * TOOTH_N);
  pat.setTransform(new DOMMatrix([1, 0, 0, 1, ox, oy]));
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalCompositeOperation = 'destination-in'; g.globalAlpha = 1;
  if (strength < 1) { // keep part of the stroke solid: blend the tooth toward opaque
    g.fillStyle = pat; g.globalAlpha = 1; g.fillRect(0, 0, W, H);
  } else { g.fillStyle = pat; g.fillRect(0, 0, W, H); }
  g.restore();
}

const PAPER = {};
function buildPaper(kind) {
  const c = makeCanvas(), g = c.getContext('2d');
  const dark = kind === 'night';
  const base = dark ? [15, 14, 19] : [243, 239, 230];
  const im = g.createImageData(W, H), d = im.data;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4;
    const mott = fbm(x / 260, y / 260, dark ? 3 : 4, 3) - .5;
    const grain = hash2(x, y) - .5;
    const vx = (x - W / 2) / (W / 2), vy = (y - H / 2) / (H / 2);
    const vig = Math.pow(clamp(Math.sqrt(vx * vx * .7 + vy * vy * .9) / 1.25), 2.2);
    const k = dark ? (mott * 7 + grain * 5 - vig * 6) : (mott * 10 + grain * 7 - vig * 22);
    const warm = dark ? [0, 0, 1] : [1, .4, -1.4];
    d[i] = base[0] + k + warm[0] * vig * 4; d[i + 1] = base[1] + k + warm[1] * vig * 4; d[i + 2] = base[2] + k + warm[2] * vig * 4; d[i + 3] = 255;
  }
  g.putImageData(im, 0, 0);
  // fibres
  const r = rng(dark ? 11 : 12);
  g.lineCap = 'round';
  for (let i = 0; i < 2600; i++) {
    const x = r() * W, y = r() * H, a = r() * TAU, l = 6 + r() * 22;
    g.strokeStyle = dark ? `rgba(255,255,255,${.012 + r() * .018})` : `rgba(90,70,40,${.02 + r() * .03})`;
    g.lineWidth = .6 + r() * .6;
    g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a) * l * .5 + (r() - .5) * 4, y + Math.sin(a) * l * .5 + (r() - .5) * 4, x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
  PAPER[kind] = c;
}
function paper(g, kind = 'night', alpha = 1) {
  g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = alpha; g.globalCompositeOperation = 'source-over';
  g.drawImage(PAPER[kind], 0, 0); g.restore();
}

// ---------- drawing clock ----------
// The drawing is redrawn `rate` times per second (8 = threes, 12 = twos, 24 = ones).
function drawClock(t, rate = 12) { const n = Math.floor(t * rate + 1e-6); return { n, tq: n / rate }; }

async function loadJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(url + ' ' + r.status); return r.json(); }
function loadImage(url) { return new Promise((ok, bad) => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => bad(new Error('img ' + url)); im.src = url; }); }
