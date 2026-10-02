"""madmom downbeats for Rewind (5).mp3 -> mm_db_mix_v5.npy (same settings as madmom_db.py)"""
import numpy as np
from madmom.features.downbeats import RNNDownBeatProcessor, DBNDownBeatTrackingProcessor
act = RNNDownBeatProcessor(num_threads=2)('../Rewind (5).mp3')
np.save('mm_act_mix_v5.npy', act)
r = DBNDownBeatTrackingProcessor(beats_per_bar=[4], fps=100, min_bpm=110, max_bpm=140, transition_lambda=100)(act)
np.save('mm_db_mix_v5.npy', r); print(len(r))
