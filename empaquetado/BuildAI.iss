; Instalador de BuildAI (Inno Setup). Compilar con:
;   "C:\Users\Usuario\AppData\Local\Programs\Inno Setup 6\ISCC.exe" empaquetado\BuildAI.iss
; Requiere que antes exista empaquetado\dist\BuildAI\BuildAI.exe (ver empaquetado\buildai.spec).

#define MyAppName "BuildAI"
#define MyAppVersion "0.6.1"
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

[Code]
// IA incluida: el modelo (2,7 GB) se descarga DURANTE la instalación, para que
// BuildAI funcione al abrirlo sin que el usuario haga nada. Va a la carpeta de
// datos del usuario (%USERPROFILE%\.buildai\ia_local\modelos), la misma que
// lee buildai\ia_local.py. URL y SHA-256 fijados allí: cambiarlos a la vez.
// Si la descarga falla o se cancela, la instalación sigue: BuildAI la retoma
// solo al arrancar (y reanuda donde quedó).
const
  ModeloArchivo = 'Qwen3.5-4B-Q4_K_M.gguf';
  ModeloUrl = 'https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf';
  ModeloSha256 = '00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4';

var
  PaginaDescarga: TDownloadWizardPage;

function CarpetaModelos: String;
begin
  Result := ExpandConstant('{%USERPROFILE}\.buildai\ia_local\modelos');
end;

function AlDescargar(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  PaginaDescarga := CreateDownloadPage('Preparando la IA incluida',
    'Descargando el modelo de IA gratuito (2,7 GB, solo esta vez). Puedes cancelar: BuildAI lo terminará al abrirse.',
    @AlDescargar);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and not FileExists(CarpetaModelos + '\' + ModeloArchivo) then
  begin
    PaginaDescarga.Clear;
    PaginaDescarga.Add(ModeloUrl, ModeloArchivo, ModeloSha256);
    PaginaDescarga.Show;
    try
      try
        PaginaDescarga.Download;
      except
        Log('Descarga del modelo omitida: ' + GetExceptionMessage);
      end;
    finally
      PaginaDescarga.Hide;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Temporal, Destino: String;
begin
  if CurStep = ssPostInstall then
  begin
    Temporal := ExpandConstant('{tmp}\' + ModeloArchivo);
    Destino := CarpetaModelos + '\' + ModeloArchivo;
    if FileExists(Temporal) and not FileExists(Destino) then
    begin
      ForceDirectories(CarpetaModelos);
      // Mover (instantáneo en el mismo disco) y, si no se puede, copiar.
      if not RenameFile(Temporal, Destino) then
        FileCopy(Temporal, Destino, False);
    end;
  end;
end;
