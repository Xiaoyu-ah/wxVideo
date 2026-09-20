"""Create local daily production documents; no generation or publishing API calls."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys


def iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须为有效的 YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("日期格式必须为 YYYY-MM-DD")
    return value


def create_day(project_root: Path, day: str, topic: str) -> Path:
    day = iso_date(day)
    topic = topic.strip()
    if not topic or any(ord(character) < 32 for character in topic):
        raise ValueError("选题不能为空，也不能包含换行或控制字符")
    profile_path = project_root / "config" / "style-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    output_dir = project_root / "days" / day
    # This is a renderable placeholder structure, never a fabricated daily story.
    scene_specs = [
        ("opening", "提出问题", ["待填：今日问题", "与观众有何关系"], "待填：本期核心问题", "待填一个具体问题", "待填写：用具体问题引出本期主题。事实需要先核验，不把选题名称当成已经发生的新闻。"),
        ("use_case", "说明用途", ["待填：具体用途", "能帮哪一步"], "待填：一个使用场景", "待填场景与适用条件", "待填写：说明这项变化能帮观众完成哪一步。只写有来源支持的能力，示意案例要明确标注。"),
        ("evidence", "展示依据", ["待填：判断依据", "信息来自哪里"], "待填：可追溯的依据", "待填来源与支持的结论", "待填写：展示能够支持核心结论的原始依据。补全来源和日期，不用封面文案替代事实核验。"),
        ("boundary", "讲清边界", ["待填：使用边界", "哪些仍需确认"], "待填：限制或确认环节", "待填相关限制与人的职责", "待填写：解释本期内容实际相关的限制和确认环节。不要添加无依据的保证，也不要泛泛堆砌提醒。"),
        ("small_trial", "给出试用方法", ["待填：一个小任务", "怎样开始试用"], "待填：可执行的试用方法", "待填步骤与检查方法", "待填写：给出一个与主题有关的小任务和检查方法。实际体验与假设示例分开，不编造试用结果。"),
        ("closing", "总结", ["待填：本期结论", "记住一个变化"], "待填：一句有依据的总结", "待填观众可以带走的判断", "待填写：回到开头的问题，用一句有依据的话总结。根据内容自然收束，不添加虚构反馈或结果承诺。"),
    ]
    document = {
        "schema_version": 1,
        "channel": profile.get("account", {}).get("channel_name") or "AI趋势观察",
        "episode": "待填期号",
        "date": day,
        "title": "待填写：今日视频标题",
        "topic": topic,
        "status": "draft_requires_content_and_review",
        "style_status": profile.get("status", "unknown"),
        "template_basis": "三张封面及抽样播放帧支持视觉参考；六段、尺寸、帧率和转场为新制作方案，历史音频未完整分析",
        "audience": None,
        "main_message": None,
        "source_references": [],
        "cover_title": None,
        "scenes": [
            {
                "id": scene_id,
                "label": f"{index:02d} · {label}",
                "title": title,
                "card_title": card_title,
                "layout": "list",
                "items": [{"label": "待填", "text": item_text}],
                "takeaway": "待填：本段一句结论",
                "narration": narration,
                "source": "待核验 · 制作占位稿 · 不可发布",
                "duration": 10,
            }
            for index, (scene_id, label, title, card_title, item_text, narration) in enumerate(scene_specs, start=1)
        ],
        "publication_caption": None,
        "hashtags": [],
    }
    script_sections = "\n\n".join(
        f"### {index:02d}｜{scene['label'].split(' · ', 1)[1]}\n\n"
        f"占位时长：10 秒。\n\n{scene['narration']}"
        for index, scene in enumerate(document["scenes"], start=1)
    )
    storyboard_rows = "\n".join(
        f"| {index:02d} | {scene['label'].split(' · ', 1)[1]} | 10（暂定） | 待填 | 待填 | 待填 | 待核验 |"
        for index, scene in enumerate(document["scenes"], start=1)
    )
    files = {
        "script.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        "script.md": f"""# {day} 制作文案

选题：{topic}

状态：**待填占位稿，不可发布**；视觉参考状态为 `{document['style_status']}`。

已参考本人主页三张封面及抽样播放帧；历史音频未完整分析。六段结构、1080×1920、30fps、0.4 秒淡化转场和默认 60 秒均为新模板选择，不是源视频参数实测。

## 今天要表达什么

- 目标观众：待填写
- 一个核心表达：待填写
- 信息与素材来源：待填写
- 封面标题：待填写

## 文案

{script_sections}

## 同步要求

以 `script.json` 为后续制作输入，本文是创建时的可读占位快照，不会随 JSON 自动更新。

填写并核验内容后，可从项目根目录运行：

```text
python scripts/build_video.py days/{day}/script.json --output-dir days/{day}/video
```

构建器会输出 HTML、时间线、更新后的脚本和 SRT；不会自动配音、渲染或发布。未提供配音时为 `silent_preview`，字幕时序仅为估算。清除全部“待填”占位、补齐来源、实际生成音频并校准字幕后，再做完整预览和渲染检查。
""",
        "storyboard.md": f"""# {day} 分镜

选题：{topic}

制作规格：1080×1920、30fps；六段默认各 10 秒，共 60 秒，可调整为总长 55–75 秒。此为新模板方案，不是历史视频原始参数。

配音尚未生成，字幕时间尚未对齐；实际音频完成后校准各段时长。

| 镜头 | 目的 | 秒数 | 画面 | 配音 | 字幕 | 素材文件及来源 |
| --- | --- | --- | --- | --- | --- | --- |
{storyboard_rows}

## 制作记录

- 使用的剪辑工具：待填写
- 成片路径：待填写
- 素材是否需要授权：逐项核实
- 导出设置：按实际项目填写

当前构建器要求恰好六个场景，可在每场的 1–3 个信息项内调整表达。六段为本次日更方案，不代表历史作品都采用同一结构。
""",
        "publish.md": f"""# {day} 发布与复盘

选题：{topic}

## 发布文案

- 标题：待填写
- 正文：待填写
- 话题：待填写
- 封面：待填写
- 计划时间：待填写

## 成片检查

- [ ] 逐字检查字幕和封面，没有错字、截断或占位符。
- [ ] 每项新闻或产品声明有可追溯来源，事件日期与制作日期分开记录。
- [ ] 播放完整视频，画面、配音、字幕节奏一致。
- [ ] 人声清晰，音乐音量适当，没有突兀音量变化。
- [ ] 素材来源与使用条件已核实。
- [ ] 在实际发布预览中检查封面、画面与文字遮挡。
- [ ] 如平台要求内容标识，按发布时的实际要求填写。

## 复盘

| 记录项 | 数据 |
| --- | --- |
| 实际发布时间 | 待填写 |
| 观察时间及距发布时长 | 待填写 |
| 播放量 | 未获取 |
| 点赞 / 评论 / 分享 | 未获取 |
| 完播、观看时长等后台指标 | 未获取 |
| 观众反馈摘录 | 待填写 |
| 下次仅调整的一项变量 | 待填写 |

缺失指标写“未获取”，不要填成 0。比较作品时注明不同观察时长和其他差异，不能把单次表现直接归因于某个模板元素。
""",
    }
    # Reserve the whole date directory atomically; never overwrite existing work.
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    for name, contents in files.items():
        (output_dir / name).write_text(contents, encoding="utf-8")
    return output_dir


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="创建每日视频制作草稿，不自动生成或发布视频。")
    parser.add_argument("--date", type=iso_date, default=date.today().isoformat(), help="YYYY-MM-DD")
    parser.add_argument("--topic", required=True, help="今天的选题")
    args = parser.parse_args()
    topic = args.topic.strip()
    if not topic:
        parser.error("选题不能为空")
    try:
        target = create_day(Path(__file__).resolve().parents[1], args.date, topic)
    except FileExistsError:
        print("当天目录已经存在；为保护已有工作，未覆盖。", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"无法生成制作草稿：{exc}", file=sys.stderr)
        return 1
    print(f"已创建制作草稿：{target}")
    print("下一步：填写六段脚本并核验来源，再构建、配音、校准和检查；占位稿不可发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
