// shots.js — REWIND full edit (implements docs/SHOTLIST.md EDL v1). Every cut is symbolic: lyric words/lines, events
// (braam/shot/silence/drop), beats, downbeats, kicks and vocal chops from analysis/timing.json — no typed seconds except
// where the EDL itself is a fraction inside a shot.
// Roto refs 'SHOT|fallback|…' resolve to the first assets/roto/<id>/ that exists: the roto agent's per-shot layer, else
// the interim auto-roto of the base clip/set plate (render/tools/make_auto_roto.py → _auto/…), else a stand-in.
// Jade is always her own layer ('J*|ld_jade') so the real roto drops in without touching the edit.
import { DW, DH, PAL, clamp, lerp, smooth, easeOutCubic, easeInOutCubic, hash } from './core.js';

export function buildShots(T) {
  const S = [];
  const add = (id, t0, t1, scene, params = {}, extra = {}) => { if (t1 > t0 + 1e-3) S.push({ id, t0, t1, scene, params, ...extra }); };
  const C = (id, t0, t1, layers, extra = {}, params = {}) => add(id, t0, t1, 'comp', { layers, ...params }, extra);
  const L = i => T.line(i), W = (x, n = 1, o) => T.word(x, n, o);
  const ev = (type, n = 1) => T.event(type, n), sec = n => T.section(n);
  const db = n => T.downbeat(n), bt = n => T.beat(n), BI = t => T.beatIndex(t + 1e-3), DI = t => T.downbeatIndex(t + 1e-3);
  const P = T.period, bar = 4 * P;

  // ---------------- roto refs ----------------
  const R = {
    jade: id => `${id}|ld_jade`,
    suits: id => `${id}|ld_suits`,
    road: '_auto/E2_calm', aerial: '_auto/E1', flood: '_auto/E3_flood', follow: '_auto/E3_follow', room: '_auto/E5', committee: '_auto/S4',
    formation: '_auto/S1', window: '_auto/S2',
    plate: n => `_auto/plate_${n}`,
  };
  // ---------------- common stacks ----------------
  const ink = { type: 'fill', color: PAL.ink };
  const jade = (id, o = {}) => ({ type: 'jade', roto: R.jade(id), ...o });
  const suits = (id, o = {}) => [{ type: 'world', roto: R.suits(id), color: PAL.ink, alpha: 0.5, comp: 'source-over', lights: 0, cam: o.cam, ...(o.world || {}) },
    { type: 'suits', roto: R.suits(id), ...o }];
  const sirenLit = (o = {}) => [{ type: 'sirens', side: 'pair', base: 0.42, peak: 0.5, ...o }, { type: 'headlights', y: 470, r: 1100, amount: 0.32 }];
  const hud = (attempt, ev_, o = {}) => ({ attempt, eval: ev_, tc: true, ...o });

  // =============================== 0 · INTRO 0 – 13.45 (the hook) ===============================
  const v1 = sec('verse1').start, braam0 = ev('braam', 1), shot1 = W('shot').start;
  // H0: the frozen build-1 death tableau (shot B6_tab at its last frame), readable at thumbnail size
  C('H0_tableau', 0, bt(1), [
    { type: 'freezeOf', shot: 'B6_tab', withType: false },
    { type: 'slam', text: 'ATTEMPT 01 ✗', variant: 'center', at: 0, y: 330, maxH: 250, stutter: 0, onType: true, color: PAL.bone },
  ], { hud: { mate: -1, tc: true }, fx: { heart: 0 } }, { post: { bloom: 0.2, ca: 1.5 } });
  // H1: the whole video backwards at ×64 — a trailer in reverse; lands on the dark road
  add('H1_scrub', bt(1), bt(6), 'rewind', { from: sec('end').start - 0.5, to: v1, speeds: [64], segs: [1], hold: 0, echo: 0, badge: 64 }, { fx: { jerks: [bt(1)] } });
  // H2: rain on the windshield; dashboard glow rising; case 1 of ∞
  C('H2_rain', bt(6), braam0, [ink,
    { type: 'world', roto: R.plate('car_interior_1'), alpha: e => 0.3 + 0.3 * e.u, lights: e => 0.3 + 0.5 * e.u, cam: { from: [0.5, 0.5, 1.06], to: [0.5, 0.52, 1.12] } },
    { type: 'rain', n: 220, alpha: 0.35 }, { type: 'rain', n: 60, alpha: 0.6, slow: 0.25 },
    { type: 'dash', amount: e => 0.35 * e.u },
    { type: 'mono', text: 'case 1 of ∞', y: 560, at: 0.6, typed: 14, color: PAL.boneDim },
  ], { fx: { heart: 0.25, soft: 0.6, blinks: [{ t: bt(6) + 1.6, skip: 0.4 }] } });
  // H3: title card on the braam
  C('H3_title', braam0, db(5), [ink,
    { type: 'slam', text: 'REWIND', variant: 'center', y: 640, maxH: 430, stutter: 1 },
    { type: 'cm', text: 'a proof by exhaustion', x: DW / 2, align: 'center', y: 820, size: 76, at: 0.35 },
  ], { fx: { jerks: [braam0], heart: 0.2 } }, { post: { bloom: 0.25, bloomThr: 0.7 } });
  // H4: aerial LSD self-drawing as one pen stroke; THEOREM / PROOF
  C('H4_theorem', db(5), v1, [ink,
    { type: 'world', roto: R.aerial, alpha: 0.18, lights: 0.45, cam: { from: [0.5, 0.5, 1.0], to: [0.48, 0.55, 1.12] } },
    { type: 'pathdraw', progress: e => easeInOutCubic(e.u), width: 5 },
    { type: 'cm', lead: 'Theorem.', text: 'She makes it home.', x: 420, y: 520, size: 112 },
    { type: 'cm', lead: 'Proof.', text: 'By exhaustion.', x: 420, y: 690, size: 112, at: 1.4 },
  ], { fx: { heart: 0.2 } });

  // =============================== 1 · VERSE 1 13.45 – 28.53 (whisper) ===============================
  const pageHdr = { header: 'Chapter 3.  Proof by Exhaustion', folio: '47' };
  C('V1_profile', v1, L(1).start, [ink,
    { type: 'world', roto: R.plate('lake_shore_drive_1'), alpha: 0.16, lights: 0.3, cam: { from: [0.5, 0.55, 1.1], to: [0.5, 0.55, 1.2] }, mirror: { y: 640, alpha: 0.3 } },
    { type: 'sodium', period: 4 * P / 2, amount: 0.34, alpha: 0.08 },
    { type: 'rain', n: 70, alpha: 0.08 },
    jade('J1', { light: 'sodium', late: P }),
    { type: 'page', lines: [0], notes: { defense: '1' }, footnotes: [{ mark: '1', text: 'tomorrow, 9:00 a.m.', word: 'defense' }], size: 140, maxLines: 3, ...pageHdr },
  ], { hud: hud(1, 0.3), fx: { heart: 0.22, soft: 0.35, blinks: [{ t: W('my').start - 0.2, skip: 0.25 }] } });
  C('V2_pov', L(1).start, L(2).start, [ink,
    { type: 'world', roto: R.road, alpha: 0.7, lights: 0.9, speed: 1.4 },
    { type: 'streetlights', vx: 1040, vy: 470, speed: 1.4 },
    { type: 'routemap', progress: e => e.u },
    { type: 'page', lines: [1], size: 104, y: 330, measure: 1150, maxLines: 2 },
  ], { hud: hud(1, 0.2), fx: { heart: 0.2, kick: 0.3 } });
  C('V3_mirror', L(2).start, sec('build1').start, [ink,
    { type: 'world', roto: R.follow, alpha: 0.65, lights: 1 },
    { type: 'ghostcar', x: 1530, y: 300, scale: 0.42, alpha: e => 0.5 + 0.4 * Math.sin(e.t * 9) ** 2 },
    { type: 'page', lines: [2], until: W('couldn\'t', 1, { after: L(2).start }).start, size: 120, y: 790, measure: 1300, maxLines: 1 },
    { type: 'redact', hold: true, parts: ['I', { bar: 9 }], x: 150, y: 950, size: 120 },
  ], { hud: hud(1, 0.1), fx: { heart: 0.25, blinks: [{ t: sec('build1').start - 0.12, skip: 0 }] } });

  // =============================== 2 · BUILD 1 28.53 – 43.42 (the approach) ===============================
  const b1 = sec('build1').start, men = W('men').start, shades = W('shades').start;
  C('B1_flood', b1, L(3).start, [ink,
    { type: 'world', roto: R.flood, alpha: 0.6, lights: 1 },
    { type: 'sirens', side: 'full', amount: 1, peak: 0.45, base: 0.2 },
    { type: 'mono', text: 'SIRENS (SILENT)', y: 980, size: 46, weight: 700, typed: 30 },
  ], { hud: hud(1, 0.0), fx: { heart: 0.3 } });
  C('B2_pullover', L(3).start, T.beatBefore(men), [ink,
    { type: 'world', roto: R.plate('pullover_3'), alpha: 0.8, lights: 1, cam: { from: [0.45, 0.6, 1.0], to: [0.42, 0.66, 1.35], ease: easeOutCubic } },
    { type: 'sirens', side: 'pair', base: 0.15, peak: 0.35 },
    { type: 'annotation', n: 1, move: 'pull over', nag: '?!', x: 150, y: 960, size: 56, at: 0.3 },
    { type: 'tree', seed: 7, depth: 4, x: 1420, y: 340, w: 380, h: 300, progress: e => 0.25 * e.u, leafSize: 30, onType: true, alpha: 0.9 },
  ], { hud: hud(1, [0, -0.4]), fx: { heart: 0.3, blinks: [{ t: L(3).start + 0.9, skip: 0.6 }] } });
  C('B3_formation', T.beatBefore(men), L(4).start, [ink, ...sirenLit(),
    ...suits('B3', { cam: { from: [0.5, 0.48, 1.0], to: [0.5, 0.46, 1.28] }, glint: e => Math.exp(-Math.max(0, e.t - shades) / 0.25) * (e.t >= shades ? 1 : 0) + ((e.b.i % 4 === 1) ? 0.5 * Math.exp(-e.b.phase * 5) : 0) }),
    { type: 'subtitle', lines: [3], from: men, x: 1250 },
  ], { hud: hud(1, [-0.4, -1.2]), fx: { heart: 0.3, kick: 0.2 } });
  const reachE = W('show', 1, { after: L(4).start }).end;
  C('B4_id', L(4).start, T.beatAfter(reachE), [ink,
    { type: 'world', roto: R.plate('car_interior_2'), alpha: 0.35, lights: 0.5, cam: { from: [0.5, 0.5, 1.1], to: [0.52, 0.5, 1.18] } },
    { type: 'sirens', side: 'pair', base: 0.12, peak: 0.25 },
    { type: 'rain', n: 80, alpha: 0.18, slow: 0.15 },
    { type: 'badge', x: e => lerp(1500, 1300, easeOutCubic(e.u)), y: e => lerp(900, 560, easeOutCubic(e.u)), scale: 0.95, rot: -0.08 },
    { type: 'subtitle', lines: [4], until: W('and', 1, { after: L(4).start }).start, x: 620 },
  ], { hud: hud(1, [-1.2, -2.5]), fx: { heart: 0.35, soft: 0.5 } });
  C('B5_and_i_do', T.beatAfter(reachE), L(5).start, [ink,
    { type: 'world', roto: R.window, alpha: 0.55, lights: 0.8 },
    ...sirenLit({ base: 0.3 }),
    { type: 'badge', x: 1180, y: 600, scale: 0.6, rot: 0.04 },
    { type: 'page', lines: [4], from: W('and', 1, { after: L(4).start }).start, size: 150, y: 500, x: 140, measure: 900, maxLines: 1 },
  ], { hud: hud(1, [-2.5, -3.5]), fx: { heart: 0.35 } });
  // B6: "with no warning" — cuts tighten from beats to 8ths to 16ths, alternating close-ups
  const b6a = L(5).start, b6end = shot1;
  {
    const cuts = []; let t = b6a, k = 0;
    while (t < b6end - 0.05) { const span = t < b6a + 2 * P ? P : t < b6end - 2 * P ? P / 2 : P / 4; cuts.push(t); t = T.snap(t + span, T.beats.concat(T.beats.map(b => b + P / 2), T.beats.map(b => b + P / 4), T.beats.map(b => b + 3 * P / 4)).sort((a, b) => a - b)); k++; if (k > 40) break; }
    cuts.push(b6end);
    const kinds = ['suit', 'type', 'jade', 'suit2'];
    for (let i = 0; i < cuts.length - 2; i++) {
      const kd = kinds[i % 4], id = `B6_${i}`;
      if (kd === 'suit' || kd === 'suit2') C(id, cuts[i], cuts[i + 1], [ink, ...sirenLit({ base: 0.5 }), ...suits('B6', { cam: { from: kd === 'suit' ? [0.5, 0.4, 1.7] : [0.62, 0.36, 2.2], to: kd === 'suit' ? [0.5, 0.4, 1.8] : [0.62, 0.36, 2.3] } })], { hud: hud(1, -4) });
      else if (kd === 'type') C(id, cuts[i], cuts[i + 1], [{ type: 'fill', color: PAL.red }, { type: 'slam', text: 'WITH NO WARNING', at: 0, y: 700, maxH: 330, color: PAL.ink, plates: [PAL.ink, PAL.ink] }], { hud: hud(1, -5, { ink: true }) }, { post: { bloom: 0 } });
      else C(id, cuts[i], cuts[i + 1], [ink, { type: 'sirens', side: 'pair', base: 0.35 }, jade('J3', { light: 'siren', cam: { from: [0.73, 0.38, 2.0], to: [0.73, 0.38, 2.1] }, mouth: true })], { hud: hud(1, -5) });
    }
    // the last cut before the shot: the tableau (suit's arm, the window, Jade's white figure, the light)
    C('B6_tab', cuts[cuts.length - 2], b6end, [ink, ...sirenLit({ base: 0.3, peak: 0.45 }),
      ...suits('B6', { cam: { from: [0.5, 0.42, 1.3], to: [0.5, 0.42, 1.31], dx: 420 } }),
      { type: 'world', roto: R.plate('car_interior_2'), alpha: 0.5, color: PAL.bone, lights: 0.3, cam: { from: [0.3, 0.5, 1.0], to: [0.3, 0.5, 1.0], dx: -300 } },
      jade('J3', { cam: { from: [0.76, 0.42, 0.95], to: [0.76, 0.42, 0.95], dx: -620, dy: 60 }, mouth: false }),
    ], { hud: hud(1, null, { mate: -1 }) });
  }
  // SHOT: freeze. muzzle star, bullet line, "SHOT"
  const sfx1 = ev('shot_sfx', 1), sil1 = ev('silence', 1), drop1 = ev('drop', 1);
  C('B7_shot', shot1, sfx1, [
    { type: 'freezeOf', shot: 'B6_tab', withType: false },
    { type: 'star', x: 1180, y: 430, r: 150 }, { type: 'bullet', x: 780, y: 470, len: 1200, angle: 0.02 },
    { type: 'slam', text: 'SHOT', at: 0, y: 1010, maxH: 260, onType: true, stutter: 0.5 },
  ], { hud: { attempt: 1, failed: true, mate: -1, tc: true } }, { post: { ca: 3, bloom: 0.4 } });
  add('B8_case01', sfx1, T.beatBefore(W('stops').start - 0.3), 'freeze', { source: 'B6_tab', case: 1, move: { n: 1, move: 'pull over', nag: '??' }, loc: 'LAKE SHORE DR', file: 'FILE 65-HQ-' },
    { fx: { heart: 0, jerks: [] }, post: {} });
  C('B9_silence', T.beatBefore(W('stops').start - 0.3), drop1, [{ type: 'fill', color: '#000' },
    { type: 'bullet', x: 1100, y: 540, len: 1400, angle: 0, color: PAL.bone },
    { type: 'mono', text: 'time stops', y: 700, typed: 12, at: W('stops').start - T.beatBefore(W('stops').start - 0.3) - 0.35 },
  ], { fx: { heart: 0 } }, { post: { bloom: 0.5, grain: 0.02, vignette: 0 } });

  // =============================== 3 · DROP 1 45.20 – 71.23 (REWIND) ===============================
  const r1end = T.snap(drop1 + 3.5 * P);
  add('R1_shatter', drop1, r1end, 'rewind', { from: shot1 - 0.02, to: b6a, kickStep: true, speeds: [2], segs: [1], hold: 0.06, echo: 2,
    layers: [{ type: 'slam', hits: T.kicksIn(drop1 + 0.2, r1end).slice(0, 3).map(k => ({ t: k, text: 'STOP', variant: 'center' })), y: 1000, maxH: 230, onType: true, color: PAL.cyan, stutter: 1, plates: false }] },
    { fx: { jerks: [drop1], kick: 1 } });
  const R2a = r1end, R2b = L(6).start;
  add('R2_backward', R2a, R2b, 'rewind', { from: b6a, to: L(3).start, speeds: [2, 4, 8], segs: [0.3, 0.33, 0.37], hold: 0, lines: [] }, { fx: { kick: 0.8 } });
  for (const d of T.downbeatsIn(R2a + 0.1, R2b - 0.3)) C(`R2_j${DI(d)}`, d, Math.min(R2b, d + 2 * P), [ink, { type: 'sirens', side: 'pair', base: 0.5 },
    jade('J5', { light: 'siren', late: P / 2, lateColor: PAL.cyan, cam: { from: [0.76, 0.42, 1.0], to: [0.76, 0.42, 1.08] } }), { type: 'circle', x: 960, y: 420, r: 320 }], { fx: { kick: 1, strobe: 0.6 } });
  const R3b = T.downbeatsIn(L(6).start + P, L(7).start)[0] ?? L(6).start + bar;
  C('R3_slam', L(6).start, R3b, [ink, { type: 'sirens', side: 'pair', base: 0.2, peak: 0.4 }, { type: 'slam', text: 'REWIND', variant: 'mirror', at: 0, y: 700 }], { fx: { kick: 1, jerks: [L(6).start] } });
  add('R3b_rewind', R3b, L(7).start, 'rewind', { from: L(3).start, to: L(0).start, speeds: [4, 8], segs: [0.5, 0.5], hold: 0, echo: 2, layers: [{ type: 'slam', text: 'REWIND', variant: 'stack', at: 0, onType: true, color: PAL.cyan }] }, { fx: { kick: 1 } });
  C('R4_slam', L(7).start, T.chopsIn(L(7).start, L(7).start + 3)[0] ?? L(7).end, [{ type: 'fill', color: PAL.bone }, { type: 'slam', text: 'REWIND', variant: 'mirror', at: 0, y: 700, color: PAL.ink }], { fx: { kick: 1, jerks: [L(7).start] } }, { post: { bloom: 0 } });
  const r5a = T.chopsIn(L(7).start, L(7).start + 3)[0] ?? L(7).end, r6a = T.downbeatsIn(r5a + 2, r5a + 6)[0];
  C('R5_hoots', r5a, r6a, [ink, { type: 'sirens', side: 'pair', base: 0.3 }, { type: 'ghosts', roto: R.jade('J5'), n: e => [2, 4, 8, 8][Math.min(3, Math.floor(e.lt / P / 1.5))] }], { fx: { kick: 1, strobe: 0.5 } });
  const r7a = T.downbeatsIn(r6a + 8.5, sec('verse3').start)[0] ?? sec('verse3').start - bar;
  C('R6_tree', r6a, r7a, [ink,
    { type: 'tree', seed: 7, depth: 4, progress: e => smooth(0, 0.5, e.u) * 0.55 + 0.45 * smooth(0.4, 1, e.u), dead: 1, deadU: e => smooth(0.15, 0.3, e.u), lit: 0.2,
      labels: [{ node: 1, text: '  pull over??', color: PAL.red }, { node: 2, text: 'bolt?' }, { node: 3, text: 'keep driving!!', color: PAL.cyan }] },
  ], { hud: { attempt: 1, failed: true, tc: true, eval: -9 }, fx: { kick: 0.6 } });
  for (const d of T.downbeatsIn(r6a + 1, r7a - 1).filter((_, i) => i % 2 === 0)) C(`R6_j${DI(d)}`, d, d + P * 2, [ink, { type: 'sirens', side: 'pair', base: 0.45 }, jade('J5', { light: 'siren', late: P, cam: { from: [0.76, 0.42, 1.1], to: [0.76, 0.42, 1.0] } }), { type: 'circle', x: 960, y: 420, r: 320, color: PAL.bone }], { fx: { kick: 1, strobe: 0.4 } });
  C('R7_attempt02', r7a, sec('verse3').start, [ink, { type: 'slam', text: 'ATTEMPT 02', variant: 'stack', at: 0 }], { fx: { kick: 1 } });

  // =============================== 4 · VERSE 3 71.23 – 89.77 (attempt 02) ===============================
  const v3 = sec('verse3').start;
  C('V4_armed', v3, L(8).start, [ink, { type: 'world', roto: R.road, alpha: 0.75, lights: 1, speed: 1.6 }, { type: 'streetlights', speed: 1.8 }, { type: 'speedlines', amount: 0.25, vy: 470 },
    { type: 'mono', text: 'LAP 2', x: DW - 72, y: 170, align: 'right', size: 46, weight: 700 }],
    { hud: hud(2, 0.3), fx: { kick: 0.5, heart: 0.25 } });
  C('V5_back', L(8).start, L(9).start, [ink,
    { type: 'world', roto: R.plate('car_interior_1'), alpha: 0.25, lights: 0.6, cam: { from: [0.5, 0.5, 1.1], to: [0.5, 0.5, 1.2] }, mirror: { y: 700, alpha: 0.25 } },
    { type: 'sodium', period: P * 2, amount: 0.34, kick: 0.5 },
    jade('J6', { light: 'sodium', late: P }),
    { type: 'page', lines: [8], size: 140, maxLines: 2, y: 470, folio: '61', header: 'Chapter 3.  Proof by Exhaustion' },
  ], { hud: hud(2, 0.3), fx: { heart: 0.25, kick: 0.25, blinks: [{ t: W('back').start - 0.15, skip: 0.3 }] } });
  C('V6_mirror', L(9).start, W('reload').start, [ink, { type: 'world', roto: R.flood, alpha: 0.6, lights: 1 }, { type: 'sirens', side: 'full', base: 0.25, peak: 0.5 },
    { type: 'mirror', rect: [1080, 120, 720, 230], timeOffset: -0.5, zoom: 1.6, focus: [0.5, 0.45], layers: [{ type: 'fill', color: PAL.ink }, ...sirenLit({ base: 0.6 }), ...suits('B3')] },
    { type: 'subtitle', lines: [9], x: 700 }], { hud: hud(2, 0.1), fx: { kick: 0.6, heart: 0.3 } });
  C('V7_reload', W('reload').start, L(10).start, [ink, { type: 'reload', dur: 0.5 }], { hud: hud(2, 0.3), fx: { jerks: [W('reload').start], kick: 0.5 } });
  C('V8_shadow', L(10).start, sec('build2').start, [ink, { type: 'world', roto: R.follow, alpha: 0.6, lights: 1 },
    { type: 'ghostcar', x: 1530, y: 300, scale: 0.42, alpha: 0.85, color: PAL.cyan },
    { type: 'mirror', rect: [150, 120, 620, 200], timeOffset: 0, zoom: 1.3, layers: [{ type: 'freezeOf', time: shot1 - 0.03, withType: false }] },
    { type: 'page', lines: [10], size: 120, y: 700, measure: 1500, maxLines: 2 }], { hud: hud(2, 0.0), fx: { heart: 0.3, kick: 0.3 } });

  // =============================== 5 · BUILD 2 88.92 – 102.84 (the field) ===============================
  const b2 = sec('build2').start, shot2 = W('shot', 2).start;
  const fieldGrass = (o = {}) => [ink, { type: 'world', roto: R.plate('grass_field_1'), alpha: 0.35, lights: 0.8, cam: o.cam }, { type: 'grass', n: 1200, y: 560, alpha: 0.55, scroll: o.scroll ?? 0.3 },
    { type: 'beams', n: o.beams ?? 2, amount: o.beamAmt ?? 0.25 }, { type: 'runner', x: o.x ?? 1300, y: 840, scale: o.scale ?? 0.9, dir: -1 }];
  {
    const ds = [L(11).start, ...T.downbeatsIn(L(11).start + 1, L(12).start), L(12).start];
    for (let i = 0; i < ds.length - 1; i++) {
      if (i % 2 === 0) C(`F1_grass${i}`, ds[i], ds[i + 1], [...fieldGrass({ cam: { from: [0.5, 0.55, 1.1], to: [0.45, 0.55, 1.25] } }), { type: 'page', lines: [11], size: 120, y: 300, measure: 1100, maxLines: 2 }], { hud: hud(2, [-0.5, -1.5]), fx: { kick: 0.5 } });
      else C(`F1_map${i}`, ds[i], ds[i + 1], [ink, { type: 'map', progress: e => clamp((e.t - L(11).start) / (L(12).start - L(11).start)) }, { type: 'subtitle', lines: [11] }], { hud: hud(2, [-1.5, -2.5]), fx: { kick: 0.6 } });
    }
  }
  C('F2_toofast', L(12).start, L(13).start, [ink, ...sirenLit({ base: 0.35 }), { type: 'speedlines', amount: 0.55, vy: 440, n: 120 },
    ...suits('F2', { cam: { from: [0.5, 0.45, 0.9], to: [0.5, 0.42, 1.6] }, world: { double: true } }),
    { type: 'slam', hits: [{ t: W('fast', 1, { after: L(12).start }).start, text: 'TOO FAST', variant: 'behind' }], y: 560 },
    { type: 'subtitle', lines: [12], until: W('fast', 1, { after: L(12).start }).start }], { hud: hud(2, [-2.5, -7]), fx: { kick: 0.8, strobe: 0.3 } });
  {
    const cuts = [L(13).start]; let t = L(13).start; while (t < shot2 - P / 2) { t = T.snap(t + P / 2, T.beats.concat(T.beats.map(b => b + P / 2)).sort((a, b) => a - b)); cuts.push(Math.min(t, shot2)); }
    if (cuts[cuts.length - 1] < shot2) cuts.push(shot2);
    for (let i = 0; i < cuts.length - 1; i++) {
      if (i === cuts.length - 2) C('F3_tab', cuts[i], cuts[i + 1], [...fieldGrass({ beams: 4, beamAmt: 0.45, x: 1000, scale: 1.2 }), { type: 'sirens', side: 'pair', base: 0.3 }, ...suits('F3', { cam: { from: [0.3, 0.45, 1.0], to: [0.3, 0.45, 1.0] }, world: { alpha: 0 } })], { hud: hud(2, null, { mate: -1 }) });
      else if (i % 2) C(`F3_${i}`, cuts[i], cuts[i + 1], [...fieldGrass({ beams: 4, beamAmt: 0.45, x: 1100 - i * 30, scale: 1.1 }), { type: 'subtitle', lines: [13] }], { hud: hud(2, -8) });
      else C(`F3_${i}`, cuts[i], cuts[i + 1], [ink, ...sirenLit({ base: 0.5 }), ...suits('F3', { cam: { from: [0.5, 0.4, 1.9 + i * 0.05], to: [0.5, 0.4, 2.0 + i * 0.05] } })], { hud: hud(2, -9) });
    }
  }
  const sfx2 = ev('shot_sfx', 2), drop2 = ev('drop', 2), stops2 = W('stops', 2).start;
  C('F4_shot', shot2, sfx2, [{ type: 'freezeOf', shot: 'F3_tab', withType: false }, { type: 'star', x: 520, y: 420, r: 140 }, { type: 'bullet', x: 900, y: 600, len: 900, angle: 0.4 },
    { type: 'slam', text: 'SHOT', at: 0, y: 1010, maxH: 260, onType: true, stutter: 0.5 }], { hud: { attempt: 2, failed: true, mate: -1, tc: true } });
  add('F5_case02', sfx2, T.beatBefore(stops2 - 0.3), 'freeze', { source: 'F3_tab', case: 2, move: { n: 1, move: 'bolt', nag: '?' }, loc: 'FIELD, MONTROSE', file: 'FILE 65-HQ-', bullet: { x: 900, y: 600, len: 900, angle: 0.4 } });
  C('F6_silence', T.beatBefore(stops2 - 0.3), drop2, [{ type: 'fill', color: '#000' }, { type: 'bullet', x: 1100, y: 540, len: 1400, angle: 0 },
    { type: 'mono', text: 'time stops', y: 700, typed: 12, at: stops2 - T.beatBefore(stops2 - 0.3) - 0.35 }], { fx: { heart: 0 } }, { post: { bloom: 0.5, vignette: 0 } });

  // =============================== 6 · DROP 2 104.56 – 134.09 (darker) ===============================
  const r9 = L(14).start, r10 = L(15).start, bd = sec('breakdown').start;
  add('R8_both', drop2, r9, 'rewind', { from: shot2 - 0.02, to: b2, speeds: [2, 4, 8], segs: [0.3, 0.3, 0.4], hold: 0.06, echo: 2,
    overlay: { from: shot1 - 0.02, to: L(3).start, color: PAL.red, alpha: 0.75 },
    layers: [{ type: 'sweepbars', progress: e => (e.lt % (2 * P)) / (2 * P), n: 5, onType: true }] }, { fx: { jerks: [drop2], kick: 1 } });
  for (const d of T.downbeatsIn(drop2 + 1, r9 - 1).filter((_, i) => i % 2 === 1)) C(`R8_j${DI(d)}`, d, d + 2 * P, [ink, { type: 'sirens', side: 'pair', base: 0.5, peak: 0.6 }, jade('J5b', { light: 'siren', late: P / 2, lateColor: PAL.red, cam: { from: [0.76, 0.42, 1.0], to: [0.76, 0.42, 1.1] } }), { type: 'circle', x: 960, y: 420, r: 320, color: PAL.red }], { fx: { kick: 1, strobe: 0.6 } });
  C('R9_bars', r9, r10, [{ type: 'fill', color: PAL.bone }, { type: 'slam', hits: [{ t: r9, text: 'REWIND', variant: 'bars', code: '(b)(7)(C)' }, { t: T.downbeatsIn(r9 + 0.5, r10)[0] ?? r9 + bar, text: 'RE—WIND', variant: 'bars', code: '(b)(6)' }] }],
    { fx: { kick: 1, jerks: [r9] } }, { post: { bloom: 0, vignette: 0.1 } });
  const r11 = T.downbeatsIn(r10 + 0.3, r10 + 3)[0] ?? r10 + bar / 2;
  C('R10_bars', r10, r11, [{ type: 'fill', color: PAL.red }, { type: 'slam', text: 'REWIND', variant: 'bars', at: 0, code: '(b)(7)(E)' }], { fx: { kick: 1, jerks: [r10] } }, { post: { bloom: 0 } });
  const r12 = T.downbeatsIn(bd - 2.5 * bar, bd)[0] ?? bd - 2 * bar;
  {
    const ks = [r11, ...T.kicksIn(r11 + 0.2, r12).filter((_, i) => i % 2 === 1)]; ks.push(r12);
    const kinds = ['wall', 'foia', 'jade', 'counter', 'tree', 'case'];
    for (let i = 0; i < ks.length - 1; i++) {
      const kd = kinds[i % kinds.length], id = `R11_${i}`;
      const lay = kd === 'wall' ? [ink, { type: 'wall', progress: 1 }]
        : kd === 'foia' ? [ink, { type: 'foia', n: 6 }]
        : kd === 'jade' ? [ink, { type: 'sirens', side: 'pair', base: 0.5 }, jade('J5b', { light: 'siren', late: P / 2, cam: { from: [0.76, 0.4, 1.3], to: [0.76, 0.4, 1.2] } }), { type: 'circle', x: 960, y: 420, r: 320 }]
        : kd === 'counter' ? [ink, { type: 'counter', value: e => (e.lt % 0.2 < 0.1 ? '02' : '03'), x: DW / 2, y: 720, size: 520, align: 'center', color: e => (e.lt % 0.2 < 0.1 ? PAL.bone : PAL.red) }]
        : kd === 'tree' ? [ink, { type: 'tree', seed: 7, depth: 4, progress: 1, dead: [1, 2], lit: 0.3, labels: [{ node: 1, text: '  pull over??', color: PAL.red }, { node: 2, text: '  bolt?', color: PAL.red }, { node: 3, text: 'keep driving!!', color: PAL.cyan }] },
          { type: 'freezeOf', shot: 'B6_tab', rect: [1450, 120, 360, 203], rot: 0.05, slot: 1, withType: false }, { type: 'freezeOf', shot: 'F3_tab', rect: [1450, 380, 360, 203], rot: -0.04, slot: 2, withType: false }]
        : [{ type: 'fill', color: PAL.bone }, { type: 'freezeOf', shot: 'B8_case01', time: sil1 - 0.05, withType: true }];
      C(id, ks[i], ks[i + 1], lay, { hud: { attempt: e => (hash(Math.floor(e * 15)) < 0.5 ? 2 : 3), tc: true, eval: -9 }, fx: { kick: 1, strobe: 0.4 } }, { post: { bloom: 0.15 } });
    }
  }
  C('R12_drain', r12, bd, [ink, { type: 'tree', seed: 7, depth: 4, progress: 1, dead: [1, 2], lit: 0.3, alpha: e => 1 - e.u }, { type: 'drain', amount: e => easeInOutCubic(e.u) }, { type: 'dot', r: 6, x: 960, y: 540 }],
    { fx: { kick: 0.5 } });

  // =============================== 7 · BREAKDOWN 134.09 – 164.10 (the defense room) ===============================
  const brm = [ev('braam', 4), ev('braam', 5), ev('braam', 6)], dSil = ev('silence', 3);
  // D1: the room, re-angled on each braam (projector flicker; one more redacted committee member each time; too many chairs)
  const roomCut = [bd, ...brm, L(16).start];
  const roomViews = [R.room, R.plate('defense_room_2'), R.plate('defense_room_3'), R.room];
  for (let i = 0; i < 4; i++) {
    const isE5 = roomViews[i] === R.room;
    C(`D1_room${i}`, roomCut[i], roomCut[i + 1], [ink,
      { type: 'world', roto: roomViews[i], alpha: 0.85, lights: 1, speed: 0.6, loop: 'pingpong', cam: { from: [0.5, 0.5, 1.0 + i * 0.08], to: [0.5, 0.5, 1.12 + i * 0.08] } },
      ...(isE5 ? [{ type: 'committee', n: i + (i ? 1 : 0), scale: 0.9, seats: [[700, 560], [860, 560], [1020, 560], [1180, 560], [1340, 560]] }] : []),
      { type: 'flash', amount: e => (i && e.lt < 0.25 ? 0.4 * (1 - e.lt / 0.25) : 0) },
      { type: 'mono', text: 'DEFENSE · 09:00', y: 1000, size: 46, weight: 700, at: i ? 0 : 0.8, typed: i ? 0 : 16 },
    ], { hud: hud(3, 0.0), fx: { heart: 0.3, soft: 0.25, blinks: i === 1 ? [{ t: roomCut[2] - 0.7, skip: 0.5 }] : [] } });
  }
  C('D2_chair', L(16).start, dSil.t ?? dSil, [ink, { type: 'world', roto: R.room, alpha: 0.3, lights: 0.5, speed: 0.4 },
    jade('J8', { cam: { from: [0.62, 0.45, 0.8], to: [0.62, 0.45, 0.82] } }),
    { type: 'revisions', lines: [16], size: 110, y: 380, measure: 1000 }], { hud: hud(3, 0.0), fx: { heart: 0.3 } });
  const dsil = T.opt(T => T.event('silence', 3), 149.12), dsilEnd = T.downbeatsIn(dsil + 1, dsil + 3)[0] ?? dsil + 2;
  C('D3_dropout', dsil, dsilEnd, [ink, { type: 'mono', text: '∴', y: 640, size: 380, weight: 700 }], { fx: { heart: 0.1 } });
  C('D4_wall', dsilEnd, L(18).start, [ink, { type: 'wall', progress: e => e.u }, { type: 'routemap', x: 1440, y: 680, progress: e => e.u },
    { type: 'revisions', lines: [17], size: 100, y: 820, measure: 1300 }], { hud: hud(3, 0.0), fx: { heart: 0.3, kick: 0.2 } });
  C('D5_reveal', L(18).start, sec('build3').start, [ink, { type: 'world', roto: R.room, alpha: 0.25, lights: 0.4, speed: 0.4 },
    { type: 'ghosts', roto: R.jade('J8b'), n: 3 },
    { type: 'page', lines: [18], until: W('couldn\'t', 2).start, size: 120, y: 760, measure: 1400, maxLines: 1 },
    { type: 'redact', text: 'it was me.', x: 150, y: 920, size: 120, at: W('place', 2).end - L(18).start + 0.2, dur: 0.7, color: PAL.cyan, barColor: PAL.bone },
  ], { hud: hud(3, 0.0), fx: { heart: 0.35 } });

  // =============================== 8 · BUILD 3 164.10 – 171.50 (brute force) ===============================
  const b3 = sec('build3').start, never = W('never').start, stop3 = W('stop', 1, { after: never }).start, fd = ev('drop', 3);
  C('X1_search', b3, never, [ink, { type: 'explode', n: e => 20 + 1600 * e.u * e.u, seed: 11 },
    { type: 'counter', value: e => (e.u < 0.92 ? Math.floor(3 + Math.pow(e.u / 0.92, 3) * 996) : '∞'), x: DW - 80, y: 250, size: 150 }],
    { hud: { attempt: 3, tc: true, eval: e => Math.sin(e * 17) * 9 }, fx: { heart: 0.5, kick: 0.6 } });
  for (const d of T.downbeatsIn(b3 + 0.5, never - 0.5)) C(`X1_eyes${DI(d)}`, d, d + P, [ink, { type: 'glasses' }], { fx: { heart: 0.5 } });
  C('X2_never', never, stop3, [ink, { type: 'explode', n: 1600, seed: 11, kill: e => e.u, lit: e => e.u }, { type: 'slam', text: 'NEVER', at: 0, y: 1000, maxH: 300, onType: true }],
    { hud: { attempt: 3, tc: true, eval: 0 }, fx: { kick: 1 } });
  C('X3_stop', stop3, T.opt(T => T.section('silence3').end, stop3 + 0.66) - 0.22, [ink, { type: 'explode', n: 0, lit: 1 }, { type: 'slam', text: 'STOP', at: 0, y: 1000, maxH: 300, onType: true }], { fx: { kick: 1 } });
  C('X4_black', T.opt(T => T.section('silence3').end, stop3 + 0.66) - 0.22, fd, [{ type: 'fill', color: '#000' }, { type: 'annotation', n: 1, move: 'keep driving', nag: '!!', x: 620, y: 560, size: 64 }], { fx: { heart: 0 } });

  // =============================== 9 · FINAL DROP 171.54 – 215.86 (never stop) ===============================
  const n2 = T.downbeatsIn(fd + 0.5, fd + 4)[0] ?? fd + bar, n3 = T.downbeatsIn(fd + 17, fd + 20)[0], n4 = T.downbeatsIn(n3 + 14, n3 + 16.5)[0] ?? n3 + 15, n5 = sec('instrumental').start, end = sec('end').start;
  C('N1_found', fd, n2, [ink, { type: 'mono', text: 'ATTEMPT 03 — LINE FOUND', y: 300, size: 64, weight: 700, color: PAL.cyan },
    { type: 'slam', hits: [{ t: fd + P, text: 'NEVER STOP', variant: 'center' }], y: 860, maxH: 420 }], { fx: { kick: 1, jerks: [fd] } });
  {
    const ds = [n2, ...T.downbeatsIn(n2 + 0.5, n3), n3];
    const kinds = ['jade', 'pov', 'mirror', 'roadside'];
    for (let i = 0; i < ds.length - 1; i++) {
      const kd = kinds[i % 4], id = `N2_${i}`;
      const lay = kd === 'jade' ? [ink, { type: 'world', roto: R.plate('car_interior_1'), alpha: 0.25, lights: 0.6, cam: { from: [0.5, 0.5, 1.1], to: [0.5, 0.5, 1.15] } }, { type: 'sodium', period: P, amount: 0.4, kick: 1 }, jade('J9', { light: 'sodium', late: P / 2 })]
        : kd === 'pov' ? [ink, { type: 'world', roto: R.road, alpha: 0.8, lights: 1, speed: 2 }, { type: 'streetlights', speed: 2.6 }, { type: 'speedlines', amount: 0.5, vy: 470 }, { type: 'kickflash', color: PAL.sodium, amount: 0.25 }]
        : kd === 'mirror' ? [ink, { type: 'world', roto: R.road, alpha: 0.5, lights: 0.8, speed: 2 }, { type: 'mirror', rect: [560, 70, 800, 240], zoom: 1.2, layers: [{ type: 'world', roto: R.flood, alpha: 0.6, lights: e => 1 - e.u * 0.7 }, { type: 'sirens', side: 'full', amount: e => 1 - e.u, base: 0.3 }] }]
        : [ink, ...sirenLit({ base: 0.3 }), ...suits('S5', { cam: { from: [0.1, 0.45, 0.7], to: [1.3, 0.45, 0.45], ease: x => x } }), { type: 'speedlines', amount: 0.6, vx: 1400, vy: 500 }];
      C(id, ds[i], ds[i + 1], [...lay, { type: 'slam', hits: T.chopsIn(ds[i], ds[i + 1]).map(c => ({ t: c, text: 'I DREAMT', variant: 'stack' })), onType: true, color: PAL.bone, cx: kd === 'jade' ? 560 : DW / 2 }],
        { hud: hud(3, 2.5), fx: { kick: 1, strobe: 0.5 } });
    }
  }
  {
    const ds = [n3, ...T.downbeatsIn(n3 + 0.5, n4).filter((_, i) => i % 2 === 1), n4];
    for (let i = 0; i < ds.length - 1; i++) {
      const plate = i % 3 === 1 ? R.plate('lake_shore_drive_2') : i % 3 === 2 ? R.plate('lake_shore_drive_4') : R.aerial;
      C(`N3_aerial${i}`, ds[i], ds[i + 1], [ink, { type: 'world', roto: plate, alpha: 0.7, lights: 1, cam: { from: [0.5, 0.5, 1.0 + 0.04 * i], to: [0.5, 0.5, 1.1 + 0.04 * i] }, mirror: plate === R.aerial ? null : { y: 560, alpha: 0.3 } },
        { type: 'tree', seed: 7, depth: 4, progress: 1, lit: 1, alpha: 0.3, x: 200, y: 560, w: 1500, h: 900, litColor: PAL.cyan },
        { type: 'pathdraw', progress: e => clamp((e.t - n3) / (n4 - n3)), width: 7 },
        { type: 'ghostcar', x: e => lerp(700, 300, e.u), y: e => lerp(500, 900, e.u), scale: 0.3, alpha: e => 0.8 * (1 - e.u), color: PAL.red },
        { type: 'ghostcar', x: e => lerp(800, 1300, e.u), y: e => lerp(500, 950, e.u), scale: 0.3, alpha: e => 0.8 * (1 - e.u), color: PAL.cyan }],
        { hud: hud(3, 4), fx: { kick: 0.8 } });
    }
  }
  {
    const ds = [n4, ...T.downbeatsIn(n4 + 0.5, n5), n5];
    for (let i = 0; i < ds.length - 1; i++) {
      const hudA = clamp(1 - (ds[i] - n4) / (n5 - n4) * 1.3);
      C(`N4_shed${i}`, ds[i], ds[i + 1], [ink, { type: 'world', roto: R.road, alpha: 0.85, lights: 1, speed: 2.4, offset: i * 0.7 }, { type: 'streetlights', speed: 3 }, { type: 'speedlines', amount: 0.7, vy: 470, n: 140 }, { type: 'kickflash', color: PAL.sodium, amount: 0.3 }],
        { hud: { attempt: hudA > 0.66 ? 3 : null, tc: hudA > 0.33, eval: hudA > 0 ? 6 : null, alpha: hudA }, fx: { kick: 1, strobe: 0.7 } });
    }
  }
  const qed = ev('braam', 9);
  C('N5_lake', n5, end, [ink, { type: 'world', roto: R.aerial, alpha: 0.6, lights: 1, cam: { from: [0.45, 0.6, 1.5], to: [0.5, 0.5, 0.82] } },
    { type: 'tree', seed: 7, depth: 4, progress: 1, lit: 1, alpha: 0.3, x: 180, y: 560, w: 1560, h: 980, litColor: PAL.cyan },
    { type: 'pathdraw', progress: 1, width: 7, head: false },
    { type: 'cm', text: 'Q.E.D.', x: DW / 2, align: 'center', y: 620, size: 240, at: qed - n5 }], { fx: { kick: 0.4, heart: 0.2 } });
  C('END_black', end, end + 0.9, [{ type: 'fill', color: '#000' }, { type: 'mono', text: '∎', y: 580, size: 120, weight: 700 }], { fx: { heart: 0 } }, { post: { bloom: 0, vignette: 0, grain: 0.02 } });
  C('END_credits', end + 0.9, T.duration + 0.5, [{ type: 'fill', color: '#000' }, { type: 'mono', text: 'REWIND — Jade Wang', y: 520, size: 44, color: PAL.boneDim },
    { type: 'mono', text: 'every frame drawn in code', y: 600, size: 42, color: PAL.boneDim, at: 0.5 }], { fx: { heart: 0 } }, { post: { bloom: 0, vignette: 0 } });
  return S;
}
