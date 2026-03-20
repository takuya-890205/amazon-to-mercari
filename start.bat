@echo off
chcp 65001 >nul
title Amazon → メルカリ 出品下書き生成ツール

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  Amazon → メルカリ 出品下書き生成ツール  ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM === Python確認・自動インストール ===
python --version >nul 2>&1
if errorlevel 1 (
    echo  Pythonが見つかりません。自動インストールを開始します...
    echo.

    REM wingetが使えるか確認
    winget --version >nul 2>&1
    if not errorlevel 1 (
        echo  winget で Python をインストールしています...
        echo  （許可を求められたら「はい」を選んでください）
        echo.
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        if not errorlevel 1 (
            set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
            goto :python_check
        )
    )

    REM wingetが使えない or 失敗 → インストーラーを自動ダウンロード
    echo  Pythonインストーラーをダウンロードしています...
    set "PYTHON_INSTALLER=%TEMP%\python_installer.exe"
    curl -L -o "%PYTHON_INSTALLER%" https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe 2>nul
    if not exist "%PYTHON_INSTALLER%" (
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%PYTHON_INSTALLER%'" 2>nul
    )

    if not exist "%PYTHON_INSTALLER%" (
        echo.
        echo  [エラー] ダウンロードに失敗しました。
        echo  https://www.python.org/downloads/ から手動でインストールしてください。
        echo  ※「Add Python to PATH」にチェックを入れてください
        pause
        exit /b 1
    )

    echo  Pythonをインストールしています...
    echo  （少々お待ちください）
    "%PYTHON_INSTALLER%" /quiet PrependPath=1 Include_pip=1
    del "%PYTHON_INSTALLER%" 2>nul

    REM PATHを即時反映
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

:python_check
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  Pythonのインストールが完了しました。
        echo  PATHを反映するため、このファイルをもう一度ダブルクリックしてください。
        pause
        exit /b 0
    )
    echo  Pythonのインストールが完了しました。
    echo.
)

REM === 初回セットアップ ===
if not exist ".venv" (
    echo  [初回セットアップ] 準備中です。少々お待ちください...
    echo.

    echo  [1/3] 仮想環境を作成中...
    python -m venv .venv
    if errorlevel 1 (
        echo  [エラー] 仮想環境の作成に失敗しました。
        pause
        exit /b 1
    )
    echo        完了
    echo.

    echo  [2/3] 必要なパッケージをインストール中...
    echo        （初回は数分かかることがあります）
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet 2>nul
    if errorlevel 1 (
        pip install -r requirements.txt
    )
    echo        完了
    echo.

    echo  [3/3] Playwright（ブラウザ自動操作）をインストール中...
    pip install playwright --quiet 2>nul
    playwright install chromium --with-deps 2>nul
    echo        完了
    echo.

    echo  ========================================
    echo   初回セットアップ完了！
    echo  ========================================
    echo.
)

REM === アプリ起動 ===
call .venv\Scripts\activate.bat

echo  アプリを起動しています...
echo  ブラウザが自動で開きます。
echo.
echo  ※ 終了するにはこのウィンドウを閉じてください
echo.

start http://localhost:8501
streamlit run app.py --server.headless true --browser.gatherUsageStats false 2>nul
pause
