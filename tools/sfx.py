"""간단한 효과음(점프, 게임 오버)을 합성해서 MP3 로 만든다 (numpy + lameenc)."""

import lameenc
import numpy as np

RATE = 44100


def _t(sec):
    return np.arange(int(RATE * sec)) / RATE


def _env(n, attack=0.004, release=0.06):
    e = np.ones(n)
    a = max(1, int(RATE * attack))
    r = max(1, int(RATE * release))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def _tone(freqs, dur, vol=0.3, wave="square", release=0.05):
    t = _t(dur)
    f = np.interp(t, np.linspace(0, dur, len(freqs)), freqs) if len(freqs) > 1 else np.full_like(t, freqs[0])
    phase = np.cumsum(f / RATE)
    if wave == "square":
        s = np.sign(np.sin(2 * np.pi * phase)) * 0.55 + np.sin(2 * np.pi * phase) * 0.45
    elif wave == "tri":
        s = 2 * np.abs(2 * (phase % 1) - 1) - 1
    else:
        s = np.sin(2 * np.pi * phase)
    return s * _env(len(t), release=release) * vol


def jump():
    return _tone([330, 560, 780], 0.13, 0.22, "square", 0.05)


def gameover():
    notes = [523, 440, 349, 262]
    parts = [_tone([n, n * 0.98], 0.17, 0.26, "square", 0.05) for n in notes[:-1]]
    parts.append(_tone([262, 240], 0.45, 0.26, "tri", 0.3))
    return np.concatenate(parts)


def to_mp3(samples):
    pcm = np.clip(samples, -1, 1)
    # 앞뒤로 짧은 무음을 붙여 디코더 끝잘림을 막는다
    pcm = np.concatenate([np.zeros(int(RATE * 0.01)), pcm, np.zeros(int(RATE * 0.05))])
    data = (pcm * 32767).astype(np.int16).tobytes()
    enc = lameenc.Encoder()
    enc.set_bit_rate(128)
    enc.set_in_sample_rate(RATE)
    enc.set_channels(1)
    enc.set_quality(2)
    mp3 = enc.encode(data) + enc.flush()
    duration = round(len(pcm) / RATE, 2)
    return bytes(mp3), duration


SOUNDS = {
    "점프": jump,
    "게임오버": gameover,
}
