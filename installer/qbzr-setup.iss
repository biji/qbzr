; Script initially generated by the Inno Setup Script Wizard
; and then modified by Alexander Belchenko.

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId=QBzr

AppName=                 QBzr
AppVerName=              QBzr 0.23.2
OutputBaseFilename=qbzr-setup-0.23.2

SourceDir="..\"
OutputDir="."
OutputManifestFile=qbzr-setup-iss.log

AppPublisher=QBzr Developers
AppPublisherURL=http://launchpad.net/qbzr
AppSupportURL=http://groups.google.com/group/qbzr
AppUpdatesURL=http://launchpad.net/qbzr/+download

DefaultDirName={code:GetDirName}

DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "basque"; MessagesFile: "compiler:Languages\Basque.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "danish"; MessagesFile: "compiler:Languages\Danish.isl"
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "finnish"; MessagesFile: "compiler:Languages\Finnish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "norwegian"; MessagesFile: "compiler:Languages\Norwegian.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "slovak"; MessagesFile: "compiler:Languages\Slovak.isl"
Name: "slovenian"; MessagesFile: "compiler:Languages\Slovenian.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "__init__.py"; DestDir: {app};
Source: "lib\*.py"; DestDir: {app}\lib; Flags: recursesubdirs;
Source: "*.txt"; DestDir: {app};
Source: "locale\*.*";  DestDir: {app}\locale; Flags: recursesubdirs;

[UninstallDelete]
; TODO: create special uninstall function in Code section to recursively delete pyc/pyo files
;       using FindFile API
Type: files; Name: {app}\*.pyc
Type: files; Name: {app}\lib\*.pyc
Type: files; Name: {app}\lib\extra\*.pyc
Type: files; Name: {app}\lib\tests\*.pyc
Type: files; Name: {app}\lib\widgets\*.pyc

Type: files; Name: {app}\*.pyo
Type: files; Name: {app}\lib\*.pyo
Type: files; Name: {app}\lib\extra\*.pyo
Type: files; Name: {app}\lib\tests\*.pyo
Type: files; Name: {app}\lib\widgets\*.pyo

[Registry]
Root: HKLM; Subkey: "Software\QBzr"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\QBzr"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"

[Code]
{Function detects system-wide installation of bzr: either bzr.exe or python-based}
function GetBzrPath(): String;
var
  BzrPath: String;
  PythonVersions: TArrayOfString;
  Ix: Integer;
  PythonKey: String;
  PythonPath: String;
  BzrlibPath: String;
  Path: String;
begin
  {Check bzr.exe presence}
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'Software\Bazaar', 'InstallPath', BzrPath) then begin
    Result := BzrPath;
  end else begin
    BzrlibPath := '';
    {Get list of all installed python versions}
    if RegGetSubkeyNames(HKEY_LOCAL_MACHINE, 'Software\Python\PythonCore', PythonVersions) then begin
      {Iterate over installed pythons and check if there is installed bzrlib}
      for Ix := 0 to GetArrayLength(PythonVersions)-1 do begin
        PythonKey := 'Software\Python\PythonCore\' + PythonVersions[Ix] + '\InstallPath'
        if RegQueryStringValue(HKEY_LOCAL_MACHINE, PythonKey, '', PythonPath) then begin
          Path := AddBackslash(PythonPath) + 'Lib\site-packages\bzrlib'
          if DirExists(Path) then begin
            BzrlibPath := Path;
            break;
          end;
        end;
      end;
    end;
    Result := BzrlibPath;
  end;
end;

{Function determines best possible PATH to install QBzr.
  At first it tries to find system-wide installation (either bzr.exe or python-based)
  then checks BZR_PLUGIN_PATH,
  if all above fails then it suggests install to %APPDATA%\bazaar\2.0
}
function GetDirName(Param: String): String;
var
  Path: String;
  BzrPath: String;
  EnvBzrPluginPath: String;
  Ix: Integer;
begin
  Path := ExpandConstant('{userappdata}\bazaar\2.0\plugins\qbzr');
  BzrPath := GetBzrPath();
  if BzrPath <> '' then begin
     Path := AddBackslash(BzrPath) + 'plugins\qbzr';
  end else begin
      EnvBzrPluginPath := GetEnv('BZR_PLUGIN_PATH')
      Ix := Pos(';', EnvBzrPluginPath)
      if Ix > 0 then
        EnvBzrPluginPath := Copy(EnvBzrPluginPath, 1, Ix-1)
      if EnvBzrPluginPath <> '' then
        Path := AddBackslash(EnvBzrPluginPath) + 'qbzr';
  end;
  Result := Path;
end;
