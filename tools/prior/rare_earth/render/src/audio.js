// Timing + audio-feature lookups. Everything the renderer does is a pure function of song time t.
import { clamp } from './util.js';

export class AudioMap {
  constructor(data) {
    this.d = data;
    this.duration = data.duration;
    this.fps = data.fps;
    this.beats = data.beats.map((b) => b.t);
    this.beatIdx = data.beats.map((b) => b.i);
    this.bars = data.bars;
    this.kicks = data.kicks;       // [t, strength]
    this.snares = data.snares;
    this.lines = data.lines;       // [{i, sec, t, end, text, words:[{w,t,end}]}]
    this.sections = data.sections;
    this.f = data.features;        // per frame at fps
  }

  // index of last element <= t in a sorted array (or -1)
  static last(arr, t, key = (x) => x) {
    let lo = 0, hi = arr.length - 1, ans = -1;
    while (lo <= hi) {
      const m = (lo + hi) >> 1;
      if (key(arr[m]) <= t) { ans = m; lo = m + 1; } else hi = m - 1;
    }
    return ans;
  }

  beat(t) {
    const k = AudioMap.last(this.beats, t);
    if (k < 0) { const p = this.beats[1] - this.beats[0]; return { k: -1, i: this.beatIdx[0] - 1, t0: this.beats[0] - p, t1: this.beats[0], phase: clamp((t - (this.beats[0] - p)) / p), period: p }; }
    const t0 = this.beats[k];
    const t1 = k + 1 < this.beats.length ? this.beats[k + 1] : t0 + (t0 - this.beats[k - 1]);
    return { k, i: this.beatIdx[k], t0, t1, phase: clamp((t - t0) / (t1 - t0)), period: t1 - t0 };
  }

  bar(t) {
    const k = AudioMap.last(this.bars, t);
    if (k < 0) { const p = this.bars[1] - this.bars[0]; return { k: -1, t0: this.bars[0] - p, t1: this.bars[0], phase: clamp((t - this.bars[0] + p) / p), period: p }; }
    const t0 = this.bars[k];
    const t1 = k + 1 < this.bars.length ? this.bars[k + 1] : t0 + (t0 - this.bars[k - 1]);
    return { k, t0, t1, phase: clamp((t - t0) / (t1 - t0)), period: t1 - t0 };
  }

  // exponential envelope since the most recent onset in list (0..strength)
  env(list, t, decay = 0.12, minStrength = 0) {
    const k = AudioMap.last(list, t, (x) => x[0]);
    if (k < 0) return 0;
    for (let j = k; j >= Math.max(0, k - 3); j--) {
      const [ot, s] = list[j];
      if (s >= minStrength) { const dt = t - ot; return s * Math.exp(-dt / decay); }
    }
    return 0;
  }
  kick(t, decay = 0.12) { return this.env(this.kicks, t, decay, 0.35); }
  snare(t, decay = 0.08) { return this.env(this.snares, t, decay, 0.6); }
  lastKickTime(t) { const k = AudioMap.last(this.kicks, t, (x) => x[0]); return k < 0 ? -99 : this.kicks[k][0]; }

  feat(name, t) {
    const a = this.f[name];
    const x = t * this.fps;
    const i = Math.floor(x);
    if (i < 0) return a[0];
    if (i >= a.length - 1) return a[a.length - 1];
    const u = x - i;
    return a[i] * (1 - u) + a[i + 1] * u;
  }

  line(i) { return this.lines[i]; }
  word(i, j) { return this.lines[i].words[j]; }
  W(i, j) { return this.lines[i].words[j].t; }   // word start time
  L(i) { return this.lines[i].t; }               // line start time
  Le(i) { return this.lines[i].end; }            // line end time

  // nearest beat time to t (for snapping cuts)
  snap(t) {
    const k = AudioMap.last(this.beats, t);
    const a = this.beats[Math.max(0, k)], b = this.beats[Math.min(this.beats.length - 1, k + 1)];
    return Math.abs(t - a) < Math.abs(b - t) ? a : b;
  }
  // beat time by its musical index (drop-1 downbeat is index 0)
  B(i) {
    const k = this.beatIdx.indexOf(i);
    if (k >= 0) return this.beats[k];
    // extrapolate
    const p = this.beats[1] - this.beats[0];
    return this.beats[0] + (i - this.beatIdx[0]) * p;
  }
}
