; LoL Voice Assistant Installer
; Inno Setup Script

#define MyAppName "LoL Voice Assistant"
#define MyAppVersion "Alpha 0.1"
#define MyAppPublisher "LoL Voice Assistant"
#define MyAppExeName "LoLVoiceAssistant.exe"

[Setup]
AppId={{B5E2D8A1-7C3F-4E9B-A1D2-8F5E6C7B9A0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=LoLVoiceAssistant_Setup_v{#MyAppVersion}
SetupIconFile=assets\favicon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\LoLVoiceAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch LoL Voice Assistant"; Flags: nowait postinstall skipifsilent

[Code]
procedure InitializeConfig();
var
  ConfigDir: String;
  ConfigFile: String;
begin
  ConfigDir := ExpandConstant('{userappdata}\LoLVoiceAssistant');
  ConfigFile := ConfigDir + '\config.json';
  
  if not DirExists(ConfigDir) then
    CreateDir(ConfigDir);
  
  if not FileExists(ConfigFile) then
  begin
    SaveStringToFile(ConfigFile, 
      '{' + #13#10 +
      '  "language": "pl_PL",' + #13#10 +
      '  "ui_language": "en_US",' + #13#10 +
      '  "recognition_mode": "letters",' + #13#10 +
      '  "spell_sensitivity": "medium",' + #13#10 +
      '  "flash_key": "D"' + #13#10 +
      '}', False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    InitializeConfig();
end;