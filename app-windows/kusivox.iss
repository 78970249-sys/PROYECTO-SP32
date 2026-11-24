; Instalador de KusiVox para Windows (Inno Setup 6)
#define MyAppName "KusiVox"
#define MyAppVersion "1.0.0"

[Setup]
AppId={{B6E2C1A4-6F1B-4C1E-9F3A-2D5E8A7C4B10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Proyecto KusiVox - Universidad Continental
AppPublisherURL=https://78970249-sys.github.io/PROYECTO-SP32/
DefaultDirName={autopf}\KusiVox
DefaultGroupName=KusiVox
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=KusiVox-Setup
SetupIconFile=kusivox.ico
UninstallDisplayIcon={app}\KusiVox.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\KusiVox.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\KusiVoxServidor.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\KusiVox"; Filename: "{app}\KusiVox.exe"
Name: "{group}\Desinstalar KusiVox"; Filename: "{uninstallexe}"
Name: "{autodesktop}\KusiVox"; Filename: "{app}\KusiVox.exe"; Tasks: desktopicon

[Registry]
; Al desinstalar, quita el inicio con Windows si estaba activado
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "KusiVox"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\KusiVox.exe"; Description: "{cm:LaunchProgram,KusiVox}"; Flags: nowait postinstall skipifsilent
