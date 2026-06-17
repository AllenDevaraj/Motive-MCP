param(
    [string]$ConfigPath = ".\config\bridge_config.example.yaml"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPython = Join-Path ".venv" "Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$env:PYTHONPATH = Join-Path $root "src"

& $python -m optitrack_bridge.validate_setup --config $ConfigPath
