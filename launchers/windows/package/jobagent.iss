; Job-search agent engine
; File:    launchers/windows/package/jobagent.iss
; Purpose: Inno Setup script: a per-user Windows installer (no administrator rights) with Start menu and optional desktop shortcuts.
; Author:  manpmanp <manp.node@gmail.com>
; Generated with Claude (Anthropic), under the author's direction and review.
; License: MIT (see LICENSE)
; Version: 0.4.1
; Date:    2026-10-29
#ifndef AppVersion
  #define AppVersion "0.4.7"
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
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\..\dist\JobAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "READ ME FIRST.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Job Agent"; Filename: "{app}\JobAgent.exe"
Name: "{group}\Update Job Agent"; Filename: "{app}\JobAgent.exe"; Parameters: "--page update"
Name: "{group}\Uninstall Job Agent"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Job Agent"; Filename: "{app}\JobAgent.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JobAgent.exe"; Description: "Start Job Agent now"; Flags: nowait postinstall skipifsilent
; after an update from the app (a silent install), start the new version
Filename: "{app}\JobAgent.exe"; Flags: nowait; Check: WizardSilent

[UninstallRun]
; daily run, settings file and (if you say yes) your job-search folder; the uninstaller removes the program files
Filename: "{app}\JobAgent.exe"; Parameters: "--cli uninstall --yes --keep-app {code:DataFlag}"; Flags: runhidden waituntilterminated; RunOnceId: "JobAgentCleanup"

[Code]
var
  RemoveData: Boolean;

function InitializeUninstall(): Boolean;
begin
  RemoveData := SuppressibleMsgBox('Also delete your job-search folder (postings, CVs, letters and documents)?' + #13#10 +
    'Choose No to keep it.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
  Result := True;
end;

function DataFlag(Param: String): String;
begin
  if RemoveData then Result := '--remove-data' else Result := '';
end;
