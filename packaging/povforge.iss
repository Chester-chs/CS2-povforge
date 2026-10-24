; Inno Setup script for the PovForge installer (https://jrsoftware.org/isinfo.php).
; Built by .github/workflows/windows-app.yml:
;   iscc /DAppVersion=0.16.3 packaging\povforge.iss
; Installs for the current user only (no admin rights), adds a desktop icon and
; a Start menu entry, and registers an uninstaller.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E0B5A4C-2F1E-4C7B-9C64-6A1D2C9F7B11}
AppName=PovForge
AppVersion={#AppVersion}
AppVerName=PovForge {#AppVersion}
AppPublisher=PovForge (personal, non-commercial)
AppPublisherURL=https://github.com/Chester-chs/CS2-povforge
AppSupportURL=https://github.com/Chester-chs/CS2-povforge/issues
AppUpdatesURL=https://github.com/Chester-chs/CS2-povforge/releases/latest
DefaultDirName={localappdata}\Programs\PovForge
DefaultGroupName=PovForge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=PovForge-Setup
SetupIconFile=povforge.ico
UninstallDisplayIcon={app}\PovForge.exe
UninstallDisplayName=PovForge
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.LaunchApp=打开 PovForge
english.LaunchApp=Open PovForge
chinesesimplified.DesktopIcon=在桌面上创建 PovForge 图标
english.DesktopIcon=Put a PovForge icon on the desktop

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"

[Files]
Source: "dist\PovForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallDelete]
; files put in by an in-app update aren't in the installer's list: remove the whole folder
Type: filesandordirs; Name: "{app}"

[InstallDelete]
; files from an older version that the new one no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autodesktop}\PovForge"; Filename: "{app}\PovForge.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{autoprograms}\PovForge"; Filename: "{app}\PovForge.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\PovForge.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
; in-app update: the app runs this installer with /SILENT /update=1 and quits;
; open the new version when the install is done
Filename: "{app}\PovForge.exe"; Flags: nowait; Check: IsAppUpdate

[Code]
function IsAppUpdate: Boolean;
begin
  Result := ExpandConstant('{param:update|0}') = '1';
end;
