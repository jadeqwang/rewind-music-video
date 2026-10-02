import librosa, numpy as np
sr=22050; hop=64; fps=sr/hop
y,_=librosa.load('../Rewind (4).mp3',sr=sr,mono=True)
S=np.abs(librosa.stft(y,n_fft=2048,hop_length=hop))
f=librosa.fft_frequencies(sr=sr,n_fft=2048)
L=np.log1p(100*S[(f>30)&(f<110)]).sum(0)
lf=np.maximum(0,np.diff(L,prepend=L[0]))
lf=lf/np.percentile(lf,99.5)
np.save('oe_low.npy',lf)
b=np.load('beats_raw.npy')
# for each beat, low-flux at beat vs at midpoint to next beat
def val(t): i=int(t*fps); return lf[max(0,i-2):i+3].max()
for a in np.arange(0,232,4):
    m=(b>=a)&(b<a+4)
    bb=b[m]
    if len(bb)<2: continue
    on=np.mean([val(t) for t in bb]); off=np.mean([val(t+ (np.median(np.diff(b))/2)) for t in bb])
    print(f"{a:5.0f} on {on:.2f} off {off:.2f} {'OFF!' if off>on*1.3 else ''}")
