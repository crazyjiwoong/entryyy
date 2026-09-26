"""간단한 8비트 느낌 효과음을 합성해서 MP3 로 만든다 (numpy + lameenc)."""

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


def _square(freq, t):
    phase = np.cumsum(freq / RATE) if np.ndim(freq) else freq * t
    return np.sign(np.sin(2 * np.pi * phase)) * 0.6 + np.sin(2 * np.pi * phase) * 0.4


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


def land():
    t = _t(0.14)
    noise = np.random.default_rng(1).uniform(-1, 1, len(t)) * np.exp(-t * 45) * 0.25
    thump = np.sin(2 * np.pi * np.cumsum(np.interp(t, [0, 0.14], [150, 55]) / RATE)) * np.exp(-t * 28) * 0.55
    return (noise + thump) * _env(len(t), 0.001, 0.03)


def beep():
    return _tone([660], 0.11, 0.25, "square", 0.04)


def go():
    return np.concatenate([_tone([880], 0.09, 0.25, "square", 0.02), _tone([1320], 0.22, 0.25, "square", 0.08)])


def gameover():
    notes = [523, 440, 349, 262]
    parts = [_tone([n, n * 0.98], 0.17, 0.26, "square", 0.05) for n in notes[:-1]]
    parts.append(_tone([262, 240], 0.45, 0.26, "tri", 0.3))
    return np.concatenate(parts)


def newbest():
    notes = [523, 659, 784, 1047]
    parts = [_tone([n], 0.09, 0.22, "square", 0.02) for n in notes[:-1]]
    parts.append(_tone([1047], 0.3, 0.22, "square", 0.2))
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
    "착지": land,
    "삐": beep,
    "출발": go,
    "게임오버": gameover,
    "신기록": newbest,
}
