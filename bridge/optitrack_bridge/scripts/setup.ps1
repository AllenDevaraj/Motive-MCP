param(
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$python = Join-Path $VenvPath "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r ".\requirements.txt"

Write-Host "Setup complete. Use $python for runs."
