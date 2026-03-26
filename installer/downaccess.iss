[Setup]
AppName=DownAccess
AppVersion=0.1.6
AppPublisher=math65
AppPublisherURL=https://github.com/math65/downaccess
AppSupportURL=https://github.com/math65/downaccess/issues
AppUpdatesURL=https://github.com/math65/downaccess/releases
DefaultDirName={autopf}\DownAccess
DefaultGroupName=DownAccess
AllowNoIcons=yes
OutputDir=..\installer_output
OutputBaseFilename=DownAccess-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\DownAccess.exe
; ShowLanguageDialog=no
; Pour l'icône : décommenter quand assets/icon.ico sera créé
; SetupIconFile=..\assets\icon.ico

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis supplémentaires :"; Flags: unchecked
Name: "startmenuicon"; Description: "Créer un raccourci dans le menu Démarrer"; GroupDescription: "Raccourcis supplémentaires :"; Flags: checkedonce

[Files]
; Application principale
Source: "..\dist\DownAccess\DownAccess.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\DownAccess\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DownAccess"; Filename: "{app}\DownAccess.exe"; Comment: "Téléchargeur vidéo/audio accessible NVDA"
Name: "{group}\Désinstaller DownAccess"; Filename: "{uninstallexe}"
Name: "{userdesktop}\DownAccess"; Filename: "{app}\DownAccess.exe"; Comment: "Téléchargeur vidéo/audio accessible NVDA"; Tasks: desktopicon

[Run]
Filename: "{app}\DownAccess.exe"; Description: "Lancer DownAccess"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Supprimer les fichiers créés au runtime (cache yt-dlp, logs…)
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
