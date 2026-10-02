import soundfile as sf, numpy as np, sys
import scipy.signal as ss
y,sr=sf.read('../../Rewind (4).mp3') if False else (None,None)
import librosa
y,sr=librosa.load('../../Rewind (4).mp3',sr=48000,mono=True)
v,_=sf.read('../stems/vocals.wav'); v=v.mean(1)
b,a=ss.butter(4,150/(sr/2)); low=ss.filtfilt(b,a,y)
def db(x,i,h): return 20*np.log10(np.sqrt(np.mean(x[i:i+h]**2))+1e-9)
a0,a1,step=float(sys.argv[1]),float(sys.argv[2]),float(sys.argv[3])
h=int(step*sr)
for t in np.arange(a0,a1,step):
    i=int(t*sr)
    print(f"{t:8.3f} mix {db(y,i,h):6.1f} low {db(low,i,h):6.1f} voc {db(v,i,h):6.1f}")
