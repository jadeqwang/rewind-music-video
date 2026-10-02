// shots.js — the main edit (PLACEHOLDER pass). Every cut is symbolic: lyric words/lines, events, beats and sections
// from the TimeMap (analysis/timing.json), never typed seconds. It renders the whole song with the look-dev scenes and
// look-dev roto so the pipeline can be exercised end to end; the director's edit replaces it shot by shot.
// Shot: {id, t0, t1, scene, params}. Scenes: page, suits, freeze, rewind, slam, tree, black, road (see scenes/).
export function buildShots(T) {
  const S = [];
  const add = (id, t0, t1, scene, params = {}) => { if (t1 > t0 + 1e-3) S.push({ id, t0, t1, scene, params }); };
  const L = i => T.line(i);
  const W = (x, n = 1, o) => T.word(x, n, o).start;
  const ev = (type, n, d) => T.opt(T => T.event(type, n), d);
  const sec = (name, d) => T.opt(T => T.section(name).start, d);
  const page = { roto: ['ld_jade', 'ld_road'], jade: 'ld_jade', world: 'ld_road', header: 'Chapter 3.  Proof by Exhaustion' };

  // loop 1 ---------------------------------------------------------------------------------------------------
  const shot1 = W('shot'), and1 = W('and', 1, { after: shot1 }), drop1 = ev('drop', 1, sec('drop1'));
  add('intro', 0, L(0).start, 'road', { roto: 'ld_road' });
  add('v1_page', L(0).start, L(3).start, 'page', { ...page, lines: [0, 1, 2], size: 78, y: 360, folio: '47', notes: { defense: '1' },
    footnotes: [{ mark: '1', text: 'tomorrow, 9:00 a.m.', word: 'defense' }], eval: [0.3, 0.1], attempt: 1 });
  add('b1_page', L(3).start, L(5).start, 'page', { ...page, lines: [3, 4], size: 84, y: 380, folio: '48', notes: { id: '2' },
    footnotes: [{ mark: '2', text: 'NASA badge. Valid through tomorrow, 9:00 a.m.', word: 'id' }], eval: [0.1, -0.9], attempt: 1 });
  add('b1_suits', L(5).start, shot1, 'suits', { roto: 'ld_suits', lines: [5], eval: [-0.9, -6], mate: -1, attempt: 1, move: { n: 1, move: 'pull over', nag: '?!', at: 0.4 }, banner: 'UNCLASSIFIED//FOR OFFICIAL USE ONLY' });
  add('b1_freeze', shot1, and1, 'freeze', { source: 'b1_suits', attempt: 1 });
  add('b1_rewind', and1, drop1, 'rewind', { from: shot1, to: L(3).start, lines: [5] });
  add('d1_stops', drop1, L(6).start, 'slam', { hits: [{ t: drop1, text: 'STOPS' }, { t: T.beat(T.beatIndex(drop1 + .01) + 2), text: 'STOPS', style: 'flood' }] });
  add('d1_rewind', L(6).start, L(8).start, 'slam', { hits: [{ t: L(6).start, text: 'REWIND' }, { t: L(7).start, text: 'REWIND', style: 'flood' }] });

  // loop 2 ---------------------------------------------------------------------------------------------------
  const shot2 = W('shot', 2), and2 = W('and', 1, { after: shot2 }), drop2 = ev('drop', 2, sec('drop2'));
  add('v3_road', L(8).start, L(11).start, 'road', { roto: 'ld_road', lines: [8], sirens: 0.6, attempt: 2 });
  add('b2_tree', L(11).start, L(13).start, 'tree', { seed: 11, depth: 6, dead: 1, attempt: 2, flipAt: 1e9, lines: [11] });
  add('b2_suits', L(13).start, shot2, 'suits', { roto: 'ld_suits', lines: [13], eval: [-2, -6], mate: -1, attempt: 2, move: { n: 1, move: 'bolt', nag: '?', at: 0.4 } });
  add('b2_freeze', shot2, and2, 'freeze', { source: 'b2_suits', attempt: 2 });
  add('b2_rewind', and2, drop2, 'rewind', { from: shot2, to: L(11).start, lines: [13] });
  add('d2_slam', drop2, sec('breakdown', drop2 + 30), 'slam', { hits: [{ t: drop2, text: 'STOPS' }, { t: L(14).start, text: 'REWIND' }, { t: L(15).start, text: 'REWIND', style: 'flood' }] });

  // breakdown → loop 3 ---------------------------------------------------------------------------------------
  const never = W('never'), fd = sec('final_drop', never + 2);
  add('bd_page', sec('breakdown', drop2 + 30), never, 'page', { ...page, lines: [16, 17, 18], size: 78, y: 360, folio: '48', attempt: 3 });
  add('b3_never', never, fd, 'slam', { hits: [{ t: never, text: 'NEVER' }, { t: W('stop', 1, { after: never }), text: 'STOP', style: 'flood' }] });
  const endT = sec('end', T.duration - 5);
  add('fd_road', fd, endT, 'road', { roto: 'ld_road', attempt: 3 });
  add('qed', endT, T.duration + 1, 'black', { caption: '∎' });
  return S;
}
