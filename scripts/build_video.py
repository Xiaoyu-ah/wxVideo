#!/usr/bin/env python3
"""Build a six-scene, seekable Hyperframes composition using Python stdlib.

Run from the repository: python scripts/build_video.py examples/episode-demo.json
Audio paths are local WAV paths relative to --output-dir, not to the input JSON.
Caption start/end and audio_start are seconds relative to the scene start.
This builder writes index.html, timeline.json, script.md, and subtitles.srt only.
It does not fetch assets, run a renderer, publish a video, or change account data.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import unicodedata
import wave
from pathlib import Path, PurePosixPath
from typing import Any


WIDTH, HEIGHT, FPS = 1080, 1920, 30
TRANSITION = 0.4
GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
COMPOSITION_ID = "ai-trend-daily"


def units(value: str) -> float:
    """Conservative full-width character estimate for the fixed Chinese layout."""
    return sum(1.0 if unicodedata.east_asian_width(c) in "WF" else 0.6 for c in value)


def text_field(value: Any, name: str, maximum: float) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    value = value.strip()
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"{name} cannot contain control characters or line breaks")
    if units(value) > maximum:
        raise ValueError(f"{name} is too long for this layout ({units(value):.1f} > {maximum} units); shorten the copy")
    return value


def number(value: Any, name: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return value


def caption_chunks(narration: str) -> list[str]:
    phrases = re.findall(r"[^，。！？；、：]+[，。！？；、：]?", narration)
    chunks: list[str] = []
    for phrase in phrases:
        buffer = ""
        for char in phrase:
            if buffer and units(buffer + char) > 19:
                chunks.append(buffer)
                buffer = ""
            buffer += char
        if buffer:
            chunks.append(buffer)
    return chunks


def captions_for(scene: dict[str, Any], name: str) -> tuple[list[dict[str, Any]], str]:
    explicit = scene.get("captions")
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ValueError(f"{name}.captions must be a non-empty array when supplied")
        captions = []
        previous_end = 0.0
        for index, entry in enumerate(explicit):
            if not isinstance(entry, dict):
                raise ValueError(f"{name}.captions[{index}] must be an object")
            label = f"{name}.captions[{index}]"
            start = number(entry.get("start"), label + ".start")
            end = number(entry.get("end"), label + ".end")
            if end <= start or end > scene["duration"] + 1e-6:
                raise ValueError(f"{label} must satisfy 0 <= start < end <= scene duration")
            if start < previous_end - 1e-6:
                raise ValueError(f"{label} overlaps the previous caption")
            captions.append({"text": text_field(entry.get("text"), label + ".text", 38), "start": start, "end": end})
            previous_end = end
        return captions, "explicit"
    chunks = caption_chunks(scene["narration"])
    begin = scene.get("audio_start", 0.6)
    span = scene.get("audio_duration", scene["duration"] - begin - 0.4)
    weight = sum(max(1, units(chunk)) for chunk in chunks)
    cursor = begin
    captions = []
    for chunk in chunks:
        end = cursor + span * max(1, units(chunk)) / weight
        captions.append({"text": chunk, "start": round(cursor, 6), "end": round(end, 6)})
        cursor = end
    return captions, "estimated_by_text_length"


def validate_episode(data: Any, output_dir: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("The input must be a JSON object")
    result: dict[str, Any] = {
        "schema_version": 1,
        "channel": text_field(data.get("channel", "AI趋势观察"), "channel", 12),
        "episode": text_field(data.get("episode", "待填期号"), "episode", 12),
        "date": text_field(data.get("date", "待填日期"), "date", 14),
        "title": text_field(data.get("title"), "title", 50),
        "scenes": [],
    }
    source_scenes = data.get("scenes")
    if not isinstance(source_scenes, list) or len(source_scenes) != 6:
        raise ValueError("scenes must contain exactly six scene objects")
    seen_ids: set[str] = set()
    cursor = 0.0
    for index, raw in enumerate(source_scenes):
        name = f"scenes[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{name} must be an object")
        scene = dict(raw)
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", scene_id):
            raise ValueError(f"{name}.id must be a short ASCII identifier beginning with a letter")
        if scene_id in seen_ids:
            raise ValueError(f"Duplicate scene id: {scene_id}")
        seen_ids.add(scene_id)
        scene["duration"] = number(scene.get("duration", 10), name + ".duration", 4.0)
        if scene["duration"] > 25:
            raise ValueError(f"{name}.duration is above this template's 25-second scene limit")
        for key, maximum in {"label": 23, "card_title": 19, "takeaway": 19, "narration": 100, "source": 32}.items():
            scene[key] = text_field(scene.get(key), name + "." + key, maximum)
        title = scene.get("title")
        if not isinstance(title, list) or not 1 <= len(title) <= 2:
            raise ValueError(f"{name}.title must contain one or two short strings")
        scene["title"] = [text_field(line, f"{name}.title[{j}]", 9.2) for j, line in enumerate(title)]
        items = scene.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 3:
            raise ValueError(f"{name}.items must contain one to three objects")
        scene["items"] = []
        for j, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{name}.items[{j}] must be an object")
            scene["items"].append({
                "label": text_field(item.get("label"), f"{name}.items[{j}].label", 7),
                "text": text_field(item.get("text"), f"{name}.items[{j}].text", 26),
            })
        scene["layout"] = scene.get("layout", "list")
        if scene["layout"] not in ("list", "flow", "compare"):
            raise ValueError(f"{name}.layout must be list, flow, or compare")
        if scene["layout"] == "compare" and len(scene["items"]) != 2:
            raise ValueError(f"{name}: compare layout requires exactly two items")
        audio = scene.get("audio")
        if audio is not None:
            if not isinstance(audio, str) or "\\" in audio:
                raise ValueError(f"{name}.audio must be a relative POSIX-style WAV path")
            relative = PurePosixPath(audio)
            if relative.is_absolute() or ".." in relative.parts or ":" in audio or relative.suffix.lower() != ".wav":
                raise ValueError(f"{name}.audio must be a local relative WAV path without '..'")
            scene["audio"] = relative.as_posix()
            scene["audio_start"] = number(scene.get("audio_start", 0.5), name + ".audio_start")
            scene["audio_duration"] = number(scene.get("audio_duration"), name + ".audio_duration", 0.001)
            if scene["audio_start"] + scene["audio_duration"] > scene["duration"] + 1e-6:
                raise ValueError(f"{name}: audio runs beyond the scene duration")
            wav_path = (output_dir / relative).resolve()
            if not wav_path.is_relative_to(output_dir.resolve()) or not wav_path.is_file():
                raise ValueError(f"{name}: audio file must exist inside output-dir: {relative}")
            try:
                with wave.open(str(wav_path), "rb") as wav:
                    actual_duration = wav.getnframes() / wav.getframerate()
            except (wave.Error, EOFError) as exc:
                raise ValueError(f"{name}: cannot read PCM WAV: {relative}") from exc
            if abs(actual_duration - scene["audio_duration"]) > 0.05:
                raise ValueError(f"{name}: audio_duration differs from the WAV duration {actual_duration:.6f}s")
        elif "audio_duration" in scene or "audio_start" in scene:
            raise ValueError(f"{name}: audio_duration/audio_start requires audio")
        scene["start"] = round(cursor, 6)
        scene["end"] = round(cursor + scene["duration"], 6)
        scene["dom_id"] = f"scene-{index + 1:02d}"
        scene["captions"], scene["caption_timing"] = captions_for(scene, name)
        result["scenes"].append(scene)
        cursor += scene["duration"]
    if not 55 <= cursor <= 75:
        raise ValueError(f"Total duration must be 55–75 seconds; got {cursor:.3f}s")
    result["duration"] = round(cursor, 6)
    audio_count = sum("audio" in scene for scene in result["scenes"])
    result["mode"] = "silent_preview" if audio_count == 0 else "narrated_preview" if audio_count == 6 else "partial_audio_preview"
    result["caption_timing"] = "explicit" if all(s["caption_timing"] == "explicit" for s in result["scenes"]) else "includes_estimates"
    return result


CSS = """
@font-face { font-family: 'Microsoft YaHei'; src: local('Microsoft YaHei'); font-weight: 400; }
@font-face { font-family: 'Microsoft YaHei'; src: local('Microsoft YaHei Bold'); font-weight: 700 900; }
* { box-sizing: border-box; }
html, body { margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #080f22; }
body { font-family: 'Microsoft YaHei', sans-serif; color: #f3f6fb; }
#root { position: relative; width: 1080px; height: 1920px; overflow: hidden; background: #080f22; }
.scene { position: absolute; inset: 0; width: 1080px; height: 1920px; background-color: #080f22; }
.scene + .scene { opacity: 0; }
.scene-content { display: flex; flex-direction: column; gap: 30px; width: 100%; height: 100%; padding: 100px 84px 132px; }
.masthead { flex: 0 0 60px; display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
.brand { color: #f3f6fb; font-size: 32px; font-weight: 700; line-height: 1.5; white-space: nowrap; }
.edition { display: flex; flex-direction: column; color: #adbcd0; font-family: Consolas, monospace; font-size: 26px; text-align: right; line-height: 1.5; }
.hero { flex: 0 0 302px; display: flex; flex-direction: column; gap: 22px; }
.eyebrow { color: #77e1dc; font-size: 30px; line-height: 1.4; font-weight: 400; margin: 0; }
h1 { display: flex; flex-direction: column; gap: 2px; margin: 0; font-size: 94px; font-weight: 900; line-height: 1.2; letter-spacing: -0.015em; }
.title-line { display: block; max-width: 912px; white-space: nowrap; }
.title-line:last-child { color: #77e1dc; }
.card { flex: 1 1 auto; min-height: 620px; display: flex; flex-direction: column; gap: 30px; padding: 42px 42px 36px; border-radius: 30px; background: #f3f6fb; color: #080f22; }
.card-title { margin: 0; color: #243fa5; font-size: 40px; font-weight: 700; line-height: 1.35; }
.items { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 26px; }
.item { display: flex; align-items: flex-start; gap: 26px; min-width: 0; }
.item-label { flex: 0 0 136px; font-size: 34px; font-weight: 700; line-height: 1.5; color: #243fa5; overflow-wrap: anywhere; }
.item-text { margin: 0; flex: 1; min-width: 0; font-size: 44px; font-weight: 400; line-height: 1.45; overflow-wrap: anywhere; }
.layout-flow .item { gap: 28px; }
.layout-flow .item-label { flex-basis: 96px; font-variant-numeric: tabular-nums; }
.layout-compare .items { flex-direction: row; align-items: stretch; gap: 36px; }
.layout-compare .item { flex: 1; flex-direction: column; justify-content: center; gap: 30px; }
.layout-compare .item-label { flex: 0 0 auto; font-size: 38px; }
.layout-compare .item-text { flex: 0 0 auto; font-size: 44px; line-height: 1.6; text-wrap: balance; }
.takeaway { margin: 0; padding: 23px 24px; border-radius: 18px; background: #080f22; color: #edbe6b; font-size: 40px; line-height: 1.4; font-weight: 700; }
.source { flex: 0 0 80px; color: #adbcd0; font-size: 26px; line-height: 1.5; margin: 0; }
.caption-area { position: relative; flex: 0 0 150px; width: 100%; }
.caption { position: absolute; top: 0; left: 0; width: 100%; max-width: 912px; height: 144px; margin: 0; color: #f3f6fb; font-size: 42px; line-height: 1.55; font-weight: 400; text-align: center; overflow: visible; }
.preview-note { color: #adbcd0; font-size: 26px; }
.progress-track { flex: 0 0 6px; width: 100%; height: 6px; background: #adbcd0; border-radius: 3px; }
.progress-fill { width: 100%; height: 6px; background: #77e1dc; transform-origin: left center; border-radius: 3px; }
"""


def escaped(value: Any) -> str:
    return html.escape(str(value), quote=True)


def js_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_html(episode: dict[str, Any], gsap_src: str) -> str:
    scenes_html, audio_html = [], []
    voiced_label = "有声演示" if episode["episode"].upper().startswith("DEMO") else "已配音"
    mode_label = {"silent_preview": "静音预览", "partial_audio_preview": "部分配音预览", "narrated_preview": voiced_label}[episode["mode"]]
    for i, scene in enumerate(episode["scenes"]):
        sid = scene["dom_id"]
        title = "".join(f'<span class="title-line reveal">{escaped(line)}</span>' for line in scene["title"])
        items = "".join(f'<div class="item"><span class="item-label reveal">{escaped(item["label"])}</span><p class="item-text reveal">{escaped(item["text"])}</p></div>' for item in scene["items"])
        captions = "".join(f'<p id="{sid}-caption-{j}" class="caption">{escaped(caption["text"])}</p>' for j, caption in enumerate(scene["captions"]))
        scenes_html.append(f'''
    <section id="{sid}" class="scene" aria-label="{escaped(scene['label'])}" style="z-index:{i + 1}">
      <div class="scene-content">
        <header class="masthead">
          <div class="brand reveal">{escaped(episode['channel'])}</div>
          <div class="edition reveal"><span>{escaped(episode['episode'])} · {i + 1:02d}/06</span><span>{escaped(episode['date'])}</span></div>
        </header>
        <div class="hero">
          <p class="eyebrow reveal">{escaped(scene['label'])}</p>
          <h1>{title}</h1>
        </div>
        <article class="card layout-{scene['layout']}">
          <h2 class="card-title reveal">{escaped(scene['card_title'])}</h2>
          <div class="items">{items}</div>
          <p class="takeaway reveal">{escaped(scene['takeaway'])}</p>
        </article>
        <p class="source reveal">{escaped(scene['source'])}<span class="preview-note"> · {mode_label}</span></p>
        <div class="caption-area" aria-label="旁白字幕">{captions}</div>
        <div class="progress-track"><div class="progress-fill"></div></div>
      </div>
    </section>''')
        if "audio" in scene:
            audio_html.append(f'<audio id="audio-{i + 1:02d}" src="{escaped(scene["audio"])}" data-start="{scene["start"] + scene["audio_start"]:.6f}" data-duration="{scene["audio_duration"]:.6f}" data-track-index="2" data-volume="1" preload="auto"></audio>')
    timings = [{"id": scene["dom_id"], "start": scene["start"], "duration": scene["duration"], "captions": scene["captions"]} for scene in episode["scenes"]]
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=1080, initial-scale=1">
  <meta name="composition-mode" content="{episode['mode']}">
  <meta name="caption-timing" content="{episode['caption_timing']}">
  <title>{escaped(episode['title'])} · {escaped(episode['channel'])}</title>
  <script src="{escaped(gsap_src)}"></script>
  <style>{CSS}</style>
</head>
<body>
  <div id="root" data-composition-id="{COMPOSITION_ID}" data-start="0" data-duration="{episode['duration']}" data-width="1080" data-height="1920" data-track-index="0">
{''.join(scenes_html)}
{''.join(audio_html)}
  </div>
  <script>
    // Built synchronously so Hyperframes can discover this seekable timeline.
    window.__timelines = window.__timelines || {{}};
    const scenes = {js_json(timings)};
    const totalDuration = {episode['duration']};
    const tl = gsap.timeline({{ paused: true }});
    const eases = ["power3.out", "sine.out", "power2.out", "expo.out"];
    scenes.forEach((scene, sceneIndex) => {{
      const selector = "#" + scene.id;
      const start = scene.start;
      tl.addLabel(scene.id, start);
      if (sceneIndex > 0) {{
        // This simultaneous opacity swap IS the transition, not a pre-exit.
        tl.to("#" + scenes[sceneIndex - 1].id,
          {{ opacity: 0, duration: {TRANSITION}, ease: "power2.inOut" }}, start);
        tl.fromTo(selector, {{ opacity: 0 }},
          {{ opacity: 1, duration: {TRANSITION}, ease: "power2.inOut", immediateRender: false }}, start);
      }}
      tl.from(selector + " .card", {{ opacity: 0, scale: 0.985, duration: 0.55, ease: "power2.out" }}, start + 0.3);
      document.querySelectorAll(selector + " .reveal").forEach((element, elementIndex) => {{
        const shifts = [{{ y: 18 }}, {{ x: -14 }}, {{ y: 24 }}, {{ x: 12, y: 6 }}];
        tl.from(element, {{ ...shifts[elementIndex % shifts.length], opacity: 0,
          duration: 0.46 + (elementIndex % 3) * 0.05, ease: eases[elementIndex % eases.length] }},
          start + 0.15 + elementIndex * 0.07);
      }});
      tl.from(selector + " .progress-track", {{ opacity: 0, duration: 0.4, ease: "sine.out" }}, start + 0.2);
      tl.fromTo(selector + " .progress-fill", {{ scaleX: start / totalDuration }},
        {{ scaleX: (start + scene.duration) / totalDuration, duration: scene.duration, ease: "none" }}, start);
      scene.captions.forEach((caption, captionIndex) => {{
        const target = "#" + scene.id + "-caption-" + captionIndex;
        const captionStart = start + caption.start;
        const captionEnd = start + caption.end;
        tl.from(target, {{ opacity: 0, y: 8, duration: Math.min(0.18, (caption.end - caption.start) / 3), ease: "sine.out" }}, captionStart);
        // A caption lifecycle ends at its timestamp; no visibility/display animation.
        tl.set(target, {{ opacity: 0 }}, captionEnd);
      }});
    }});
    window.__timelines["{COMPOSITION_ID}"] = tl;
    window.__compositionMeta = {{ mode: {js_json(episode['mode'])}, captionTiming: {js_json(episode['caption_timing'])} }};
  </script>
</body>
</html>
'''


def srt_time(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds_whole, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_whole:02d},{millis:03d}"


def render_srt(episode: dict[str, Any]) -> str:
    output = []
    cue = 1
    for scene in episode["scenes"]:
        for caption in scene["captions"]:
            start = scene["start"] + caption["start"]
            end = scene["start"] + caption["end"]
            output.append(f"{cue}\n{srt_time(start)} --> {srt_time(end)}\n{caption['text']}\n")
            cue += 1
    return "\n".join(output)


def render_script(episode: dict[str, Any]) -> str:
    output = [f"# {episode['title']}", "", f"账号：{episode['channel']}  ",
              f"视频时长：{episode['duration']:.3f} 秒；画布：1080×1920；建议帧率：30 fps。  ",
              f"音频状态：`{episode['mode']}`；字幕时间：`{episode['caption_timing']}`。", "",
              "内容性质与来源见各场说明；核验记录以输入稿件的来源清单为准。", "",
              "`explicit` 表示使用输入中的字幕时间；`estimated_by_text_length` 是按文本长度估算，并未通过音频对齐。", ""]
    for index, scene in enumerate(episode["scenes"], 1):
        output.extend([f"## {index:02d}｜{scene['label']}", "",
                       f"时间：{scene['start']:.3f}–{scene['end']:.3f} 秒；字幕：`{scene['caption_timing']}`。", "",
                       f"标题：{' / '.join(scene['title'])}", "", f"旁白：{scene['narration']}", "",
                       f"卡片：{scene['card_title']}", ""])
        output.extend(f"- {item['label']}：{item['text']}" for item in scene["items"])
        output.extend(["", f"收束：{scene['takeaway']}", "", f"来源说明：{scene['source']}", ""])
        if "audio" in scene:
            output.extend([f"音频：`{scene['audio']}`；场内开始 {scene['audio_start']:.6f} 秒；长度 {scene['audio_duration']:.6f} 秒。", ""])
    return "\n".join(output)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=root / "examples" / "episode-demo.json")
    parser.add_argument("--output-dir", type=Path, default=root / "video")
    args = parser.parse_args(argv)
    try:
        source = json.loads(args.input.read_text(encoding="utf-8-sig"))
        episode = validate_episode(source, args.output_dir)
        local_gsap = args.output_dir / "vendor" / "gsap.min.js"
        gsap_src = "vendor/gsap.min.js" if local_gsap.is_file() else GSAP_CDN
        timeline = {
            "schema_version": 1, "composition_id": COMPOSITION_ID,
            "width": WIDTH, "height": HEIGHT, "fps": FPS,
            "transition": {"type": "crossfade", "duration": TRANSITION, "starts_at": "incoming_scene_start"},
            "gsap": gsap_src, **episode,
        }
        artifacts = {
            "index.html": render_html(episode, gsap_src),
            "timeline.json": json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
            "script.md": render_script(episode),
            "subtitles.srt": render_srt(episode),
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in artifacts.items():
            (args.output_dir / name).write_text(content, encoding="utf-8")
        print(f"Built {episode['duration']:.3f}s / 6 scenes / {episode['mode']} / captions: {episode['caption_timing']}")
        print(f"Composition: {(args.output_dir / 'index.html').resolve()}")
        print("Next: run Hyperframes lint, validate, inspect, visual checks, and render.")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"build_video: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
