#define MyAppName "SanBenedettoPOS"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Festa di Paese"
#define MyAppExeName "SanBenedettoPOS.exe"
#define SetupIcon "img\icona.ico"

[Setup]
AppId={{D97BC1EA-6FD0-4A3A-B0C3-E6CE347B0CE4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist\installer
OutputBaseFilename=SanBenedettoPOS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
#if FileExists(SetupIcon)
SetupIconFile={#SetupIcon}
#endif

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; GroupDescription: "Icone aggiuntive:"; Flags: unchecked

[Files]
Source: "dist\SanBenedettoPOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\storico"
Name: "{app}\logs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia {#MyAppName}"; Flags: nowait postinstall skipifsilent