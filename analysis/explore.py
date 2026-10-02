import librosa, numpy as np
y, sr = librosa.load('../Rewind (4).mp3', sr=22050, mono=True)
hop=512
rms = librosa.feature.rms(y=y, hop_length=hop)[0]
t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
f = librosa.fft_frequencies(sr=sr, n_fft=2048)
low = S[f<120].sum(0); 
db = 20*np.log10(rms+1e-9)
# print per-second summary
for s in range(0, 233):
    m = (t>=s)&(t<s+1)
    print(f"{s:3d} rms {db[m].mean():6.1f} min {db[m].min():6.1f} low {20*np.log10(low[m].mean()+1e-9):6.1f}")
