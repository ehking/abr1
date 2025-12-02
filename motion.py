#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
motion.py
Manim scene for Farsi Kinetic Typography with:
- Beat-based pulse
- Border glow
- Full-line Farsi text
"""

from manim import *
import json
import math

SEGMENTS_FILE = "segments.json"
BEATS_FILE = "beats.json"
FARSI_FONT = "B Nazanin"   # تغییر به فونت موجود روی سیستم‌تان

MIN_WAIT = 1 / 30  # ~0.033s

def make_calligraphic_line(text, frame_w):
    """
    ساخت استایل تایپوگرافی فارسی:
    - فونت خوشنویسی / دست‌نویس
    - استروک تیره + سایه
    """
    base = Text(
        text,
        font=FARSI_FONT,
        weight=BOLD,
    ).scale(1.4)

    max_width = frame_w * 0.8
    if base.width > max_width:
        base.scale(max_width / base.width)

    base.set_color("#F7F2EB")
    base.set_stroke("#1b100c", width=4, opacity=0.9)

    shadow = base.copy()
    shadow.set_color("#000000")
    shadow.set_opacity(0.45)
    shadow.set_stroke(width=0)
    shadow.shift(0.09 * DOWN + 0.07 * LEFT)

    group = VGroup(shadow, base)
    group.rotate(-6 * DEGREES)
    group.scale(1.05)
    return group

class FarsiKinetic(Scene):
    def construct(self):
        # load segments
        with open(SEGMENTS_FILE, encoding="utf-8") as f:
            segments = json.load(f)

        # load beats
        try:
            with open(BEATS_FILE, encoding="utf-8") as f:
                beats = json.load(f)
        except FileNotFoundError:
            beats = []
        beats = sorted(float(b) for b in beats)

        frame_w = self.camera.frame_width
        frame_h = self.camera.frame_height

        # border
        border = Rectangle(
            width=frame_w * 1.03,
            height=frame_h * 1.03,
        )
        border.set_stroke(color="#FFFFFF", width=2, opacity=0.18)
        border.set_fill(opacity=0.0)
        self.add(border)

        current_time = 0.0
        beat_index = 0

        for seg in segments:
            start = float(seg["start"])
            end = float(seg["end"])
            text = seg["text"].strip()
            if not text:
                continue

            segment_duration = max(0.4, end - start)

            # sync to segment start
            gap = start - current_time
            if gap > MIN_WAIT:
                self.wait(gap)
                current_time += gap
            elif gap > 0:
                current_time += gap

            # build calligraphic line
            line = make_calligraphic_line(text, frame_w)
            line.move_to(ORIGIN + 0.4*DOWN)

            intro_rt = min(0.45, segment_duration * 0.25)
            outro_rt = min(0.35, segment_duration * 0.2)
            used = intro_rt + outro_rt
            hold_rt = max(0.25, segment_duration - used)

            # enter
            self.play(
                line.animate.shift(0.3*UP).scale(1.08),
                run_time=intro_rt,
                rate_func=smooth,
            )
            current_time += intro_rt

            # hold + beat pulses
            hold_start = current_time
            hold_end = hold_start + hold_rt
            local_t = hold_start

            while beat_index < len(beats) and beats[beat_index] < hold_start - 0.01:
                beat_index += 1

            j = beat_index
            while j < len(beats) and beats[j] <= hold_end + 0.01:
                beat_time = beats[j]
                dt = beat_time - local_t
                if dt > MIN_WAIT:
                    self.wait(dt)
                    current_time += dt
                    local_t += dt

                pulse_rt = 0.08
                self.play(
                    line.animate.scale(1.05),
                    border.animate.set_stroke(opacity=0.45, width=3),
                    run_time=pulse_rt,
                    rate_func=there_and_back,
                )
                current_time += pulse_rt
                local_t += pulse_rt
                j += 1

            remaining = hold_end - local_t
            if remaining > MIN_WAIT:
                self.wait(remaining)
                current_time += remaining

            # exit
            self.play(
                FadeOut(line, shift=UP * 0.4),
                run_time=outro_rt,
                rate_func=smooth,
            )
            current_time += outro_rt
