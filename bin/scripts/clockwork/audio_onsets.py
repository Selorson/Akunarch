"""Tìm điểm phát âm (onset) trong file WAV PCM — chỉ dùng thư viện chuẩn. Dùng xếp chốt trống chuông theo nhạc."""

from __future__ import annotations

import array
import math
import wave


def _read_mono(path: str) -> tuple[list[float], int]:
    with wave.open(path, "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        data = array.array("h", raw)
        scale = 32768.0
    elif width == 4:
        data = array.array("i", raw)
        scale = 2147483648.0
    elif width == 3:
        data = [int.from_bytes(raw[i:i + 3], "little", signed=True) for i in range(0, len(raw), 3)]
        scale = 8388608.0
    elif width == 1:
        data = [b - 128 for b in raw]
        scale = 128.0
    else:
        raise ValueError(f"Độ sâu mẫu {width * 8}-bit chưa hỗ trợ: {path}")
    mono = [sum(data[i:i + ch]) / (ch * scale) for i in range(0, len(data), ch)]
    return mono, sr


def detect_onsets(wav_path: str, min_gap_s: float = 0.12, window_ms: float = 10.0) -> list[float]:
    """Thời điểm (giây) các âm bắt đầu: năng lượng RMS vượt ngưỡng 10% đỉnh, rồi dò ngược tới mẫu đầu tiên vượt 10% biên độ."""
    x, sr = _read_mono(wav_path)
    if not x:
        return []
    peak = max(abs(v) for v in x)
    if peak < 1e-4:
        return []
    win = max(1, int(sr * window_ms / 1000.0))
    hop = max(1, int(sr * 0.001))
    sq = [0.0]
    for v in x:
        sq.append(sq[-1] + v * v)
    env = [math.sqrt((sq[min(i + win, len(x))] - sq[i]) / win) for i in range(0, len(x), hop)]
    thresh = 0.10 * max(env)
    amp_thresh = 0.10 * peak
    onsets: list[float] = []
    above = False
    for k, e in enumerate(env):
        if e > thresh and not above:
            start = k * hop
            idx = next((i for i in range(start, min(start + win, len(x))) if abs(x[i]) > amp_thresh), start)
            t = idx / sr
            if not onsets or t - onsets[-1] >= min_gap_s:
                onsets.append(round(t, 4))
            above = True
        elif e < 0.5 * thresh:
            above = False
    return onsets
