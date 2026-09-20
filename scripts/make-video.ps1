<#
.SYNOPSIS
Build a narrated video from episode JSON with Windows SAPI and Hyperframes.
.DESCRIPTION
Runs synthesis, measured caption preparation, video HTML, cover HTML, full
Hyperframes checks, and MP4 rendering. PrepareOnly skips checks/rendering so the
HTML can be prepared without Node, FFmpeg or a render browser; run a full check
before treating a prepared composition as validated.
.EXAMPLE
powershell -File scripts/make-video.ps1
.EXAMPLE
powershell -File scripts/make-video.ps1 -Episode days/2026-09-21/script.json -Output renders/2026-09-21.mp4
.EXAMPLE
powershell -File scripts/make-video.ps1 -ReuseAudio -PrepareOnly
#>
[CmdletBinding()]
param(
    [string]$Episode = '',
    [string]$Output = '',
    [switch]$ReuseAudio,
    [switch]$PrepareOnly,
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
$taskRepoRoot = Split-Path -Parent $PSScriptRoot
$taskVideoDir = Join-Path $taskRepoRoot 'video'
$taskSynthesize = Join-Path $PSScriptRoot 'synthesize.ps1'
if (-not $Episode) { $Episode = Join-Path $taskRepoRoot 'examples/episode-demo.json' }
if (-not $Output) { $Output = Join-Path $taskRepoRoot 'renders/demo.mp4' }
$Episode = [IO.Path]::GetFullPath($Episode)
$Output = [IO.Path]::GetFullPath($Output)
if (-not (Test-Path -LiteralPath $Episode -PathType Leaf)) { throw "Episode JSON not found: $Episode" }
if ([IO.Path]::GetExtension($Output) -ne '.mp4') { throw '-Output must be an MP4 file path.' }
$Python = & $taskSynthesize -Python $Python -ResolvePythonOnly
$taskAudioEpisode = Join-Path $taskVideoDir 'episode-with-audio.json'

if ($ReuseAudio) {
    if (-not (Test-Path -LiteralPath $taskAudioEpisode -PathType Leaf)) {
        throw 'No video/episode-with-audio.json found. Run once without -ReuseAudio to synthesize narration.'
    }
    # Reuse only matching narration; retain measured audio/timings, but allow
    # updated titles and other visual fields from the selected episode.
    $taskReuseCode = @'
import json, pathlib, sys
source = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
target = pathlib.Path(sys.argv[2])
audio = json.loads(target.read_text(encoding="utf-8-sig"))
if len(source["scenes"]) != len(audio["scenes"]):
    raise SystemExit("Cannot reuse audio: scene count changed. Run without -ReuseAudio.")
for fresh, old in zip(source["scenes"], audio["scenes"]):
    if fresh["id"] != old["id"] or fresh["narration"] != old["narration"]:
        raise SystemExit("Cannot reuse audio: scene IDs or narration changed. Run without -ReuseAudio.")
    for field in ("audio", "audio_start", "audio_duration", "captions"):
        fresh[field] = old[field]
    fresh["duration"] = max(float(fresh["duration"]), float(old["duration"]))
source["audio_production"] = audio.get("audio_production", {})
target.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
'@
    $taskReuseCode | & $Python - $Episode $taskAudioEpisode
    if ($LASTEXITCODE -ne 0) { throw 'Audio reuse validation failed.' }
    Write-Output 'Reusing the existing measured scene audio.'
} else {
    & $taskSynthesize -Episode $Episode -OutputDir $taskVideoDir -Python $Python
    if ($LASTEXITCODE -ne 0) { throw 'Narration synthesis failed.' }
}

& $Python (Join-Path $PSScriptRoot 'build_video.py') $taskAudioEpisode --output-dir $taskVideoDir
if ($LASTEXITCODE -ne 0) { throw 'Video HTML generation failed.' }
& $Python (Join-Path $PSScriptRoot 'build_cover.py') $taskAudioEpisode --output (Join-Path $taskVideoDir 'cover.html')
if ($LASTEXITCODE -ne 0) { throw 'Cover HTML generation failed.' }
if ($PrepareOnly) {
    Write-Output "Prepared video/index.html, cover.html, captions, and audio in $taskVideoDir"
    Write-Output 'PrepareOnly did not run Hyperframes checks or render an MP4. Run without -PrepareOnly to validate and render.'
    return
}

$taskNpx = Get-Command npx.cmd,npx -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$taskLocalRunner = $null
if (-not $taskNpx) {
    # A local environment prepared alongside this project is an optional fallback.
    # It is never copied into the repository and is not required on other PCs.
    $taskAncestor = [IO.DirectoryInfo]$taskRepoRoot
    for ($taskDepth = 0; $taskDepth -lt 4 -and $null -ne $taskAncestor; $taskDepth++) {
        $taskPossibleRunner = Join-Path $taskAncestor.FullName 'work/render-env/run-hyperframes.ps1'
        if (Test-Path -LiteralPath $taskPossibleRunner -PathType Leaf) {
            $taskLocalRunner = $taskPossibleRunner
            break
        }
        $taskAncestor = $taskAncestor.Parent
    }
}
if (-not $taskNpx -and -not $taskLocalRunner) {
    throw 'Rendering requires Node.js 22+ with npm/npx, FFmpeg/FFprobe, and a supported Chrome/Edge browser. Install these and rerun with -ReuseAudio, or use -PrepareOnly to build HTML.'
}

function Invoke-VideoHyperframes {
    param([string[]]$CommandArguments)
    if ($taskNpx) {
        & $taskNpx.Source --yes 'hyperframes@0.8.55' @CommandArguments
    } else {
        & $taskLocalRunner @CommandArguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Hyperframes failed (exit $LASTEXITCODE). Verify Node.js 22+, FFmpeg/FFprobe, and browser dependencies. For details run: npx --yes hyperframes@0.8.55 doctor"
    }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Output) | Out-Null
Push-Location $taskVideoDir
try {
    Invoke-VideoHyperframes -CommandArguments @('check', '.')
    Invoke-VideoHyperframes -CommandArguments @('render', '.', '--fps', '30', '--quality', 'high', '--workers', '2', '--output', $Output)
} finally {
    Pop-Location
}
Write-Output "Rendered MP4: $Output"
