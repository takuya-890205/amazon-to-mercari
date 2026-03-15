@echo off
chcp 65001 >nul
echo ========================================
echo   Amazon → メルカリ 出品下書き生成ツール
echo   セットアップ
echo ========================================
echo.

REM Pythonの確認
python --version >nul 2>&1
if errorlevel 1 (
    echo [エラー] Pythonがインストールされていません。
    echo https://www.python.org/downloads/ からインストールしてください。
    echo ※ インストール時に「Add Python to PATH」にチェックを入れてください。
    pause
    exit /b 1
)

echo [1/3] 仮想環境を作成中...
if not exist ".venv" (
    python -m venv .venv
    echo       仮想環境を作成しました。
) else (
    echo       仮想環境は既に存在します。
)

echo.
echo [2/3] パッケージをインストール中...
call .venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo       インストール完了。

echo.
echo [3/3] APIキーの設定...
if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo ============================================================
    echo   Gemini APIキーを設定してください。
    echo.
    echo   1. https://aistudio.google.com/apikey にアクセス
    echo   2. 「APIキーを作成」をクリック
    echo   3. 作成されたキーをコピー
    echo ============================================================
    echo.
    set /p APIKEY="APIキーを入力してください: "
    echo GEMINI_API_KEY=%APIKEY%> .env
    echo       APIキーを保存しました。
) else (
    echo       .env ファイルは既に存在します。
)

echo.
echo ========================================
echo   セットアップ完了！
echo   run.bat をダブルクリックで起動できます。
echo ========================================
pause
