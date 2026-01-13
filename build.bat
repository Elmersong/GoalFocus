@echo off
setlocal enabledelayedexpansion

echo [1/3] 清理旧的打包产物
echo --------------------------------------------
if exist dist (
    echo 删除 dist...
    rmdir /s /q dist
)
if exist build (
    echo 删除 build...
    rmdir /s /q build
)
if exist GoalFocus.spec (
    echo 删除 GoalFocus.spec ...
    del /f /q GoalFocus.spec
)
if exist main.spec (
    echo 删除 main.spec ...
    del /f /q main.spec
)
echo 清理完成。
echo.

echo [2/3] 使用 PyInstaller 生成單文件 EXE
echo --------------------------------------------
python -m PyInstaller --onefile --name=GoalFocus --icon=logo.ico --noconsole main.py
if errorlevel 1 (
    echo.
    echo [錯誤] PyInstaller 打包失敗，請查看上方錯誤訊息。
    pause
    exit /b 1
)
echo PyInstaller 打包完成。
echo.

echo [3/3] 使用 Inno Setup 生成安裝包
echo --------------------------------------------

REM ★★★ 在這裡填上你機器上 ISCC.exe 的完整路徑 ★★★
SET "ISCC_EXE=E:\practice\Inno Setup 6\ISCC.exe"

if not exist "%ISCC_EXE%" (
    echo [錯誤] 找不到 ISCC.exe:
    echo   %ISCC_EXE%
    echo 請確認路徑是否正確，必要時修改 build.bat 中的 ISCC_EXE。
    pause
    exit /b 1
)

"%ISCC_EXE%" GoalFocus.iss
