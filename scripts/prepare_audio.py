#!/usr/bin/env python3
"""Prepare SAPI phrase jobs, then join measured PCM audio and aligned captions.

This uses Python's standard library only. All times come from WAV sample counts,
not text-length estimates. Invoke through synthesize.ps1 on Windows.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import wave
from pathlib import Path


def caption_phrases(text: str, maximum: int = 22) -> list[str]:
    """Prefer punctuation boundaries and keep every screen <=22 characters."""
    atoms = re.findall(r"[^，。！？；、：,.!?;:]+[，。！？；、：,.!?;:]?", text)
    chunks: list[str] = []
    current = ""
    for atom in atoms:
        atom = atom.strip()
        while len(atom) > maximum:
            if current:
                chunks.append(current)
                current = ""
            # Keep Latin words together when a whitespace boundary is available.
            cut = atom.rfind(" ", maximum // 2, maximum + 1)
            cut = cut if cut > 0 else maximum
            chunks.append(atom[:cut].strip())
            atom = atom[cut:].strip()
        if not atom:
            continue
        if current and len(current + atom) > maximum:
            chunks.append(current)
            current = ""
        current += atom
        if current[-1] in "。！？.!?；;":
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    if not chunks:
        raise ValueError("Narration must contain spoken text")
    return chunks


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def plan(args: argparse.Namespace) -> None:
    source = args.episode.resolve()
    episode = read_json(source)
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    jobs = []
    for scene_index, scene in enumerate(episode["scenes"], start=1):
        phrases = caption_phrases(scene["narration"])
        for phrase_index, phrase in enumerate(phrases, start=1):
            jobs.append({
                "scene_index": scene_index,
                "phrase_index": phrase_index,
                "text": phrase,
                "wav": str(work / f"scene-{scene_index:02d}-phrase-{phrase_index:02d}.wav"),
            })
    result = {
        "episode": str(source),
        "output_dir": str(args.output_dir.resolve()),
        "voice": args.voice,
        "rate": args.rate,
        "gap_seconds": args.gap,
        "audio_start": 0.5,
        "jobs": jobs,
    }
    write_json(work / "plan.json", result)
    print(f"Prepared {len(jobs)} phrases across {len(episode['scenes'])} scenes.")


def assemble(args: argparse.Namespace) -> None:
    job_plan = read_json(args.plan)
    episode = copy.deepcopy(read_json(Path(job_plan["episode"])))
    output_dir = Path(job_plan["output_dir"])
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    voice = job_plan["voice"]
    episode["audio_production"] = {
        "engine": "Windows System.Speech / SAPI",
        "voice": voice,
        "rate": job_plan["rate"],
        "note": "本期系统合成音；非历史作品原声，未做声音克隆。",
        "caption_timing": "Each caption follows its synthesized WAV's measured PCM sample boundaries.",
        "phrase_gap_seconds": job_plan["gap_seconds"],
    }
    totals = []
    for scene_index, scene in enumerate(episode["scenes"], start=1):
        jobs = [job for job in job_plan["jobs"] if job["scene_index"] == scene_index]
        if not jobs:
            raise ValueError(f"No audio jobs for scene {scene_index}")
        params = None
        segments = []
        captions = []
        cursor_samples = 0
        gap_samples = 0
        for index, job in enumerate(jobs):
            with wave.open(job["wav"], "rb") as audio:
                signature = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype())
                if signature[3] != "NONE" or signature[1] != 2:
                    raise ValueError(f"Expected 16-bit uncompressed PCM: {job['wav']}")
                if params is None:
                    params = signature
                    gap_samples = round(job_plan["gap_seconds"] * params[2])
                if signature != params:
                    raise ValueError("All phrase WAV files must use the same PCM format")
                frame_count = audio.getnframes()
                if frame_count <= 0:
                    raise ValueError(f"Empty phrase WAV: {job['wav']}")
                if index:
                    segments.append(b"\0" * gap_samples * params[0] * params[1])
                    cursor_samples += gap_samples
                start = job_plan["audio_start"] + cursor_samples / params[2]
                segments.append(audio.readframes(frame_count))
                cursor_samples += frame_count
                end = job_plan["audio_start"] + cursor_samples / params[2]
                captions.append({"text": job["text"], "start": round(start, 6), "end": round(end, 6)})
        relative_audio = f"audio/scene-{scene_index:02d}.wav"
        with wave.open(str(output_dir / relative_audio), "wb") as combined:
            combined.setnchannels(params[0])
            combined.setsampwidth(params[1])
            combined.setframerate(params[2])
            combined.writeframes(b"".join(segments))
        audio_duration = cursor_samples / params[2]
        scene["audio"] = relative_audio
        scene["audio_start"] = job_plan["audio_start"]
        scene["audio_duration"] = round(audio_duration, 6)
        scene["captions"] = captions
        scene["duration"] = round(max(float(scene["duration"]), job_plan["audio_start"] + audio_duration + 0.6), 6)
        totals.append(scene["duration"])
        print(f"Scene {scene_index:02d}: audio {audio_duration:.3f}s, scene {scene['duration']:.3f}s, {len(captions)} captions")
    output_json = output_dir / "episode-with-audio.json"
    write_json(output_json, episode)
    print(f"Total episode duration: {sum(totals):.3f}s.")
    print(f"Wrote {output_json}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    planning = modes.add_parser("plan")
    planning.add_argument("episode", type=Path)
    planning.add_argument("--output-dir", type=Path, required=True)
    planning.add_argument("--work-dir", type=Path, required=True)
    planning.add_argument("--voice", default="Microsoft Huihui Desktop")
    planning.add_argument("--rate", type=int, default=2, choices=range(-10, 11))
    planning.add_argument("--gap", type=float, default=0.12)
    joining = modes.add_parser("assemble")
    joining.add_argument("plan", type=Path)
    args = parser.parse_args()
    if args.mode == "plan":
        if args.gap < 0 or args.gap > 2:
            parser.error("--gap must be between 0 and 2 seconds")
        plan(args)
    else:
        assemble(args)


if __name__ == "__main__":
    main()
