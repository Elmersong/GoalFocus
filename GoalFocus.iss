; ================================
; GoalFocus 安装包脚本（保存为 GoalFocus.iss）
; ================================

#define MyAppName "GoalFocus"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "Elmer"
#define MyAppExeName "GoalFocus.exe"

[Setup]
; 唯一 ID，保持不变即可
AppId={{87E8D5E3-4A5E-4D37-9D1B-8D6E3C9A1234}}

; 应用基本信息
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; 默认安装目录（Program Files\GoalFocus）
DefaultDirName={autopf}\{#MyAppName}

; 开始菜单文件夹名
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 输出安装包的位置和名称
OutputDir=.\Output
OutputBaseFilename=GoalFocusSetup

; 安装程序图标（使用项目根目录下的 logo.ico）
SetupIconFile=logo.ico

; 64 位系统安装到 64 位 Program Files
ArchitecturesInstallIn64BitMode=x64

; 压缩设置
Compression=lzma
SolidCompression=yes

WizardStyle=modern

; 语言（目前先只用英文，最稳定）
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 可选：是否创建桌面图标
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: unchecked

[Files]
; 主程序（注意这里用的是 dist\GoalFocus.exe）
Source: ".\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; 资源文件：动效、音效、奖杯图片
Source: ".\success.gif"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\sound.mp3";  DestDir: "{app}"; Flags: ignoreversion
Source: ".\pic.png";    DestDir: "{app}"; Flags: ignoreversion

; 图标文件也一起放到安装目录，方便快捷方式使用
Source: ".\logo.ico";   DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单快捷方式
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"

; 桌面快捷方式（绑定上面 Tasks: desktopicon）
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
; 安装完成后，给用户一个“立即运行”的勾选
Filename: "{app}\{#MyAppExeName}"; Description: "运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent
