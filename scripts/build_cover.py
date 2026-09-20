#!/usr/bin/env python3
"""Build a 1080 x 1440 cover HTML from the episode JSON, using stdlib only.

Usage: python scripts/build_cover.py examples/episode-demo.json
The HTML references the project avatar using a relative path. Render video/cover.html
in a browser at viewport 1080 x 1440, device scale factor 1, to export the PNG.
"""

import argparse
import html
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def escape(value):
    return html.escape(str(value), quote=True)


def build_cover(data, avatar_src="../assets/avatar-proposal.png"):
    scenes = data.get("scenes", [])
    if not scenes:
        raise ValueError("Episode must contain at least one scene.")
    opening = scenes[0]
    cover = data.get("cover", {})
    if not isinstance(cover, dict):
        raise ValueError("cover must be an object when supplied.")
    title = cover.get("title", opening.get("title", []))
    items = cover.get("items", opening.get("items", []))
    if not isinstance(title, list) or not 1 <= len(title) <= 2:
        raise ValueError("The cover title must contain one or two lines.")
    if any(len(str(line)) > 10 for line in title):
        raise ValueError("Each title line must contain no more than 10 characters.")
    if not isinstance(items, list) or not 1 <= len(items) <= 3:
        raise ValueError("The cover requires one to three items.")
    for item in items:
        if len(str(item.get("label", ""))) > 2 or len(str(item.get("text", ""))) > 14:
            raise ValueError("Cover item labels allow 2 characters and questions allow 14.")
    channel = str(data.get("channel", "AI趋势观察"))
    episode = str(data.get("episode", ""))
    if len(channel) > 12 or len(episode) > 18:
        raise ValueError("Shorten the channel name or episode number for the cover.")
    # Demo provenance remains explicit; use optional cover overrides for real episodes.
    badge = str(cover.get("badge", "模板演示" if episode.upper().startswith("DEMO") else "每日观察"))
    deck_label = str(cover.get("deck_label", opening.get("card_title", "本期要点")))
    tagline = str(cover.get("tagline", scenes[-1].get("takeaway", "看懂用途，也看清边界")))
    if len(tagline) > 18 or len(badge) > 8:
        raise ValueError("Shorten the cover tagline or badge to preserve readability.")
    if len(deck_label) > 24:
        raise ValueError("The cover deck label must contain no more than 24 characters.")
    rows = "\n".join(
        '<div class="question-row"><span class="question-label">'
        + escape(item["label"])
        + '</span><span class="question-text">'
        + escape(item["text"])
        + '</span><span class="arrow" aria-hidden="true">↗</span></div>'
        for item in items
    )
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=1080, initial-scale=1">
<title>__CHANNEL__ · __EPISODE__ · 封面</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;width:1080px;height:1440px;overflow:hidden}
body{background:#080f22;color:#f3f6fb;font-family:"Microsoft YaHei","PingFang SC",sans-serif;-webkit-font-smoothing:antialiased}
.cover{position:relative;width:1080px;height:1440px;padding:78px 80px 64px;background:radial-gradient(ellipse at 95% 3%,rgba(119,225,220,.06),transparent 48%),#080f22}
.brand{display:flex;align-items:center;gap:24px;height:82px}
.brand img{height:82px;width:82px;border-radius:50%;object-fit:cover;border:1px solid rgba(119,225,220,.22)}
.brand-name{font-size:34px;font-weight:700;letter-spacing:2px}
.brand-note{font-family:Consolas,monospace;font-size:18px;letter-spacing:3px;color:#adbcd0;margin-top:6px}
.edition{margin-left:auto;align-self:center;text-align:right;font-family:Consolas,monospace;font-size:25px;letter-spacing:2px;color:#adbcd0}
.headline{margin:101px 0 0;font-size:91px;line-height:1.27;font-weight:700;letter-spacing:-2px;white-space:nowrap}
.headline span{display:block}
.headline .accent{color:#77e1dc;margin-top:8px}
.deck-label{display:flex;align-items:center;gap:16px;margin-top:70px;font-size:27px;color:#adbcd0;letter-spacing:3px}
.deck-label:before{content:"";width:36px;height:3px;background:#edbe6b;display:block}
.question-card{margin-top:28px;background:#f3f6fb;border:1px solid rgba(255,255,255,.7);border-radius:30px;padding:10px 43px;color:#080f22;box-shadow:0 18px 60px rgba(0,0,0,.17)}
.question-row{display:flex;align-items:center;gap:29px;height:157px;border-bottom:1px solid #d8e0ea}
.question-row:last-child{border-bottom:0}
.question-label{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:87px;height:67px;border-radius:15px;background:#e3eaf9;color:#243fa5;font-size:28px;font-weight:700;letter-spacing:1px}
.question-text{font-size:42px;line-height:1.35;font-weight:700;letter-spacing:-.8px;white-space:nowrap}
.arrow{margin-left:auto;color:#243fa5;opacity:.8;font-size:34px}
.tagline{margin-top:60px;font-size:39px;font-weight:700;letter-spacing:1px}
.tagline:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;background:#edbe6b;margin-right:19px;vertical-align:middle;transform:translateY(-3px)}
.footer{position:absolute;left:80px;right:80px;bottom:64px;padding-top:24px;border-top:1px solid #293247;display:flex;align-items:center;justify-content:space-between}
.footer-note{font-size:23px;letter-spacing:2px;color:#adbcd0}
.badge{font-size:23px;color:#edbe6b;letter-spacing:2px;padding:9px 17px;border:1px solid #5f523d;border-radius:8px}
</style></head><body><main class="cover" aria-label="__CHANNEL__ 视频封面">
<header class="brand"><img src="__AVATAR_SRC__" alt="账号标识"><div><div class="brand-name">__CHANNEL__</div><div class="brand-note">AI / DAILY OBSERVATION</div></div><div class="edition">__EPISODE__</div></header>
<h1 class="headline"><span>__TITLE_A__</span><span class="accent">__TITLE_B__</span></h1>
<div class="deck-label">__DECK_LABEL__</div>
<section class="question-card" aria-label="__DECK_LABEL__">__ROWS__</section>
<div class="tagline">__TAGLINE__</div>
<footer class="footer"><span class="footer-note">每天看懂一个变化</span><span class="badge">__BADGE__</span></footer>
</main></body></html>
""".replace("__ROWS__", rows).replace("__CHANNEL__", escape(channel)).replace(
        "__EPISODE__", escape(episode)
    ).replace("__TITLE_A__", escape(title[0])).replace("__TITLE_B__", escape(title[1] if len(title) == 2 else "")).replace(
        "__TAGLINE__", escape(tagline)
    ).replace("__BADGE__", escape(badge)).replace("__DECK_LABEL__", escape(deck_label)).replace("__AVATAR_SRC__", escape(avatar_src))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", nargs="?", type=Path, default=ROOT / "examples/episode-demo.json")
    parser.add_argument("--output", type=Path, default=ROOT / "video/cover.html")
    args = parser.parse_args()
    data = json.loads(args.episode.read_text(encoding="utf-8-sig"))
    avatar_src = Path(os.path.relpath(ROOT / "assets/avatar-proposal.png", args.output.parent.resolve())).as_posix()
    output = build_cover(data, avatar_src=avatar_src)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")
    print("Cover HTML: " + str(args.output))
    print("Export viewport: 1080 x 1440, deviceScaleFactor: 1")


if __name__ == "__main__":
    main()
