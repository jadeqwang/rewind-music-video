import numpy as np, madmom, sys
from madmom.features.downbeats import RNNDownBeatProcessor, DBNDownBeatTrackingProcessor
from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
for name,fn in [('inst','stems/no_vocals.wav'),('mix','../Rewind (4).mp3')]:
    act=RNNDownBeatProcessor(num_threads=4)(fn)
    np.save(f'mm_act_{name}.npy',act)
    proc=DBNDownBeatTrackingProcessor(beats_per_bar=[4],fps=100,min_bpm=110,max_bpm=140,transition_lambda=100)
    r=proc(act)
    np.save(f'mm_db_{name}.npy',r)
    print(name,len(r))
