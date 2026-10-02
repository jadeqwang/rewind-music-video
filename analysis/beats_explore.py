import librosa, numpy as np
y, sr = librosa.load('../Rewind (4).mp3', sr=22050, mono=True)
hop=256
oenv = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
tempo, beats = librosa.beat.beat_track(onset_envelope=oenv, sr=sr, hop_length=hop, start_bpm=124, tightness=400, units='time')
print('tempo', tempo)
bt=np.array(beats)
d=np.diff(bt)
for i in range(0,len(bt)-1):
    if i%8==0: print(f"{bt[i]:7.3f} ibi {d[i]:.3f} bpm {60/d[i]:.1f}")
# local tempo windows
for s in range(0,232,10):
    m=(bt>=s)&(bt<s+10)
    if m.sum()>2: print(s, 60/np.median(np.diff(bt[m])))
