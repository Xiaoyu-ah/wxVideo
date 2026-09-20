# AI趋势观察 · 每日视频模板 v1

已经实际生成带中文配音的竖屏样片：约70.7秒，1080×1920，30fps。模板包含六段脚本、图卡动画、逐句字幕、3:4封面和账号改版提案。

本版依据用户确认的主页、前三条封面和播放画面抽样整理。保留“场景问题＋具体用途＋能力边界”的表达；没有完整分析历史音轨，不声称复刻原声或全部剪辑节奏。详细依据见 [分析记录](docs/analysis-status.md)。

## 先看这些

- [改版方案](templates/brand-profile.md)：推荐保留“AI趋势观察”，简介更直接；另有两套名称方案。
- [新版头像](assets/avatar-proposal.png) 与 [样片封面](assets/cover-demo.png)。
- [演示脚本](video/script.md)、[逐句字幕](video/subtitles.srt)、[生成输入](examples/episode-demo.json)。
- [每日流程](docs/daily-workflow.md)、[制作提示词](prompts/daily-production.md)、[视觉规范](DESIGN.md)。
- [验证记录](docs/validation.md)。

本样片“看到AI新功能，先问三句话”是原创方法演示，不是当日新闻或产品实测。头像与资料是提案，尚未应用到微信。

## 在这台电脑上生成视频

在此项目目录打开 PowerShell，执行：

```powershell
powershell -File scripts/make-video.ps1
```

流程：中文配音 → 按实际音频长度生成字幕 → 视频与封面HTML → Hyperframes完整检查 → 导出 `renders/demo.mp4`。默认用 Windows 的 Microsoft Huihui Desktop 中文合成音；无需付费配音服务。

已有演示配音随项目提供。只更改排版、没有改变旁白时可以复用：

```powershell
powershell -File scripts/make-video.ps1 -ReuseAudio
```

只准备源文件、不检查或导出视频：

```powershell
powershell -File scripts/make-video.ps1 -ReuseAudio -PrepareOnly
```

`-ReuseAudio` 会检查旁白与场景编号是否匹配；改口播后应去掉该参数。每次生成会更新 `video/` 中的当前作品，所以先保存要保留的旧稿。

## 每日换选题

```powershell
.\scripts\new-day.ps1 -Date 2026-09-21 -Topic "填写今天的选题"
```

该步骤只创建当天制作文件夹，不覆盖已有日期。填好 `days/2026-09-21/script.json` 中的六段内容与来源，删除全部“待填”文字，再运行：

```powershell
powershell -File scripts/make-video.ps1 -Episode days/2026-09-21/script.json -Output renders/2026-09-21.mp4
```

建议先用演示JSON熟悉字段。固定六段为：**问题、用途、依据、边界、试用、总结**。初稿每段约10秒；配音生成后以实际长度延长场景，合计必须55–75秒。超长时精简旁白后重做，不能截断音频。

当前是文字与图卡模板，可替换标题、卡片、来源和旁白。若需要产品操作录屏或复杂实测图表，需要扩展画面组件。每天的事实搜集和选题仍需执行 [制作提示词](prompts/daily-production.md)，不自动编造新闻或直接发布到微信。

## 封面

`build_cover.py` 读取同一JSON的封面字段（未填写时取首场内容），生成 `video/cover.html`。演示PNG已经提供。批量导出新封面时使用独立浏览器按 **1080×1440、缩放1** 截图，不用9:16视频直接拉伸。当前一键脚本生成封面HTML，**不自动导出封面PNG**。

## 换电脑使用

需要 Windows、Python 3.10+、中文 SAPI 语音、Node.js 22+ 与 npm/npx、FFmpeg/FFprobe、Chrome 或 Edge。脚本优先使用已存在的 Codex Python，也可用 `-Python` 指定；渲染器固定 `hyperframes@0.8.55`。

Edge 可通过环境变量 `HYPERFRAMES_BROWSER_PATH` 指向本机安装的 `msedge.exe`。FFmpeg、FFprobe需在PATH中，或使用对应的 `HYPERFRAMES_FFMPEG_PATH`、`HYPERFRAMES_FFPROBE_PATH`。这台电脑已准备本地渲染环境；它不是仓库的一部分，换电脑仍要安装依赖。首次运行会下载渲染器、GSAP及部分字体，需联网。

中文使用系统 Microsoft YaHei，字体文件不随项目分发。当前成片已在这台Windows电脑验证，其他系统需更换配音方式和合法可用的中文字体。

## GitHub与文件范围

用户指定目标：`Xiaoyu-ah/wxVideo`，要求为私有仓库。上传前核验可见性与访问权限；仓库链接是否已写入成功以实际提交为准。

提交模板、文档、生成源码，以及本项目新生成的头像、演示封面与六段系统配音。原始微信截图、微信缓存、聊天记录和本机渲染环境不进入仓库。成片MP4单独交付，默认不纳入Git版本管理。
