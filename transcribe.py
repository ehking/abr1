#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribe.py
Simple wrapper around OpenAI Whisper to generate segments.json:
[
  {"start": ..., "end": ..., "text": "..."},
  ...
]
"""

import json
import whisper

def transcribe_audio(audio_path: str, out_path: str):
    """
    Transcribe the given audio file and write segments (start/end/text)
    into out_path.
    """
    print("[TRANSCRIBE] Loading Whisper model (small)...")
    model = whisper.load_model("small")

    print(f"[TRANSCRIBE] Transcribing: {audio_path}")
    result = model.transcribe(audio_path, language="fa", fp16=False)

    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg.get("text", "").strip(),
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"[TRANSCRIBE] Saved segments → {out_path}")
    return out_path
