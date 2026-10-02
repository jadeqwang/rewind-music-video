import librosa, numpy as np
sr=22050
for a,b in [(42.0,45.3),(101.6,104.7),(169.6,171.6),(148.2,149.6)]:
    y,_=librosa.load('stems/no_vocals.wav',sr=sr,offset=a,duration=b-a)
    S=np.abs(librosa.stft(y,n_fft=8192,hop_length=441))
    f=librosa.fft_frequencies(sr=sr,n_fft=8192)
    cen=librosa.feature.spectral_centroid(S=S,sr=sr)[0]
    db=20*np.log10(S.sum(0)+1e-6)
    print('---',a,b)
    out=[]
    for i in range(0,S.shape[1],2):
        out.append(f"{a+i*441/sr:.2f}:{cen[i]:.0f}/{db[i]:.0f}")
    print(' '.join(out))
