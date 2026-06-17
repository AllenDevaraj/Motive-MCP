# Launch the Motive MCP server on the Windows OptiTrack PC.
#
# PRE-FLIGHT: the Motive GUI must be CLOSED — the NPTrackingTools API takes ownership of the
# cameras, so the GUI and this server cannot both hold them.
#
# Usage:
#   .\run_server.ps1                 # serve on 0.0.0.0:8765
#   .\run_server.ps1 --selftest      # DLL + engine sanity check, no serving
#   .\run_server.ps1 --port 9000     # custom port

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$motive = Get-Process Motive -ErrorAction SilentlyContinue
if ($motive) {
    Write-Host "Motive GUI is running (PID $($motive.Id)). Close it first — the API needs the cameras." -ForegroundColor Red
    exit 1
}

# Show the IP to use from the laptop ('claude mcp add --transport http motive http://<ip>:8765/mcp')
$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -like "192.168.50.*" } | Select-Object -First 1).IPAddress
if ($ip) { Write-Host "This PC: http://$ip:8765/mcp" -ForegroundColor Cyan }

python "$here\motive_mcp_server.py" @args
