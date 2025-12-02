#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motion_pipeline.py

Wraps the Manim + Whisper + Librosa + ffmpeg pipeline into a single function:
    process_job(audio_path, video_path, output_dir, progress_callback, quality)

You can import and call this from Flask or any other UI.
"""

import os
import subprocess
import glob
from pathlib import Path
import hashlib
import datetime
import random
import string
import shutil
import json

import transcribe
import beat_analysis

SCENE_NAME = "FarsiKinetic"
MOTION_FILE = "motion.py"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
MEDIA_DIR = os.path.join(BASE_DIR, "media")

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

def _hash_file(path: str, chunk_size: int = 8192) -> str:
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()

def _unique_id() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rnd = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=4))
    return f"{ts}_{rnd}"

def _run_manim(quality: str = "h") -> str:
    """
    Run Manim to render the scene FarsiKinetic from motion.py.
    Output may be .mp4 or .mov; we match with wildcard.
    """
    if quality not in {"l", "m", "h", "p", "k"}:
        quality = "h"

    cmd = [
        "manim",
        f"-q{quality}",
        "-t",     # transparent background
        MOTION_FILE,
        SCENE_NAME,
    ]
    subprocess.run(cmd, check=True)

    pattern = os.path.join(
        MEDIA_DIR, "videos", Path(MOTION_FILE).stem, "*", f"{SCENE_NAME}.*"
    )
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"Could not find Manim output with pattern: {pattern}")
    matches.sort(key=os.path.getmtime)
    return matches[-1]

def _overlay_video(base_video: str, overlay_video: str, audio: str, output: str):
    """
    Overlay the transparent motion video on top of the base video
    while looping the base video so there's always image until the audio ends.
    """
    filter_complex = (
        "[1:v]scale=iw:-1[fg];"
        "[0:v][fg]overlay=(W-w)/2:(H-h)/2:format=auto[vout]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1", "-i", base_video,   # 0:v
        "-i", overlay_video,                      # 1:v
        "-i", audio,                              # 2:a
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "2:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output,
    ]
    subprocess.run(cmd, check=True)

def process_job(
    audio_path: str,
    video_path: str,
    output_dir: str,
    progress_callback=None,
    quality: str = "h",
) -> str:
    """
    Full pipeline for one job:
    1) Cache / build transcription segments (Whisper)
    2) Cache / build beats (Librosa)
    3) Run Manim scene
    4) Overlay with base video via ffmpeg
    """
    os.makedirs(output_dir, exist_ok=True)

    def _update(p, msg):
        if progress_callback:
            progress_callback(p, msg)

    _update(5, "محاسبه‌ی هش فایل صوتی...")
    audio_hash = _hash_file(audio_path)
    seg_cache = os.path.join(CACHE_DIR, f"segments_{audio_hash}.json")
    beats_cache = os.path.join(CACHE_DIR, f"beats_{audio_hash}.json")

    # segments.json
    if os.path.exists(seg_cache):
        _update(15, "استفاده از کش متن...")
        shutil.copy(seg_cache, os.path.join(BASE_DIR, "segments.json"))
    else:
        _update(15, "تبدیل صوت به متن (Whisper)...")
        transcribe.transcribe_audio(audio_path, seg_cache)
        shutil.copy(seg_cache, os.path.join(BASE_DIR, "segments.json"))

    # beats.json
    if os.path.exists(beats_cache):
        _update(35, "استفاده از کش ضرب‌ها...")
        shutil.copy(beats_cache, os.path.join(BASE_DIR, "beats.json"))
    else:
        _update(35, "تحلیل ضرب آهنگ (Librosa)...")
        beat_analysis.analyze_beats(audio_path, beats_cache)
        shutil.copy(beats_cache, os.path.join(BASE_DIR, "beats.json"))

    _update(55, "رندر موشن با Manim...")
    manim_out = _run_manim(quality=quality)

    uid = _unique_id()
    overlay_src = os.path.join(output_dir, f"manim_{uid}{Path(manim_out).suffix}")
    shutil.copy(manim_out, overlay_src)

    final_output = os.path.join(output_dir, f"final_{uid}.mp4")
    _update(80, "ترکیب موشن با ویدیو اصلی (ffmpeg)...")
    _overlay_video(base_video=video_path, overlay_video=overlay_src, audio=audio_path, output=final_output)

    _update(100, "تمام شد ✅")
    return final_output
