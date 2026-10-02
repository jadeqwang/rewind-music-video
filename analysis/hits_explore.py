import librosa, numpy as np, scipy.signal as ss
sr=48000
y,_=librosa.load('../Rewind (4).mp3',sr=sr,mono=True)
hop=240
S=np.abs(librosa.stft(y,n_fft=2048,hop_length=hop))
L=np.log1p(1000*S)
fl=np.maximum(0,np.diff(L,axis=1)).sum(0); fl=np.r_[0,fl]
t=np.arange(len(fl))*hop/sr
# adaptive: subtract running median 1s
med=ss.medfilt(fl,201)
x=fl-med
pk,pr=ss.find_peaks(x,distance=int(0.08*sr/hop),prominence=np.percentile(x,99))
order=np.argsort(-x[pk])
print(len(pk))
for i in order[:60]:
    p=pk[i]; print(f"{t[p]:8.3f} {x[p]/np.percentile(x,99.9):.2f}")
