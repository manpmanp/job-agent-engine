; Job-search agent engine
; File:    launchers/windows/package/jobagent.iss
; Purpose: Inno Setup script: a per-user Windows installer (no administrator rights) with Start menu and optional desktop shortcuts.
; Author:  manpmanp <manp.node@gmail.com>
; Generated with Claude (Anthropic), under the author's direction and review.
; License: MIT (see LICENSE)
; Version: 0.4.1
; Date:    2026-10-29
#ifndef AppVersion
  #define AppVersion "0.4.4"
#endif
[Setup]
AppId={{6F1C2E7A-4B8D-4C2B-9E3A-JOBAGENTENGINE}
AppName=Job Agent
AppVersion={#AppVersion}
AppPublisher=manpmanp
AppPublisherURL=https://github.com/manpmanp/job-agent-engine
DefaultDirName={localappdata}\Programs\Job Agent
DefaultGroupName=Job Agent
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\..\dist
OutputBaseFilename=JobAgent-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\..\LICENSE
UninstallDisplayName=Job Agent

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\..\dist\JobAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "READ ME FIRST.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Job Agent"; Filename: "{app}\JobAgent.exe"
Name: "{group}\Uninstall Job Agent"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Job Agent"; Filename: "{app}\JobAgent.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JobAgent.exe"; Description: "Start Job Agent now"; Flags: nowait postinstall skipifsilent
