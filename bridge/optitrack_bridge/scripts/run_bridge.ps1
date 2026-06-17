param(
    [string]$ConfigPath = ".\config\bridge_config.example.yaml",
    [double]$MaxSeconds = 0
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path ".venv" "Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$env:PYTHONPATH = Join-Path $root "src"

if ($MaxSeconds -gt 0) {
    & $python -m optitrack_bridge.main --config $ConfigPath --max-seconds $MaxSeconds --log-level INFO
}
else {
    & $python -m optitrack_bridge.main --config $ConfigPath --log-level INFO
}
