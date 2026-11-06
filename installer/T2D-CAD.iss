; T2D-CAD Windows installer (Inno Setup 6). Built by the GitHub Actions workflow:
;   iscc /DAppVersion=0.6.0 installer\T2D-CAD.iss
; Installs for the current user (no administrator rights needed), creates the
; desktop and Start menu shortcuts and an uninstaller.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1F3D2E-7B8A-4E55-9C3D-2D0A7F1B5E41}
AppName=T2D-CAD
AppVersion={#AppVersion}
AppVerName=T2D-CAD {#AppVersion}
AppPublisher=TDD Technic
DefaultDirName={autopf}\T2D-CAD
DefaultGroupName=T2D-CAD
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=T2D-CAD-Kurulum-{#AppVersion}
SetupIconFile=..\assets\t2dcad.ico
UninstallDisplayIcon={app}\T2D-CAD.exe
UninstallDisplayName=T2D-CAD
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.AssocTask=.dwg ve .dxf dosyalarını T2D-CAD ile aç
english.AssocTask=Open .dwg and .dxf files with T2D-CAD
turkish.OtherTasks=Diğer seçenekler:
english.OtherTasks=Other options:

[Tasks]
Name: "assoc"; Description: "{cm:AssocTask}"; GroupDescription: "{cm:OtherTasks}"; Flags: unchecked

[Files]
Source: "..\dist\T2D-CAD\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\T2D-CAD"; Filename: "{app}\T2D-CAD.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\T2D-CAD"; Filename: "{app}\T2D-CAD.exe"; WorkingDir: "{app}"
Name: "{autoprograms}\T2D-CAD kaldır"; Filename: "{uninstallexe}"

[Registry]
Root: HKA; Subkey: "Software\Classes\T2DCAD.Drawing"; ValueType: string; ValueData: "T2D-CAD çizimi"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\T2DCAD.Drawing\DefaultIcon"; ValueType: string; ValueData: "{app}\T2D-CAD.exe,0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\T2DCAD.Drawing\shell\open\command"; ValueType: string; ValueData: """{app}\T2D-CAD.exe"" ""%1"""; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.dwg\OpenWithProgids"; ValueType: string; ValueName: "T2DCAD.Drawing"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.dxf\OpenWithProgids"; ValueType: string; ValueName: "T2DCAD.Drawing"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.dwg"; ValueType: string; ValueName: ""; ValueData: "T2DCAD.Drawing"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\.dxf"; ValueType: string; ValueName: ""; ValueData: "T2DCAD.Drawing"; Flags: uninsdeletevalue; Tasks: assoc

[Run]
Filename: "{app}\T2D-CAD.exe"; Description: "{cm:LaunchProgram,T2D-CAD}"; Flags: nowait postinstall skipifsilent
