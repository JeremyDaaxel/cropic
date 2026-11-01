import os
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "sounds")


def tone(freq, dur, amp=0.5, decay=28.0, harmonics=(1.0, 0.32, 0.12), attack=0.004, bend=0.0):
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    f = freq * (1.0 + bend * t / max(dur, 1e-6))
    phase = 2 * np.pi * np.cumsum(f) / SR
    wave_ = sum(a * np.sin(phase * (i + 1)) for i, a in enumerate(harmonics))
    env = np.exp(-decay * t)
    a = int(SR * attack)
    if a > 1:
        env[:a] *= np.linspace(0, 1, a)
    return amp * wave_ * env


def seq(parts, gap=0.0):
    total = sum(len(p) for p in parts) + int(SR * gap) * max(0, len(parts) - 1)
    buf = np.zeros(total)
    pos = 0
    for p in parts:
        buf[pos:pos + len(p)] += p
        pos += len(p) + int(SR * gap)
    return buf


def save(name, sig, peak=0.75):
    sig = np.asarray(sig, dtype=np.float64)
    m = np.abs(sig).max()
    if m > 0:
        sig = sig / m * peak
    fade = int(SR * 0.008)
    sig[-fade:] *= np.linspace(1, 0, fade)
    data = (sig * 32767).astype(np.int16)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    print(f"  {name:16s} {len(data) / SR * 1000:5.0f} ms")


def main():
    save("hover.wav", tone(1180, 0.055, amp=0.22, decay=70, harmonics=(1.0, 0.15)), peak=0.28)
    save("click.wav", tone(760, 0.085, decay=55, harmonics=(1.0, 0.45, 0.2)), peak=0.55)
    save("select.wav", seq([tone(920, 0.07, decay=48), tone(1380, 0.10, amp=0.4, decay=40)]),
         peak=0.55)
    save("open.wav", seq([tone(660, 0.09, decay=34), tone(990, 0.16, amp=0.55, decay=26)]))
    save("close.wav", seq([tone(880, 0.08, decay=38), tone(587, 0.15, amp=0.55, decay=30)]))
    save("done.wav", seq([tone(784, 0.10, decay=26), tone(988, 0.10, decay=24),
                          tone(1319, 0.26, amp=0.6, decay=14)]))
    save("error.wav", seq([tone(320, 0.11, decay=30, harmonics=(1.0, 0.5, 0.3)),
                           tone(240, 0.20, amp=0.6, decay=22, harmonics=(1.0, 0.5, 0.3))]))
    save("ready.wav", seq([tone(1046, 0.07, decay=40), tone(1568, 0.18, amp=0.5, decay=22)]))
    save("tick.wav", tone(1500, 0.05, amp=0.35, decay=80, harmonics=(1.0, 0.2), bend=0.25),
         peak=0.4)
    save("lightmode.wav", seq([tone(784, 0.08, decay=30), tone(1046, 0.08, decay=28),
                               tone(1568, 0.22, amp=0.5, decay=16)]), peak=0.5)
    save("darkmode.wav", seq([tone(1046, 0.08, decay=30), tone(784, 0.08, decay=28),
                              tone(523, 0.24, amp=0.55, decay=14)]), peak=0.5)


if __name__ == "__main__":
    print("Generando efectos de sonido en", OUT)
    main()
