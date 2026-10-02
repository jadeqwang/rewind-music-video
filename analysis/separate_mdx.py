"""Vocal separation with UVR MDX-Net Kim_Vocal_2 (ONNX, CPU) -- numpy reimplementation of UVR's MDX inference.
Writes stems/vocals.wav and stems/no_vocals.wav at 48 kHz (same length as the song).
"""
import numpy as np, soundfile as sf, onnxruntime as ort, soxr, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
# usage: separate_mdx.py [song path] [stem dir]   (defaults: Rewind (4).mp3 -> stems/)
SONG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'Rewind (4).mp3')
STEMS = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'stems')
N_FFT, HOP, DIM_F, DIM_T, COMP = 7680, 1024, 3072, 256, 1.009
CHUNK = HOP * (DIM_T - 1)
TRIM = N_FFT // 2
GEN = CHUNK - 2 * TRIM
NB = N_FFT // 2 + 1
WIN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)  # periodic hann


def stft(x):  # x [n, CHUNK] -> [n, NB, T] complex (torch.stft center=True reflect)
    xp = np.pad(x, ((0, 0), (N_FFT // 2, N_FFT // 2)), mode='reflect')
    idx = np.arange(DIM_T)[:, None] * HOP + np.arange(N_FFT)[None]
    fr = xp[:, idx] * WIN  # [n, T, N_FFT]
    return np.fft.rfft(fr, axis=-1).transpose(0, 2, 1)


def istft(S):  # [n, NB, T] -> [n, CHUNK]
    fr = np.fft.irfft(S.transpose(0, 2, 1), n=N_FFT, axis=-1) * WIN
    L = N_FFT + HOP * (DIM_T - 1)
    out = np.zeros((S.shape[0], L), np.float32)
    wsum = np.zeros(L, np.float32)
    for t in range(DIM_T):
        out[:, t * HOP:t * HOP + N_FFT] += fr[:, t]
        wsum[t * HOP:t * HOP + N_FFT] += WIN ** 2
    out = out / np.maximum(wsum, 1e-8)
    return out[:, N_FFT // 2:N_FFT // 2 + CHUNK]


def main():
    import librosa
    y, sr = librosa.load(SONG, sr=None, mono=False)
    print('loaded', y.shape, sr)
    n48 = y.shape[1]
    mix = soxr.resample(y.T, sr, 44100).T.astype(np.float32)
    n = mix.shape[1]
    pad = GEN - n % GEN
    mixp = np.concatenate([np.zeros((2, TRIM), np.float32), mix, np.zeros((2, pad + TRIM), np.float32)], 1)
    sess = ort.InferenceSession(os.path.join(HERE, 'models', 'Kim_Vocal_2.onnx'), providers=['CPUExecutionProvider'])
    iname = sess.get_inputs()[0].name
    outs = []
    t0 = time.time()
    for i in range(0, n + pad, GEN):
        w = mixp[:, i:i + CHUNK]
        S = stft(w)[:, :DIM_F]  # [2, F, T]
        X = np.stack([S[0].real, S[0].imag, S[1].real, S[1].imag])[None].astype(np.float32)
        Y = sess.run(None, {iname: X})[0][0]
        Sc = np.zeros((2, NB, DIM_T), np.complex64)
        Sc[0, :DIM_F] = Y[0] + 1j * Y[1]
        Sc[1, :DIM_F] = Y[2] + 1j * Y[3]
        wav = istft(Sc)
        outs.append(wav[:, TRIM:-TRIM])
        print(f'chunk {i // GEN} {time.time() - t0:.1f}s', flush=True)
    voc = np.concatenate(outs, 1)[:, :n] * COMP
    voc48 = soxr.resample(voc.T, 44100, sr)[:n48]
    if voc48.shape[0] < n48:
        voc48 = np.pad(voc48, ((0, n48 - voc48.shape[0]), (0, 0)))
    inst = y.T - voc48
    os.makedirs(STEMS, exist_ok=True)
    sf.write(os.path.join(STEMS, 'vocals.wav'), voc48, sr)
    sf.write(os.path.join(STEMS, 'no_vocals.wav'), inst, sr)
    print('done')


if __name__ == '__main__':
    main()
