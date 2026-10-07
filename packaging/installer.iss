#define AppName "EasyThing"
#define AppVersion "0.1.0"

[Setup]
AppId={{C50E3B70-13BB-44D9-909F-532370EB7DA5}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=EasyThing contributors
AppPublisherURL=https://github.com/gengyixiong/easything
DefaultDirName={localappdata}\Programs\EasyThing
DefaultGroupName=EasyThing
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=EasyThing-Setup
Compression=lzma2/fast
SolidCompression=yes
LicenseFile=..\LICENSE
WizardStyle=modern
UninstallDisplayName=EasyThing
UninstallDisplayIcon={app}\EasyThing.exe
CloseApplications=yes
RestartApplications=no
AppMutex=Local\EasyThingDesktop

[Files]
Source: "..\build\frozen\EasyThing\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EasyThing"; Filename: "{app}\EasyThing.exe"
Name: "{group}\Uninstall EasyThing"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\EasyThing.exe"; Description: "Open EasyThing"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "EasyThing"; Flags: uninsdeletevalue

[Code]
var
  DeleteModel, DeleteIndex, DeleteSettings: Boolean;

function HasParameter(Value: String): Boolean;
var I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Value) = 0 then Result := True;
end;

function InitializeUninstall(): Boolean;
var
  Form: TSetupForm;
  LabelText: TNewStaticText;
  ModelBox, IndexBox, SettingsBox: TNewCheckBox;
  RemoveButton, CancelButton: TNewButton;
begin
  Result := False;
  if CheckForMutexes('Local\EasyThingDesktop') then begin
    if not UninstallSilent then
      MsgBox('Please exit EasyThing from its system tray menu before uninstalling.', mbInformation, MB_OK);
    Exit;
  end;
  DeleteModel := HasParameter('/DELETEMODEL');
  DeleteIndex := HasParameter('/DELETEINDEX');
  DeleteSettings := HasParameter('/DELETESETTINGS');
  if UninstallSilent then begin Result := True; Exit; end;
  Form := CreateCustomForm(ScaleX(480), ScaleY(260), False, False);
  try
    Form.Caption := 'Uninstall EasyThing';
    LabelText := TNewStaticText.Create(Form);
    LabelText.Parent := Form;
    LabelText.SetBounds(ScaleX(20), ScaleY(16), ScaleX(440), ScaleY(48));
    LabelText.AutoSize := False;
    LabelText.WordWrap := True;
    LabelText.Caption := 'Remove application: yes' + #13#10 + 'Original documents and photos will never be deleted.';
    ModelBox := TNewCheckBox.Create(Form);
    ModelBox.Parent := Form;
    ModelBox.SetBounds(ScaleX(20), ScaleY(80), ScaleX(440), ScaleY(24));
    ModelBox.Caption := 'Delete downloaded EmbeddingGemma 2 model';
    ModelBox.Checked := False;
    IndexBox := TNewCheckBox.Create(Form);
    IndexBox.Parent := Form;
    IndexBox.SetBounds(ScaleX(20), ScaleY(116), ScaleX(440), ScaleY(24));
    IndexBox.Caption := 'Delete local search index';
    IndexBox.Checked := False;
    SettingsBox := TNewCheckBox.Create(Form);
    SettingsBox.Parent := Form;
    SettingsBox.SetBounds(ScaleX(20), ScaleY(152), ScaleX(440), ScaleY(24));
    SettingsBox.Caption := 'Delete settings and cache';
    SettingsBox.Checked := False;
    RemoveButton := TNewButton.Create(Form);
    RemoveButton.Parent := Form;
    RemoveButton.SetBounds(ScaleX(270), ScaleY(210), ScaleX(90), ScaleY(28));
    RemoveButton.Caption := 'Uninstall';
    RemoveButton.ModalResult := mrOk;
    RemoveButton.Default := True;
    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.SetBounds(ScaleX(370), ScaleY(210), ScaleX(90), ScaleY(28));
    CancelButton.Caption := 'Cancel';
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;
    Result := Form.ShowModal() = mrOk;
    if Result then begin
      DeleteModel := ModelBox.Checked;
      DeleteIndex := IndexBox.Checked;
      DeleteSettings := SettingsBox.Checked;
    end;
  finally
    Form.Free();
  end;
end;

function GetFileAttributes(FileName: String): LongWord;
external 'GetFileAttributesW@kernel32.dll stdcall';

procedure DeleteOwnedTree(Directory: String);
var FindRec: TFindRec; Child: String;
begin
  if not DirExists(Directory) then Exit;
  { Never follow junctions/symlinks, even if a user has placed one in app data. }
  if (GetFileAttributes(Directory) and $400) <> 0 then begin
    Log('Cleanup skipped a reparse point: ' + Directory);
    Exit;
  end;
  if FindFirst(Directory + '\*', FindRec) then begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
          Child := Directory + '\' + FindRec.Name;
          if (FindRec.Attributes and $400) = 0 then begin
            if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
              DeleteOwnedTree(Child)
            else DeleteFile(Child);
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  RemoveDir(Directory);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var DataRoot: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    DataRoot := ExpandConstant('{localappdata}\EasyThing');
    if (GetFileAttributes(DataRoot) and $400) <> 0 then Exit;
    if DeleteModel then DeleteOwnedTree(DataRoot + '\models');
    if DeleteIndex then DeleteOwnedTree(DataRoot + '\index');
    if DeleteSettings then begin
      DeleteOwnedTree(DataRoot + '\settings');
      DeleteOwnedTree(DataRoot + '\cache');
    end;
  end;
end;
