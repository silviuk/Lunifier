; Inno Setup Script for Lunifier 2.1 Native
#define MyAppName "Lunifier"
#define MyAppVersion "2.2.0"
#define MyAppPublisher "silviuk"
#define MyAppURL "https://github.com/silviuk/Lunifier"
#define MyAppExeName "Lunifier.exe"

[Setup]
AppId={{6B5A137D-D980-4D5E-A430-8C846FA6A512}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (C) 2026 Silviu Vlasceanu
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright=Copyright (C) 2026 Silviu Vlasceanu
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=Lunifier-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern dynamic
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
PrivilegesRequiredOverridesAllowed=dialog commandline
DisableDirPage=auto
DisableProgramGroupPage=auto
SetupIconFile=..\src\windows\Lunifier.Windows\Resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start Lunifier automatically when Windows starts"; GroupDescription: "Windows Integration:"

[Files]
Source: "..\dist\windows\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.pdb"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--minimized"; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function IsDotNet9DesktopInstalled(): Boolean;
var
  FindRec: TFindRec;
  SharedFxPath: String;
begin
  Result := False;
  SharedFxPath := ExpandConstant('{pf64}\dotnet\shared\Microsoft.WindowsDesktop.App');
  if not DirExists(SharedFxPath) then
    SharedFxPath := ExpandConstant('{pf}\dotnet\shared\Microsoft.WindowsDesktop.App');

  if DirExists(SharedFxPath) then
  begin
    if FindFirst(SharedFxPath + '\9.0*', FindRec) then
    begin
      try
        Result := True;
      finally
        FindClose(FindRec);
      end;
    end;
  end;
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;
  if not IsDotNet9DesktopInstalled() then
  begin
    if MsgBox('Lunifier requires Microsoft .NET 9 Desktop Runtime (x64) to run properly.' + #13#10 + #13#10 +
              'Would you like to open the official Microsoft download page now?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', 'https://aka.ms/dotnet/9.0/windowsdesktop-runtime-win-x64.exe', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
    end;
  end;
end;
