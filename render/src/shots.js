// shots.js — the main edit (skeleton). Cut times are symbolic: words, beats/downbeats and sections from the TimeMap.
// This is a placeholder pass that renders the whole song with the existing scenes; the director's edit replaces it.
// Shot: {id, t0, t1, scene, params}. Scenes: page, suits, freeze, rewind, slam, tree, black, road (see scenes/).
export function buildShots(T) {
  const S = [];
  const add = (id, t0, t1, scene, params = {}) => { if (t1 > t0) S.push({ id, t0, t1, scene, params }); };
  const w = (x, n = 1, o) => T.word(x, n, o).start;
  const end = T.duration;
  add('intro', 0, w('the'), 'road', { roto: 'ld_road' });
  add('v1_page', w('the'), w('i', 1, { after: 29 }), 'page', { roto: ['ld_jade', 'ld_road'], world: 'ld_road', lines: [0, 1, 2].slice(0, 1),
    notes: { defense: '1' }, footnotes: [{ mark: '1', text: 'tomorrow, 9:00 a.m.', word: 'defense' }], header: 'Chapter 3.  Proof by Exhaustion', folio: '47', eval: [0.3, 0.2], attempt: 1 });
  add('b1_suits', w('i', 1, { after: 29 }), w('shot'), 'suits', { roto: 'ld_suits', lines: [3], eval: [0.2, -6], mate: -1, attempt: 1, move: { n: 1, move: 'pull over', nag: '?!', at: 1 } });
  add('b1_freeze', w('shot'), w('and', 1, { after: w('shot') }), 'freeze', { source: 'b1_suits', attempt: 1 });
  add('b1_rewind', w('and', 1, { after: w('shot') }), w('stop', 1, { after: 44 }), 'rewind', { from: w('shot'), to: w('shot') - 8, lines: [6] });
  add('d1_slam', w('stop', 1, { after: 44 }), w('rewind'), 'slam', { hits: [{ t: w('stop', 1, { after: 44 }), text: 'STOP' }, { t: w('stop', 2, { after: 44 }), text: 'STOP', style: 'flood' }, { t: w('stop', 3, { after: 44 }), text: 'STOP' }] });
  add('d1_rewind', w('rewind'), w('now'), 'slam', { hits: [{ t: w('rewind'), text: 'REWIND' }, { t: w('rewind', 2), text: 'REWIND', style: 'flood' }] });
  add('v3_road', w('now'), T.section('build2').start, 'road', { roto: 'ld_road', lines: [12, 13, 14], sirens: 0.6, attempt: 2 });
  add('b2_tree', T.section('build2').start, w('rewind', 3), 'tree', { seed: 11, depth: 7, dead: 1, attempt: 2, flipAt: 1e9 });
  add('d2_slam', w('rewind', 3), T.section('breakdown').start, 'slam', { hits: [{ t: w('rewind', 3), text: 'REWIND' }, { t: w('rewind', 4), text: 'REWIND', style: 'flood' }] });
  add('bd_page', T.section('breakdown').start, w('never'), 'page', { roto: ['ld_jade'], lines: [22, 23], header: 'Chapter 3.  Proof by Exhaustion', folio: '48' });
  add('b3_slam', w('never'), T.section('final_drop').start, 'slam', { hits: [{ t: w('never'), text: 'NEVER STOP' }] });
  add('fd_road', T.section('final_drop').start, end - 0.5, 'road', { roto: 'ld_road', attempt: 3 });
  add('qed', end - 0.5, end + 1, 'black', { caption: '∎' });
  return S;
}
