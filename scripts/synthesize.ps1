<#
.SYNOPSIS
Generate Chinese demo narration using a locally installed Windows SAPI voice.
.DESCRIPTION
Creates phrase WAVs in the ignored repository work/tts folder, measures each WAV,
and produces video/audio/scene-XX.wav plus video/episode-with-audio.json.
This is a new synthetic demo voice, not a clone of historical narration.
.EXAMPLE
powershell -File scripts/synthesize.ps1 -Python python
.EXAMPLE
powershell -File scripts/synthesize.ps1 -Voice 'Microsoft Yaoyao' -Rate 2
#>
[CmdletBinding()]
param(
    [string]$Episode = '',
    [string]$OutputDir = '',
    [string]$WorkDir = '',
    [string]$Voice = 'Microsoft Huihui Desktop',
    [ValidateRange(-10, 10)][int]$Rate = 2,
    [string]$Python = '',
    [switch]$ResolvePythonOnly
)

$ErrorActionPreference = 'Stop'

function Resolve-VideoPython {
    param([string]$Requested)
    $taskCandidates = @()
    if ($Requested) {
        $taskCandidates += $Requested
    } else {
        if ($env:USERPROFILE) {
            $taskCandidates += Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        }
        foreach ($taskName in @('python3.exe', 'python.exe', 'py.exe', 'python3', 'python')) {
            $taskFound = Get-Command $taskName -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($taskFound) { $taskCandidates += $taskFound.Source }
        }
    }
    foreach ($taskCandidate in ($taskCandidates | Select-Object -Unique)) {
        $taskCommand = Get-Command $taskCandidate -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $taskCommand) { continue }
        $taskExecutable = $taskCommand.Source
        if ($taskExecutable -match '[\\/]WindowsApps[\\/]') { continue }
        try {
            $taskVersion = & $taskExecutable -c 'import sys; print(sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $taskExecutable }
        } catch {
            continue
        }
    }
    throw 'Python 3.10+ was not found. Install Python, add it to PATH, or pass -Python with its executable path. WindowsApps Store aliases are not accepted.'
}

$Python = Resolve-VideoPython -Requested $Python
if ($ResolvePythonOnly) {
    Write-Output $Python
    return
}
$taskRepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Episode) { $Episode = Join-Path $taskRepoRoot 'examples/episode-demo.json' }
if (-not $OutputDir) { $OutputDir = Join-Path $taskRepoRoot 'video' }
if (-not $WorkDir) { $WorkDir = Join-Path $taskRepoRoot 'work/tts' }
$Episode = [IO.Path]::GetFullPath($Episode)
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$WorkDir = [IO.Path]::GetFullPath($WorkDir)
$taskPrepare = Join-Path $PSScriptRoot 'prepare_audio.py'

Add-Type -AssemblyName System.Speech
$taskSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskAvailable = @($taskSynth.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object { $_.VoiceInfo.Name })
    if ($Voice -notin $taskAvailable) {
        throw "Requested voice '$Voice' is unavailable. Installed voices: $($taskAvailable -join ', ')"
    }
    $taskSynth.SelectVoice($Voice)
    $taskSynth.Rate = $Rate
    $taskSynth.Volume = 100
    $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        24000,
        [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono
    )
    & $Python $taskPrepare plan $Episode --output-dir $OutputDir --work-dir $WorkDir --voice $Voice --rate $Rate
    if ($LASTEXITCODE -ne 0) { throw 'Failed to prepare narration jobs.' }
    $taskPlanPath = Join-Path $WorkDir 'plan.json'
    $taskPlan = Get-Content -LiteralPath $taskPlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($taskJob in $taskPlan.jobs) {
        $taskSynth.SetOutputToWaveFile([string]$taskJob.wav, $taskFormat)
        $taskSynth.Speak([string]$taskJob.text)
        $taskSynth.SetOutputToNull()
    }
} finally {
    $taskSynth.Dispose()
}
& $Python $taskPrepare assemble $taskPlanPath
if ($LASTEXITCODE -ne 0) { throw 'Failed to assemble measured scene audio.' }
Write-Output 'Narration uses the selected Windows synthetic voice; it is not a voice clone.'
