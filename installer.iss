; LoL Voice Controller installer.
;
; Per user install, no elevation, nothing written outside the user profile.
; Compile with:
;   iscc /DMyAppVersion=1.2.3 /Odist\installer /FLoLVoiceSetup installer.iss
; or through build.py --installer-only, which passes the same arguments.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

#define MyAppName "LoL Voice Controller"
#define MyAppShortName "LoLVoice"
#define MyAppPublisher "Axword"
#define MyAppURL "https://github.com/Axword/voice-recognition-lol"
#define MyAppExeName "LoLVoice.exe"
#define MySourceDir "dist\LoLVoice"

[Setup]
; Stable identity, do not change between releases. Matches APP_ID in build_config.py.
AppId={{9F1D2C4E-6B78-4A31-9E5C-0D3A7F8B2E14}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Per user install. No administrator rights, no UAC prompt.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={localappdata}\Programs\{#MyAppShortName}
UsePreviousAppDir=yes
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
AllowNoIcons=yes

; Entry in Apps and features
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
; Rough footprint in KB, keeps the size column in Apps and features honest.
UninstallFilesDir={app}\uninstall

OutputDir=dist\installer
OutputBaseFilename=LoLVoiceSetup
SetupIconFile=assets\installer_icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Close a running instance before replacing files. The mutex name matches
; server/single_instance.py, so an in app update does not need a reboot.
AppMutex=Global\LoLVoiceSingleInstance
CloseApplications=yes
RestartApplications=no
SetupMutex=LoLVoiceSetupMutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"

[CustomMessages]
english.LaunchApp=Start {#MyAppName}
english.LogsShortcut=LoL Voice logs
english.RemoveData=Remove your settings and logs as well?%n%nChoose No to keep them for a future install.
english.RemoveModels=Remove downloaded speech models as well?%n%nThey can be several hundred megabytes and would need downloading again.
polish.LaunchApp=Uruchom {#MyAppName}
polish.LogsShortcut=Logi LoL Voice
polish.RemoveData=Usunac takze ustawienia i logi?%n%nWybierz Nie, aby zachowac je na przyszla instalacje.
polish.RemoveModels=Usunac takze pobrane modele mowy?%n%nMoga zajmowac kilkaset megabajtow i trzeba bedzie pobrac je ponownie.

[Tasks]
; Unchecked by default, the tray icon is the primary entry point.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "Voice control for League of Legends"
; Direct route to the logs, works even when the application does not start.
Name: "{autoprograms}\{cm:LogsShortcut}"; Filename: "{localappdata}\LoLVoice\logs"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; No skipifsilent: a silent update from the in app updater relaunches the
; application once the files are replaced.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall

[Code]
function LogsDir(): String;
begin
  Result := ExpandConstant('{localappdata}\LoLVoice\logs');
end;

procedure CreateUserDirs();
begin
  ForceDirectories(ExpandConstant('{localappdata}\LoLVoice'));
  ForceDirectories(LogsDir());
  ForceDirectories(ExpandConstant('{localappdata}\LoLVoice\cache'));
  ForceDirectories(ExpandConstant('{localappdata}\LoLVoice\models'));
  ForceDirectories(ExpandConstant('{userappdata}\LoLVoice'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { The log shortcut must point at a folder that exists, otherwise the shell
    resolves it to something unhelpful. The application writes the files. }
  if CurStep = ssPostInstall then
    CreateUserDirs();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ModelsDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  { Autostart entry, the only registry key the application owns. }
  RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'LoLVoice');

  ModelsDir := ExpandConstant('{localappdata}\LoLVoice\models');

  if not UninstallSilent() then
  begin
    if MsgBox(ExpandConstant('{cm:RemoveModels}'), mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ModelsDir, True, True, True);

    if MsgBox(ExpandConstant('{cm:RemoveData}'), mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\LoLVoice'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\LoLVoice\logs'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\LoLVoice\cache'), True, True, True);
      DeleteFile(ExpandConstant('{localappdata}\LoLVoice\runtime.json'));
      RemoveDir(ExpandConstant('{localappdata}\LoLVoice'));
    end;
  end;
end;
