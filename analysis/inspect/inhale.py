import librosa, numpy as np, sys
sr=22050
a,b=float(sys.argv[1]),float(sys.argv[2])
v,_=librosa.load('../stems/vocals.wav',sr=sr,offset=a,duration=b-a)
y,_=librosa.load('../../Rewind (4).mp3',sr=sr,offset=a,duration=b-a)
hop=220
S=np.abs(librosa.stft(v,n_fft=1024,hop_length=hop))
f=librosa.fft_frequencies(sr=sr,n_fft=1024)
hi=20*np.log10(S[f>3000].sum(0)+1e-6); lo=20*np.log10(S[(f>100)&(f<1000)].sum(0)+1e-6)
flat=librosa.feature.spectral_flatness(S=S)[0]
rmsm=20*np.log10(librosa.feature.rms(y=y,frame_length=1024,hop_length=hop)[0]+1e-6)
for i in range(S.shape[1]):
    print(f"{a+i*hop/sr:7.2f} vhi {hi[i]:6.1f} vlo {lo[i]:6.1f} flat {flat[i]:.3f} mix {rmsm[i]:6.1f}")
