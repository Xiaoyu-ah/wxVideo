param(
    [string]$Date = (Get-Date -Format 'yyyy-MM-dd'),
    [Parameter(Mandatory = $true)][string]$Topic
)

$ErrorActionPreference = 'Stop'
$runtimePython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $runtimePython) {
    $pythonExecutable = $runtimePython
} elseif ($pythonCommand -and $pythonCommand.Source -notmatch 'Microsoft\\WindowsApps') {
    $pythonExecutable = $pythonCommand.Source
} else {
    throw '未找到可用 Python。请安装 Python 3.10 或更新版本，再重新运行。'
}

& $pythonExecutable (Join-Path $PSScriptRoot 'new_day.py') --date $Date --topic $Topic
exit $LASTEXITCODE
