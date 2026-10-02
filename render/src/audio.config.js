// audio.config.js: THE one place that picks the mix. The renderer reads timing/envelopes from it (browser, ?audio=<key>
// overrides) and render.mjs muxes `song` from it (--audio <key> overrides; --song <path> still wins over both).
// Every path falls back down its list, so a v5 entry works before analysis/envelopes_v5.json / timing_v5.json land.
export const AUDIO_DEFAULT = 'v5final';   // FINAL (user-approved): Rewind5_final.wav + timing_v5 + envelopes_v5
export const AUDIO = {
  v4:    { song: 'Rewind (4).mp3',                         timing: ['analysis/timing.json'],                          envelopes: ['analysis/envelopes.json'] },
  v4sfx: { song: 'assets/sound/Rewind_with_intro_sfx.mp3', timing: ['analysis/timing.json'],                          envelopes: ['analysis/envelopes.json'] },
  v5:    { song: 'Rewind (5).mp3',                         timing: ['analysis/timing_v5.json', 'analysis/timing.json'], envelopes: ['analysis/envelopes_v5.json', 'analysis/envelopes.json'] },
  v5sfx: { song: 'assets/sound/Rewind5_with_intro_sfx.mp3', timing: ['analysis/timing_v5.json', 'analysis/timing.json'], envelopes: ['analysis/envelopes_v5.json', 'analysis/envelopes.json'] },
  // v5final: v5 with the 6.6 s intro impact removed + intro SFX (tools/sound/declick_intro.py --v5) = the master for the final encode
  v5final: { song: 'assets/sound/Rewind5_final.wav',          timing: ['analysis/timing_v5.json', 'analysis/timing.json'], envelopes: ['analysis/envelopes_v5.json', 'analysis/envelopes.json'] },
};
export const audioCfg = key => AUDIO[key || AUDIO_DEFAULT] || AUDIO[AUDIO_DEFAULT];
