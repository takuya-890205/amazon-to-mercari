@echo off
chcp 65001 >nul
echo ========================================
echo   exe ビルドスクリプト
echo ========================================
echo.

cd /d "%~dp0"

if not exist ".venv" (
    echo [エラー] 先に start.bat を実行してセットアップを完了してください。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

echo [1/2] PyInstallerをインストール中...
pip install pyinstaller --quiet

echo [2/2] exeをビルド中...
pyinstaller --onefile --windowed --name "メルカリ出品ツール" --icon=NONE launcher.py

echo.
if exist "dist\メルカリ出品ツール.exe" (
    echo ========================================
    echo   ビルド完了！
    echo   dist\メルカリ出品ツール.exe
    echo ========================================
    echo.
    echo   配布方法:
    echo   1. dist\メルカリ出品ツール.exe をコピー
    echo   2. プロジェクトフォルダに配置
    echo   3. ダブルクリックで起動
    echo.
    echo   ※ .venv フォルダが必要です
) else (
    echo [エラー] ビルドに失敗しました。
)
pause
