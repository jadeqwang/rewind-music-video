import librosa, numpy as np, scipy.signal as ss, sys
sr=48000
y,_=librosa.load('../Rewind (4).mp3',sr=sr,mono=True)
def band(lo,hi):
    sos=ss.butter(4,[lo,hi],'band',fs=sr,output='sos'); x=ss.sosfiltfilt(sos,y)
    e=np.sqrt(np.convolve(x**2,np.ones(96)/96,'same')); return 20*np.log10(e+1e-7)
sub=band(30,70); mid=band(150,400); hi=band(3000,9000)
a,b=float(sys.argv[1]),float(sys.argv[2])
for t in np.arange(a,b,0.02):
    i=int(t*sr)
    s=sub[i]; bar='#'*int(max(0,s+40)/1.5)
    print(f"{t:8.2f} sub {s:6.1f} mid {mid[i]:6.1f} hi {hi[i]:6.1f} {bar}")
