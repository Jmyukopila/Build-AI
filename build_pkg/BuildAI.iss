; Instalador de BuildAI (Inno Setup). Compilar con:
;   "C:\Users\Usuario\AppData\Local\Programs\Inno Setup 6\ISCC.exe" build_pkg\BuildAI.iss
; Requiere que antes exista build_pkg\dist\BuildAI\BuildAI.exe (ver build_pkg\buildai.spec).

#define MyAppName "BuildAI"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "BuildAI"
#define MyAppExeName "BuildAI.exe"
#define MyDistDir "dist\BuildAI"

[Setup]
; GUID fijo: identifica la app entre versiones para que "Instalar" sobre una
; versión anterior actualice en el mismo sitio en vez de duplicar la entrada.
AppId={{6F275C1E-6E6A-4C0B-9C63-9A6B8B9F0B41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
; Sin privilegios de administrador: se instala en el perfil del usuario,
; como VS Code, y no pide UAC.
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=BuildAI-Setup
SetupIconFile=..\buildai\ui\assets\buildai.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} ahora"; Flags: nowait postinstall skipifsilent
