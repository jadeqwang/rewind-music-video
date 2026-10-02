// timing.js: the TimeMap over analysis/timing.json (+ envelopes). Shots reference times symbolically through it.
// timing.json: {duration, bpm, beats[], downbeats[], sections[{name,start,end}], words[{w,start,end,line_idx}],
//               lines[{text,start,end}], events[{type,t}]}
// envelopes:   {fps:30, rms[], low[], mid[], high[], vocal[], onset[]} (0..1)
import { clamp, fin } from './core.js';

const norm = s => String(s).toLowerCase().replace(/[^a-z0-9']/g, '');

async function getJSON(urls) {
  for (const u of urls) {
    try { const r = await fetch(u, { cache: 'no-store' }); if (r.ok) return { url: u, json: await r.json() }; } catch (e) { /* next */ }
  }
  return null;
}

export class TimeMap {
  static async load(base = '..') {
    const tm = await getJSON([`${base}/analysis/timing.json`, `data/timing.stub.json`]);
    const env = await getJSON([`${base}/analysis/envelopes.json`, `${base}/analysis/envelopes30.json`, `data/envelopes.stub.json`]);
    if (!tm) throw new Error('no timing.json (analysis/timing.json or render/data/timing.stub.json)');
    const m = new TimeMap(tm.json, env ? env.json : null);
    m.sources = { timing: tm.url, envelopes: env && env.url };
    return m;
  }

  constructor(d, env) {
    this.d = d;
    this.duration = fin(d.duration, 232.44);
    this.bpm = fin(d.bpm, 124);
    this.period = 60 / this.bpm;
    const bt = x => (typeof x === 'number' ? x : x.t ?? x.time);
    this.beats = (d.beats || []).map(bt).filter(Number.isFinite);
    this.downbeats = (d.downbeats || []).map(bt).filter(Number.isFinite);
    if (!this.downbeats.length) this.downbeats = this.beats.filter((_, i) => i % 4 === 0);
    this.sections = d.sections || [];
    this.words = (d.words || []).map((w, i) => ({ ...w, i, key: norm(w.w) }));
    this.lines = d.lines || [];
    this.events = d.events || [];
    this.env = env || {};
    this.envFps = fin(this.env.fps, 30);
    this.kicks = (d.kicks || []).map(bt).filter(Number.isFinite);
  }
  // try a symbolic reference, fall back when the timing data doesn't have it (e.g. the stub has no events)
  opt(fn, dflt) { try { const v = fn(this); return Number.isFinite(v) ? v : dflt; } catch (e) { return dflt; } }
  downbeatIndex(t) { return TimeMap._last(this.downbeats, t); }
  // kick envelope (falls back to the beat pulse when no kick list exists)
  kick(t, decay = 0.1) { if (!this.kicks.length) return this.pulse(t, decay); const k = TimeMap._last(this.kicks, t); return k < 0 ? 0 : Math.exp(-(t - this.kicks[k]) / decay); }

  // ---- symbolic lookups (throw loudly when a reference doesn't resolve: a silent 0 would put a cut in the wrong place) ----
  // word("defense") → first occurrence; word("rewind", 2) → second; word("stop", 1, {after: 43}) → first after 43 s
  word(text, n = 1, opt = {}) {
    const k = norm(text), after = opt.after ?? -1e9, before = opt.before ?? 1e9;
    let c = 0;
    for (const w of this.words) if (w.key === k && w.start >= after && w.start < before && ++c === n) return w;
    throw new Error(`word("${text}", ${n}) not found`);
  }
  wordAt(t) { let r = null; for (const w of this.words) { if (w.start <= t) r = w; else break; } return r; }
  wordsIn(a, b) { return this.words.filter(w => w.start >= a - 1e-6 && w.start < b); }
  line(i) { return this.lines[i]; }
  lineWords(i) { return this.words.filter(w => w.line_idx === i); }
  section(name, n = 1) { let c = 0; for (const s of this.sections) if (s.name === name && ++c === n) return s; throw new Error(`section ${name} not found`); }
  event(type, n = 1) { let c = 0; for (const e of this.events) if (e.type === type && ++c === n) return e.t; throw new Error(`event ${type} not found`); }

  // beat(n) / downbeat(n): time of the n-th (0-based) beat; extrapolated on the tempo grid outside the list
  beat(n) { return TimeMap._grid(this.beats, n, this.period); }
  downbeat(n) { return TimeMap._grid(this.downbeats, n, this.period * 4); }
  static _grid(a, n, p) { if (!a.length) return n * p; if (n < 0) return a[0] + n * p; if (n >= a.length) return a[a.length - 1] + (n - a.length + 1) * p; return a[n]; }
  beatIndex(t) { return TimeMap._last(this.beats, t); }
  // snap to the nearest beat (or downbeat) time
  snap(t, list = this.beats) { const k = TimeMap._last(list, t); const a = list[Math.max(0, k)], b = list[Math.min(list.length - 1, k + 1)]; return Math.abs(t - a) <= Math.abs(b - t) ? a : b; }
  beatBefore(t) { const k = TimeMap._last(this.beats, t); return k < 0 ? this.beats[0] : this.beats[k]; }
  beatAfter(t) { const k = TimeMap._last(this.beats, t); return this.beats[Math.min(this.beats.length - 1, k + 1)]; }
  // phase within the current beat: {i, t0, phase 0..1, period}
  beatPhase(t, list = this.beats, p = this.period) {
    const k = TimeMap._last(list, t);
    if (k < 0) { const t1 = list[0] ?? 0; const t0 = t1 - p; return { i: -1, t0, phase: clamp((t - t0) / p), period: p }; }
    const t0 = list[k], t1 = k + 1 < list.length ? list[k + 1] : t0 + p;
    return { i: k, t0, phase: clamp((t - t0) / (t1 - t0)), period: t1 - t0 };
  }
  barPhase(t) { return this.beatPhase(t, this.downbeats, this.period * 4); }
  // exponential pulse since the last beat
  pulse(t, decay = 0.12) { const b = this.beatPhase(t); return Math.exp(-(t - b.t0) / decay); }

  // ---- envelopes (linear interpolation; 0 when missing) ----
  e(key, t) {
    const a = this.env[key]; if (!a || !a.length) return 0;
    const x = t * this.envFps, i = Math.floor(x);
    if (i <= 0) return fin(a[0]); if (i >= a.length - 1) return fin(a[a.length - 1]);
    return fin(a[i] + (a[i + 1] - a[i]) * (x - i));
  }

  static _last(arr, t) { let lo = 0, hi = arr.length - 1, ans = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m] <= t + 1e-9) { ans = m; lo = m + 1; } else hi = m - 1; } return ans; }
}
