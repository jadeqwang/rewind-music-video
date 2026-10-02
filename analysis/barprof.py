import librosa, numpy as np, soundfile as sf
sr=22050
y,_=librosa.load('stems/no_vocals.wav',sr=sr); v,_=librosa.load('stems/vocals.wav',sr=sr)
r=np.load('mm_db_mix.npy'); d=r[r[:,1]==1,0]
S=np.abs(librosa.stft(y,n_fft=2048,hop_length=512)); f=librosa.fft_frequencies(sr=sr,n_fft=2048)
tt=librosa.frames_to_time(np.arange(S.shape[1]),sr=sr,hop_length=512)
def db(x): return 10*np.log10(x+1e-9)
bands=[(20,60),(60,150),(150,500),(500,2000),(2000,6000),(6000,11000)]
print('bar  start   ' + ' '.join(f'{a}-{b}' .rjust(9) for a,b in bands)+'  voc  flux')
oe=librosa.onset.onset_strength(y=y,sr=sr,hop_length=512)
for i in range(len(d)):
    a=d[i]; b=d[i+1] if i+1<len(d) else 232.44
    m=(tt>=a)&(tt<b)
    e=[db((S[(f>=lo)&(f<hi)][:,m]**2).sum(0).mean()) for lo,hi in bands]
    vv=db(np.mean(v[int(a*sr):int(b*sr)]**2))
    print(f"{i+1:3d} {a:7.2f}  "+' '.join(f'{x:9.1f}' for x in e)+f" {vv:6.1f} {oe[m].mean():5.2f}")
