// audio.config.js: THE one place that picks the mix. The renderer reads timing/envelopes from it (browser, ?audio=<key>
// overrides) and render.mjs muxes `song` from it (--audio <key> overrides; --song <path> still wins over both).
// Every path falls back down its list, so a v5 entry works before analysis/envelopes_v5.json / timing_v5.json land.
export const AUDIO_DEFAULT = 'v4';   // flip to 'v5' (or 'v5sfx') for the final encode once the v5 analysis is in
export const AUDIO = {
  v4:    { song: 'Rewind (4).mp3',                         timing: ['analysis/timing.json'],                          envelopes: ['analysis/envelopes.json'] },
  v4sfx: { song: 'assets/sound/Rewind_with_intro_sfx.mp3', timing: ['analysis/timing.json'],                          envelopes: ['analysis/envelopes.json'] },
  v5:    { song: 'Rewind (5).mp3',                         timing: ['analysis/timing_v5.json', 'analysis/timing.json'], envelopes: ['analysis/envelopes_v5.json', 'analysis/envelopes.json'] },
  v5sfx: { song: 'assets/sound/Rewind_v5_with_intro_sfx.mp3', timing: ['analysis/timing_v5.json', 'analysis/timing.json'], envelopes: ['analysis/envelopes_v5.json', 'analysis/envelopes.json'] },
};
export const audioCfg = key => AUDIO[key || AUDIO_DEFAULT] || AUDIO[AUDIO_DEFAULT];
