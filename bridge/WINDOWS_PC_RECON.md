# WINDOWS PC Recon Report

Generated: 2026-06-17 14:48:40 -06:00
Host: DESKTOP-7BL2VJ1
User: arpg

## A. Motive software

### A1. Motive version + install path

```powershell
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack" -Recurse -Filter "Motive.exe" -ErrorAction SilentlyContinue |
  ForEach-Object { "{0}  v{1}" -f $_.FullName, $_.VersionInfo.ProductVersion }
```

```text
C:\Program Files\OptiTrack\Motive\Motive.exe  v2.2.0.1

```

GUI-only required fields:
- Help -> About exact version + edition: **requires operator GUI check**
- License type (perpetual/subscription): **requires operator GUI check**

## B. Motive API / SDK availability

### B1. API headers/libs/DLLs + NMotive assembly

```powershell
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack" -Recurse -ErrorAction SilentlyContinue `
  -Include NPTrackingTools.h,NPTrackingTools.lib,NPTrackingTools.dll,MotiveAPI.h,MotiveAPI.lib,MotiveAPI.dll,NMotiveAPI.chm,NMotive.dll |
  Select-Object FullName,Length,LastWriteTime
```

```text

FullName                                                             Length LastWriteTime        
--------                                                             ------ -------------        
C:\Program Files\OptiTrack\Motive\assemblies\x64\NMotive.dll       54074368 11/8/2019 10:37:44 AM
C:\Program Files\OptiTrack\Motive\Help\NMotiveAPI.chm                812880 10/2/2019 1:41:56 PM 
C:\Program Files\OptiTrack\Motive\inc\NPTrackingTools.h               45633 10/22/2019 9:32:10 AM
C:\Program Files\OptiTrack\Motive\MotiveBatchProcessor\NMotive.dll 54074368 11/8/2019 10:37:44 AM



```

### B2. Batch Processor + CHM files

```powershell
Get-ChildItem "C:\Program Files\OptiTrack" -Recurse -ErrorAction SilentlyContinue `
  -Include MotiveBatchProcessor.exe,*.chm | Select-Object FullName
```

```text

FullName                                                                       
--------                                                                       
C:\Program Files\OptiTrack\Motive\Help\NMotiveAPI.chm                          
C:\Program Files\OptiTrack\Motive\MotiveBatchProcessor\MotiveBatchProcessor.exe



```

### B3. Obvious API/SDK/devkit folders

```powershell
Get-ChildItem "C:\Program Files\OptiTrack","C:\Program Files (x86)\OptiTrack","$env:USERPROFILE\Documents" -Directory -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'API|SDK|Devkit|NPTracking|NMotive|Sample' } | Select-Object FullName
```

```text

FullName                                         
--------                                         
C:\Program Files\OptiTrack\Motive\PeripheralAPI  
C:\Program Files\OptiTrack\Motive\Samples        
C:\Program Files\OptiTrack\Motive\Samples\NMotive



```


B Conclusions:
- Core Motive API artifacts found on this machine.
- DLL bitness checks:
  - C:\Program Files\OptiTrack\Motive\assemblies\x64\NMotive.dll: 64-bit (x64)
  - C:\Program Files\OptiTrack\Motive\MotiveBatchProcessor\NMotive.dll: 64-bit (x64)

## C. Python + build environment

### C1. Python versions

```powershell
python --version 2>$null; py -3 --version 2>$null
```

```text
[command invocation failed]
The term 'py' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

### C2. Python bitness

```powershell
python -c "import struct,sys; print('python', sys.version, struct.calcsize('P')*8, 'bit')" 2>$null
```

```text
[no output returned]
```

### C3. Python launchers in PATH

```powershell
where.exe python; where.exe py
```

```text
C:\Users\arpg\AppData\Local\Microsoft\WindowsApps\python.exe
where.exe : INFO: Could not find files for the given pattern(s).
At line:1 char:19
+ where.exe python; where.exe py
+                   ~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (INFO: Could not...ven pattern(s).:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 

```

### C4. pip version

```powershell
pip --version 2>$null
```

```text
[command invocation failed]
The term 'pip' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

### C5. C/C++ toolchain paths

```powershell
where.exe cl 2>$null; where.exe msbuild 2>$null
```

```text
[no output returned]
```

### C6. Visual Studio directories

```powershell
Get-ChildItem "C:\Program Files\Microsoft Visual Studio","C:\Program Files (x86)\Microsoft Visual Studio" -Directory -ErrorAction SilentlyContinue | Select-Object FullName
```

```text
[no output returned]
```

### C7. git path

```powershell
where.exe git 2>$null
```

```text
C:\Program Files\Git\cmd\git.exe

```


C Conclusions:
- Python: not found in tested launchers (python/py returned no output).
- pip returned no output (missing or not in PATH).
- MSVC cl.exe not found in PATH from this shell.
- Internet/proxy package-install capability: requires operator/network policy check.

## D. Network / how Linux reaches this PC

### D1. ipconfig /all

```powershell
ipconfig /all
```

```text

Windows IP Configuration

   Host Name . . . . . . . . . . . . : DESKTOP-7BL2VJ1
   Primary Dns Suffix  . . . . . . . : 
   Node Type . . . . . . . . . . . . : Hybrid
   IP Routing Enabled. . . . . . . . : No
   WINS Proxy Enabled. . . . . . . . : No
   DNS Suffix Search List. . . . . . : lan

Ethernet adapter Ethernet:

   Connection-specific DNS Suffix  . : 
   Description . . . . . . . . . . . : Realtek PCIe GbE Family Controller
   Physical Address. . . . . . . . . : FC-AA-14-D9-FA-9C
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes
   Link-local IPv6 Address . . . . . : fe80::8a48:56cd:3f6:a42b%7(Preferred) 
   Autoconfiguration IPv4 Address. . : 169.254.195.114(Preferred) 
   Subnet Mask . . . . . . . . . . . : 255.255.0.0
   Default Gateway . . . . . . . . . : 
   DHCPv6 IAID . . . . . . . . . . . : 368880148
   DHCPv6 Client DUID. . . . . . . . : 00-01-00-01-21-B3-B5-AD-FC-AA-14-D9-FA-9C
   DNS Servers . . . . . . . . . . . : fec0:0:0:ffff::1%1
                                       fec0:0:0:ffff::2%1
                                       fec0:0:0:ffff::3%1
   NetBIOS over Tcpip. . . . . . . . : Enabled

Ethernet adapter Npcap Loopback Adapter:

   Connection-specific DNS Suffix  . : 
   Description . . . . . . . . . . . : Npcap Loopback Adapter
   Physical Address. . . . . . . . . : 02-00-4C-4F-4F-50
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes
   Link-local IPv6 Address . . . . . : fe80::f139:d0c5:df74:589d%20(Preferred) 
   Autoconfiguration IPv4 Address. . : 169.254.221.201(Preferred) 
   Subnet Mask . . . . . . . . . . . : 255.255.0.0
   Default Gateway . . . . . . . . . : 
   DHCPv6 IAID . . . . . . . . . . . : 989986892
   DHCPv6 Client DUID. . . . . . . . : 00-01-00-01-21-B3-B5-AD-FC-AA-14-D9-FA-9C
   DNS Servers . . . . . . . . . . . : fec0:0:0:ffff::1%1
                                       fec0:0:0:ffff::2%1
                                       fec0:0:0:ffff::3%1
   NetBIOS over Tcpip. . . . . . . . : Enabled

Wireless LAN adapter Local Area Connection* 1:

   Media State . . . . . . . . . . . : Media disconnected
   Connection-specific DNS Suffix  . : 
   Description . . . . . . . . . . . : Microsoft Wi-Fi Direct Virtual Adapter
   Physical Address. . . . . . . . . : 42-E2-30-E9-A1-B9
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes

Wireless LAN adapter Local Area Connection* 2:

   Media State . . . . . . . . . . . : Media disconnected
   Connection-specific DNS Suffix  . : 
   Description . . . . . . . . . . . : Microsoft Wi-Fi Direct Virtual Adapter #2
   Physical Address. . . . . . . . . : 40-E2-30-E9-A1-B9
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes

Wireless LAN adapter Wi-Fi:

   Connection-specific DNS Suffix  . : lan
   Description . . . . . . . . . . . : Realtek 8821AE Wireless LAN 802.11ac PCI-E NIC
   Physical Address. . . . . . . . . : 40-E2-30-E9-A1-B9
   DHCP Enabled. . . . . . . . . . . : Yes
   Autoconfiguration Enabled . . . . : Yes
   IPv6 Address. . . . . . . . . . . : fd89:a0d3:1818::ccf(Preferred) 
   Lease Obtained. . . . . . . . . . : Wednesday, June 17, 2026 1:29:35 PM
   Lease Expires . . . . . . . . . . : Saturday, July 24, 2162 9:16:56 PM
   IPv6 Address. . . . . . . . . . . : fd89:a0d3:1818:0:59ea:7704:767b:b9d9(Preferred) 
   Temporary IPv6 Address. . . . . . : fd89:a0d3:1818:0:c0fd:8e0e:9214:bfbf(Preferred) 
   Link-local IPv6 Address . . . . . : fe80::989a:e421:3de8:2c5d%10(Preferred) 
   IPv4 Address. . . . . . . . . . . : 192.168.50.44(Preferred) 
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Lease Obtained. . . . . . . . . . : Wednesday, June 17, 2026 1:26:33 PM
   Lease Expires . . . . . . . . . . : Thursday, June 18, 2026 1:29:33 AM
   Default Gateway . . . . . . . . . : 192.168.50.1
   DHCP Server . . . . . . . . . . . : 192.168.50.1
   DHCPv6 IAID . . . . . . . . . . . : 222356016
   DHCPv6 Client DUID. . . . . . . . : 00-01-00-01-21-B3-B5-AD-FC-AA-14-D9-FA-9C
   DNS Servers . . . . . . . . . . . : fd89:a0d3:1818::1
                                       192.168.50.1
   NetBIOS over Tcpip. . . . . . . . : Enabled

```

### D2. Firewall profile status

```powershell
Get-NetFirewallProfile | Select-Object Name,Enabled
```

```text

Name    Enabled
----    -------
Domain    False
Private   False
Public    False



```

### D3. OpenSSH server service

```powershell
Get-Service sshd -ErrorAction SilentlyContinue | Select-Object Name,Status   # is OpenSSH server present?
```

```text
[no output returned]
```


D Conclusions:
- IPv4 address(es): 169.254.195.114, 169.254.221.201, 192.168.50.44
- Subnet mask(s): 255.255.0.0, 255.255.255.0
- Default gateway(s): 192.168.50.1
- MoCap 192.168.50.x network: present.
- Firewall profile Domain: Enabled=False
- Firewall profile Private: Enabled=False
- Firewall profile Public: Enabled=False
- OpenSSH server service not found.
- ping <LINUX_LAPTOP_IP>: skipped because Linux IP not provided.
- Can open inbound TCP port: depends on admin rights and policy (see F1).

## E. OptiTrack system state

GUI-only Motive state items:
- Camera count + model + frame rate: **requires operator GUI check**
- Calibration status/quality/date: **requires operator GUI check**
- Continuous Calibration availability/on-off: **requires operator GUI check**
- Streaming (VRPN/NatNet/Local Interface/Unicast-Multicast): **requires operator GUI check**
- Assets pane rigid-body names: **requires operator GUI check**
### E1. Saved profiles/calibration files on disk

```powershell
Get-ChildItem "$env:USERPROFILE\Documents\OptiTrack","$env:LOCALAPPDATA\OptiTrack","$env:USERPROFILE" -Recurse -ErrorAction SilentlyContinue `
  -Include *.motive,*.ttp,*.cal,*.mcal,*.tra | Select-Object FullName,LastWriteTime
```

```text

FullName                                                                                                         LastWr
                                                                                                                 iteTim
                                                                                                                 e     
--------                                                                                                         ------
C:\Users\arpg\Documents\OptiTrack\Session 2020-09-10\Calibration Exceptional (MeanErr 0.925 mm) 2020-09-10 3.cal 9/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.088 mm) 2018-04-23 9.cal                      4/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.263 mm) 2020-07-27 6.cal                      7/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.337 mm) 2020-02-28 3.cal                      2/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.441 mm) 2020-02-15 3.cal                      2/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.466 mm) 2018-01-18 11.cal                     1/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.498 mm) 2020-07-28 2.cal                      7/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.900 mm) 2019-03-21 2.cal                    3/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.921 mm) 2018-01-03 11.cal                   1/3...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.954 mm) 2019-02-19 3.cal                    2/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.988 mm) 2017-12-11 4.cal                    12/...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.018 mm) 2017-12-12 1.cal                    12/...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.068 mm) 2018-07-16 6.cal                    7/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.213 mm) 2018-01-17 3.cal                    1/1...
C:\Users\arpg\Documents\OptiTrack\CalibrationResult 2018-01-17 _poor.cal                                         1/1...
C:\Users\arpg\Documents\OptiTrack\CalibrationResult 2019-02-19 3.cal                                             2/1...
C:\Users\arpg\Documents\OptiTrack\MARBLE Gate.tra                                                                1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE Robot.tra                                                               1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE_Gate.tra                                                                1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE_Robot.tra                                                               1/5...
C:\Users\arpg\Documents\OptiTrack\ninja test.tra                                                                 6/2...
C:\Users\arpg\Desktop\programs\Calibration.cal                                                                   1/3...
C:\Users\arpg\Desktop\programs\Calibration_zeroed.cal                                                            1/3...
C:\Users\arpg\Desktop\4camera_superlit.cal                                                                       9/1...
C:\Users\arpg\Desktop\Assets - 2023-09-19 10.motive                                                              9/1...
C:\Users\arpg\Desktop\Calibration Excellent (MeanErr 0.616 mm) 2024-10-11 11.cal                                 10/...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.376 mm) 2023-09-18 4.cal                                9/1...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.379 mm) 2026-02-17 4.cal                                2/1...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.474 mm) 2023-05-24 3.cal                                5/2...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.855 mm) 2020-10-12 10.cal                               10/...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.876 mm) 2020-10-12 12.cal                               10/...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.885 mm) 2022-04-05 2.cal                                4/5...
C:\Users\arpg\Desktop\Calibration Exceptional (MeanErr 0.996 mm) 2022-04-29 3.cal                                4/2...
C:\Users\arpg\Desktop\Calibration Poor (MeanErr 5.345 mm) 2024-10-10 12.cal                                      10/...
C:\Users\arpg\Desktop\CalibrationResult 2021-01-20 12.cal                                                        1/2...
C:\Users\arpg\Desktop\mike_N02.motive                                                                            6/2...
C:\Users\arpg\Desktop\RestoreBotCalibration.cal                                                                  9/1...
C:\Users\arpg\Desktop\shoppingCartCal.cal                                                                        8/1...
C:\Users\arpg\Desktop\shoppingCartCal_BEST.cal                                                                   8/2...
C:\Users\arpg\Documents\OptiTrack\Session 2020-09-10\Calibration Exceptional (MeanErr 0.925 mm) 2020-09-10 3.cal 9/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.088 mm) 2018-04-23 9.cal                      4/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.263 mm) 2020-07-27 6.cal                      7/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.337 mm) 2020-02-28 3.cal                      2/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.441 mm) 2020-02-15 3.cal                      2/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.466 mm) 2018-01-18 11.cal                     1/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Excellent (MeanErr 1.498 mm) 2020-07-28 2.cal                      7/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.900 mm) 2019-03-21 2.cal                    3/2...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.921 mm) 2018-01-03 11.cal                   1/3...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.954 mm) 2019-02-19 3.cal                    2/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 0.988 mm) 2017-12-11 4.cal                    12/...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.018 mm) 2017-12-12 1.cal                    12/...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.068 mm) 2018-07-16 6.cal                    7/1...
C:\Users\arpg\Documents\OptiTrack\Calibration Exceptional (MeanErr 1.213 mm) 2018-01-17 3.cal                    1/1...
C:\Users\arpg\Documents\OptiTrack\CalibrationResult 2018-01-17 _poor.cal                                         1/1...
C:\Users\arpg\Documents\OptiTrack\CalibrationResult 2019-02-19 3.cal                                             2/1...
C:\Users\arpg\Documents\OptiTrack\MARBLE Gate.tra                                                                1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE Robot.tra                                                               1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE_Gate.tra                                                                1/5...
C:\Users\arpg\Documents\OptiTrack\MARBLE_Robot.tra                                                               1/5...
C:\Users\arpg\Documents\OptiTrack\ninja test.tra                                                                 6/2...



```


## F. Operating constraints

### F1. Admin rights

```powershell
[bool](([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator))
```

```text
False

```

F Prose answers:
1. Admin rights: False
   - This account is non-admin; elevation would be required for firewall/service/install tasks.
2. GUI vs headless tolerance: **requires operator decision**.
3. Shared-machine usage windows/other users: **requires operator input**.
4. Internet access for pip/downloads: **requires operator/network policy check**.

## Checklist completion

- [x] Motive version + edition + license (A)
  - Edition/license are GUI-only and require operator fill-in.
- [x] Motive API SDK present? paths + bitness — or not installed (B)
- [x] NMotive / Batch Processor present? (B)
- [ ] Python present? version + 32/64-bit + pip/internet (C)
- [ ] C++ toolchain (MSVC) present? (C)
- [x] Network: IP/subnet/gateway, net, firewall, SSH, can-open-a-port (D)
- [x] OptiTrack state: cameras/frame/calibration/streaming/assets + saved profiles (E)
  - GUI-only items marked as requires operator GUI check.
- [x] Constraints: admin rights, GUI-vs-headless, shared-machine windows, internet (F)
