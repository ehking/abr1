#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat_analysis.py
Beat detection for audio using librosa.

Creates beats.json:
[
  0.23,
  0.47,
  ...
]
"""

import json
import librosa
import numpy as np

def analyze_beats(audio_path: str, out_path: str):
    print(f"[BEAT] Loading audio → {audio_path}")
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    print("[BEAT] Running beat_track...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    beats = [float(t) for t in beat_times]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(beats, f, ensure_ascii=False, indent=2)

    tempo_arr = np.atleast_1d(tempo)
    tempo_val = float(tempo_arr[0]) if tempo_arr.size > 0 else 0.0
    print(f"[BEAT] Saved beats → {out_path} (tempo ≈ {tempo_val:.1f} BPM)")
    return out_path
