import array
import math
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_onsets import detect_onsets  # noqa: E402


def write_clicks(path: Path, times, sr=44100, dur=2.6):
    n = int(sr * dur)
    buf = array.array("h", [0] * n)
    for t in times:
        i0 = int(t * sr)
        for j in range(int(0.08 * sr)):  # tiếng chuông tắt dần 80 ms, 880 Hz
            if i0 + j < n:
                buf[i0 + j] = int(20000 * math.exp(-j / (0.02 * sr)) * math.sin(2 * math.pi * 880 * j / sr))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(buf.tobytes())


class AudioOnsetsTest(unittest.TestCase):
    def test_detects_three_clicks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.wav"
            write_clicks(p, [0.50, 1.25, 2.00])
            got = detect_onsets(str(p))
            self.assertEqual(len(got), 3, got)
            for a, b in zip(got, [0.50, 1.25, 2.00]):
                self.assertLess(abs(a - b), 0.010)

    def test_silence_has_no_onsets(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.wav"
            write_clicks(p, [])
            self.assertEqual(detect_onsets(str(p)), [])


if __name__ == "__main__":
    unittest.main()
