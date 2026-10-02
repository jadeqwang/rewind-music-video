// shots.lookdev.js — the 12 s look-dev sequence (song 36.0 → 48.0: "I reach for my ID… and I do / With no warning
// I get shot / and time stops / stop, stop"). Select with ?shots=lookdev. Cuts are referenced to the timing data.
export const LOOKDEV_START = 36.0;          // window anchor (the only literal: where the 12 s slice of the song begins)
export const LOOKDEV_END = 48.0;

export function buildShots(T) {
  const reach = T.word('reach');
  const With = T.word('with');
  const shot = T.word('shot');
  const andTime = T.word('and', 1, { after: shot.start });
  const stop1 = T.word('stop', 1, { after: andTime.start });
  const stop2 = T.word('stop', 2, { after: andTime.start });
  const stop3 = T.word('stop', 3, { after: andTime.start });
  const L = reach.line_idx;                   // "I reach for my ID to show, and I do"
  return [
    { id: 'ld_page', t0: LOOKDEV_START, t1: With.start, scene: 'page',
      params: { roto: ['ld_jade', 'ld_road'], world: 'ld_road', lines: [L], notes: { id: '2' },
        footnotes: [{ mark: '2', text: 'NASA badge. Valid through tomorrow, 9:00 a.m.', word: 'id' }],
        header: 'Chapter 3.  Proof by Exhaustion', folio: '47', eval: [0.3, -0.9], attempt: 1, size: 100, y: 430, measure: 1020 } },
    { id: 'ld_suits', t0: With.start, t1: shot.start, scene: 'suits',
      params: { roto: 'ld_suits', lines: [With.line_idx], eval: [-0.9, -6], mate: -1, attempt: 1,
        move: { n: 1, move: 'pull over', nag: '?!', at: 0.4 }, banner: 'UNCLASSIFIED//FOR OFFICIAL USE ONLY', caseNo: 'FILE 65-HQ-██████', pageNo: 'b6 b7C' } },
    { id: 'ld_freeze', t0: shot.start, t1: andTime.start, scene: 'freeze',
      params: { source: 'ld_suits', attempt: 1, bullet: { x: 700, y: 452, len: 1300, angle: 0.025 } } },
    { id: 'ld_rewind', t0: andTime.start, t1: stop1.start, scene: 'rewind',
      params: { from: shot.start, to: LOOKDEV_START + 0.4, speeds: [2, 4, 8], segs: [0.3, 0.33, 0.37], hold: 0.1, lines: [andTime.line_idx] } },
    { id: 'ld_slam', t0: stop1.start, t1: stop3.start, scene: 'slam',
      params: { hits: [{ t: stop1.start, text: 'STOP', style: 'ink' }, { t: stop2.start, text: 'STOP', style: 'flood' }] } },
    { id: 'ld_tree', t0: stop3.start, t1: LOOKDEV_END, scene: 'tree',
      params: { seed: 7, depth: 6, dead: 1, grow: 1.1, attempt: 1, flipAt: 1.55, eval: [-9, 0.3], lines: [stop3.line_idx],
        labels: [{ node: 1, text: '1. pull over?!', color: '#FF2A2A' }, { node: 2, text: '1. bolt?' }, { node: 3, text: '1. keep driving!!', color: '#3DF2E6' }] } },
  ];
}
