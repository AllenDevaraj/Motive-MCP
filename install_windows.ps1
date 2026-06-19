#requires -Version 5.1
<#
  install_windows.ps1 - set up the Python env that lets publish_sportmodestate.py
  publish rt/sportmodestate on Windows.

  WHY THIS SCRIPT EXISTS
    The vendored Unitree SDK pins  cyclonedds==0.10.2 . That release has NO prebuilt
    Windows wheel for Python 3.11 / 3.12 / 3.13 (only 3.7-3.10). On 3.11+ pip falls
    back to a source build and dies with:
        "Could not locate cyclonedds. Try to set CYCLONEDDS_HOME or CMAKE_PREFIX_PATH"
    The cure is to run an interpreter that HAS a prebuilt 0.10.2 wheel - i.e. Python 3.10.

  PATHS (simplest first):
    auto / wheel310  : install/use python.org Python 3.10 (x64) -> OFFICIAL PyPI
                       cyclonedds 0.10.2 wheel. No compiler, no env vars, exact pin.
    community        : keep your existing 64-bit Python 3.11/3.12, install the
                       community-built 0.10.2 wheel (third-party GitHub release).
    native           : build the CycloneDDS C library from source (MSVC + CMake) and
                       compile the binding. Heavy last resort - run ELEVATED.

  RUN (from the motive-mocap repo root, PowerShell):
    powershell -NoProfile -ExecutionPolicy Bypass -File .\install_windows.ps1
    # alternatives:
    #   ... .\install_windows.ps1 -Mode community     (keep your Python 3.11/3.12)
    #   ... .\install_windows.ps1 -Mode native        (run from an ELEVATED shell)

  After it succeeds:
    .\.venv\Scripts\python.exe publish_sportmodestate.py
#>
param(
  [ValidateSet('auto','wheel310','community','native')] [string]$Mode = 'auto',
  [string]$CycloneHome = 'C:\cyclonedds',
  [string]$CDdsTag     = '0.10.2'   # CycloneDDS C-library git tag that pairs with binding 0.10.2
)
$ErrorActionPreference = 'Stop'
function Info($m){ Write-Host "[install] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[install] $m" -ForegroundColor Yellow }

# --- repo layout -------------------------------------------------------------
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }
$Sdk  = Join-Path $Root 'unitree_sdk2_python'
if (-not (Test-Path (Join-Path $Sdk 'setup.py'))) {
  throw "Run this from the motive-mocap repo root (cannot find unitree_sdk2_python\setup.py next to this script)."
}
$Venv = Join-Path $Root '.venv'
$VPy  = Join-Path $Venv 'Scripts\python.exe'
Info "Repo root: $Root"

# --- helpers -----------------------------------------------------------------
function Need-Winget {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget (App Installer) not found. Install 64-bit Python 3.10 from python.org and Git for Windows by hand, then re-run with -Mode community (or wheel310)."
  }
}
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
}
function Assert-64bit([string]$py){
  $bits = (& $py -c "import struct;print(struct.calcsize('P')*8)").Trim()
  if ($bits -ne '64') {
    throw "Interpreter '$py' is $bits-bit. cyclonedds 0.10.2 ships win_amd64 (64-bit) wheels only - a 32-bit/ARM Python reproduces the exact error. Use a 64-bit Python."
  }
}
function Find-Python310Exe {
  try {
    $exe = (& py -3.10 -c "import sys;print(sys.executable)" 2>$null)
    if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
  } catch {}
  foreach ($p in @(
      (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe'),
      'C:\Program Files\Python310\python.exe')) {
    if (Test-Path $p) { return $p }
  }
  return $null
}
function Ensure-Git {
  if (Get-Command git -ErrorAction SilentlyContinue) { return }
  Need-Winget
  Info 'Installing Git for Windows (winget)...'
  winget install --id Git.Git --source winget --accept-source-agreements --accept-package-agreements
  Refresh-Path
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git still not on PATH; open a NEW terminal and re-run.' }
}

# --- core: make a venv, install the SDK (+ optional pre-wheel), verify --------
function New-VenvAndInstall([string]$basePy, [string]$preWheelUrl){
  Assert-64bit $basePy
  if (Test-Path $Venv) { Info 'Removing stale .venv'; Remove-Item -Recurse -Force $Venv }
  Info "Creating venv:  $basePy -m venv .venv"
  & $basePy -m venv $Venv
  & $VPy -m pip install --upgrade pip
  if ($preWheelUrl) {
    Info "Pre-installing prebuilt cyclonedds 0.10.2 wheel: $preWheelUrl"
    & $VPy -m pip install $preWheelUrl
  }
  Info 'pip install -e unitree_sdk2_python   (pulls cyclonedds 0.10.2 + numpy + opencv-python)'
  & $VPy -m pip install -e $Sdk
  Verify-Stack
}

function Verify-Stack {
  $cv = (& $VPy -c "from importlib.metadata import version; print(version('cyclonedds'))" 2>$null)
  if ($cv) { $cv = ($cv | Select-Object -First 1).Trim() } else { $cv = 'unknown' }
  Info "cyclonedds installed: $cv"
  if ($cv -ne '0.10.2' -and $cv -ne 'unknown') { Warn "cyclonedds is $cv, not the pinned 0.10.2 - vendored IDL is only guaranteed against 0.10.2." }
  Info 'Checking the load-bearing IDL imports (the thing that was failing)...'
  & $VPy -c "from cyclonedds.idl import IdlStruct; from cyclonedds.domain import DomainParticipant; from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_; print('IDL import OK')"
  if ($LASTEXITCODE -ne 0) { throw 'IDL import failed.' }

  Info 'Publishing rt/sportmodestate once on loopback (no robot required)...'
  $smoke = @'
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__SportModeState_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
ChannelFactoryInitialize(0)                       # loopback / default domain
p = ChannelPublisher("rt/sportmodestate", SportModeState_)
p.Init()
p.Write(unitree_go_msg_dds__SportModeState_())
print("published rt/sportmodestate OK")
'@
  $tmp = Join-Path $env:TEMP 'mocap_smoke_sportmodestate.py'
  Set-Content -Path $tmp -Value $smoke -Encoding utf8
  try { & $VPy $tmp } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
  if ($LASTEXITCODE -ne 0) { throw 'Loopback publish failed (if it HUNG, allow the Windows Defender Firewall prompt / check your NIC, then re-run).' }

  Write-Host ''
  Info 'SUCCESS - the DDS stack imports and publishes.'
  Info 'Next:'
  Info '  1) edit the CONFIG block at the top of publish_sportmodestate.py'
  Info '  2) run:  .\.venv\Scripts\python.exe publish_sportmodestate.py'
  Info 'Note: a REAL robot needs the NIC name -> ChannelFactoryInitialize(0, "<AdapterName>"); loopback proves the stack, not connectivity.'
}

# --- PATH 1 (recommended): python.org 3.10 + official wheel -------------------
function Try-Wheel310 {
  Info 'PATH 1 (recommended): python.org Python 3.10 + OFFICIAL cyclonedds 0.10.2 wheel'
  $py = Find-Python310Exe
  if (-not $py) {
    Need-Winget
    Info 'Python 3.10 not found - installing the python.org build via winget (per-user, no admin; avoids the Microsoft Store trap)...'
    winget install --id Python.Python.3.10 --architecture x64 --scope user --source winget --accept-source-agreements --accept-package-agreements
    Refresh-Path
    $py = Find-Python310Exe
    if (-not $py) { throw 'Python 3.10 installed but not yet discoverable. Open a NEW terminal and re-run (the launcher/PATH register only in a fresh process).' }
  }
  Info "Using interpreter: $py"
  New-VenvAndInstall $py $null
}

# --- PATH 2: keep current 3.11/3.12, community prebuilt 0.10.2 wheel ----------
function Try-Community {
  Info 'PATH 2: keep your current Python, use the community prebuilt 0.10.2 wheel (still the exact pinned version)'
  # Use the CURRENT interpreter - Microsoft Store Python has NO `py` launcher, so resolve python/python3 directly.
  $cur = $null
  foreach ($name in @('python','python3')) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c) { $cur = $c.Source; break }
  }
  if (-not $cur) { throw 'No python/python3 on PATH. Use -Mode wheel310 (installs Python 3.10) instead.' }
  Assert-64bit $cur
  $ver = (& $cur -c "import sys;print('%d%d'%sys.version_info[:2])").Trim()
  switch ($ver) {
    '311' { $tag = 'cp311' }
    '312' { $tag = 'cp312' }
    default { throw "Community 0.10.2 wheels exist only for cp311/cp312 (this interpreter is cp$ver). Use -Mode wheel310 (Python 3.10) or -Mode native." }
  }
  $url = "https://github.com/LY1806620741/cyclonedds-python/releases/download/0.10.2/cyclonedds-0.10.2-$tag-$tag-win_amd64.whl"
  Info "Checking the community wheel is reachable: $url"
  try { Invoke-WebRequest -Method Head -Uri $url -UseBasicParsing -ErrorAction Stop | Out-Null }
  catch { throw "Community wheel not reachable ($url) - it may have been removed/renamed. Use -Mode wheel310 or -Mode native." }
  Info "Using interpreter: $cur"
  New-VenvAndInstall $cur $url
}

# --- PATH 3 (heavy fallback): build CycloneDDS C lib from source --------------
function Try-Native {
  Warn 'PATH 3 (heavy fallback): build CycloneDDS C library from source. Needs MSVC + CMake. RUN FROM AN ELEVATED SHELL.'
  Need-Winget
  Ensure-Git
  Info 'Installing VS 2022 Build Tools (C++ workload + CMake component)...'
  winget install --id Microsoft.VisualStudio.2022.BuildTools --source winget --accept-source-agreements --accept-package-agreements `
    --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.CMake.Project --includeRecommended"

  # Bring cmake.exe / cl.exe onto PATH via the VS developer shell (they are NOT on the global PATH).
  $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
  if (-not (Test-Path $vswhere)) { throw 'vswhere not found. Open the "x64 Native Tools Command Prompt for VS 2022" and run the cmake steps from WINDOWS_INSTALL.md by hand.' }
  $vsPath = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
  if ($vsPath) { $vsPath = ($vsPath | Select-Object -First 1).Trim() }
  if (-not $vsPath) { throw 'VS Build Tools with the C++ toolset not found after install.' }
  Import-Module (Join-Path $vsPath 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
  Enter-VsDevShell -VsInstallPath $vsPath -DevCmdArguments '-arch=x64 -host_arch=x64' -SkipAutomaticLocation
  if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) { throw 'cmake still not on PATH after Enter-VsDevShell. Run from the "x64 Native Tools Command Prompt for VS 2022".' }

  $src = Join-Path $env:TEMP 'cyclonedds_src'
  if (Test-Path $src) { Remove-Item -Recurse -Force $src }
  git clone https://github.com/eclipse-cyclonedds/cyclonedds.git $src
  Push-Location $src
  try {
    git checkout $CDdsTag        # tag 0.10.2 pairs with binding 0.10.2; do NOT use master/11.x (causes the C1083 q_radmin.h error)
    cmake -G "Visual Studio 17 2022" -A x64 -DCMAKE_INSTALL_PREFIX="$CycloneHome" -DBUILD_EXAMPLES=OFF -B build .
    cmake --build build --config Release --target install
  } finally { Pop-Location }
  foreach ($d in @('bin\ddsc.dll','include','lib')) {
    if (-not (Test-Path (Join-Path $CycloneHome $d))) { throw "native install is missing '$d' under $CycloneHome (cyclone_search needs bin+include+lib or it re-emits the same error)." }
  }

  # Persist env: CYCLONEDDS_HOME (build-time discovery) + bin on PATH (runtime DLL load).
  # Use SetEnvironmentVariable for PATH, NOT setx (setx truncates PATH at 1024 chars).
  [Environment]::SetEnvironmentVariable('CYCLONEDDS_HOME', $CycloneHome, 'User')
  $userPath = [Environment]::GetEnvironmentVariable('Path','User')
  if ($userPath -notlike "*$CycloneHome\bin*") {
    [Environment]::SetEnvironmentVariable('Path', "$CycloneHome\bin;$userPath", 'User')
  }
  $env:CYCLONEDDS_HOME = $CycloneHome
  $env:Path = "$CycloneHome\bin;$env:Path"

  $cur = $null
  foreach ($name in @('python','python3')) { $c = Get-Command $name -ErrorAction SilentlyContinue; if ($c) { $cur = $c.Source; break } }
  if (-not $cur) { throw 'No python/python3 on PATH for the native build.' }
  Assert-64bit $cur
  if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
  & $cur -m venv $Venv
  & $VPy -m pip install --upgrade pip
  & $VPy -m pip install "cyclonedds==0.10.2" --no-binary cyclonedds
  $cv = (& $VPy -c "from importlib.metadata import version; print(version('cyclonedds'))" 2>$null)
  if ($cv) { $cv = ($cv | Select-Object -First 1).Trim() }
  if ($cv -ne '0.10.2') { throw "built cyclonedds is $cv, expected 0.10.2 (C-tag mismatch - re-checkout tag 0.10.2)." }
  & $VPy -m pip install -e $Sdk --no-deps
  & $VPy -m pip install numpy opencv-python
  Verify-Stack
}

# --- driver ------------------------------------------------------------------
switch ($Mode) {
  'wheel310'  { Try-Wheel310 }
  'community' { Try-Community }
  'native'    { Try-Native }
  'auto' {
    try { Try-Wheel310 }
    catch {
      Warn "Recommended path failed: $($_.Exception.Message)"
      Warn "Next options: keep your current Python with  -Mode community , or build from source with  -Mode native  (elevated). See WINDOWS_INSTALL.md."
      throw
    }
  }
}
