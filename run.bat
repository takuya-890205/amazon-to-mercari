@echo off
chcp 65001 >nul
echo Amazon → メルカリ 出品下書き生成ツールを起動中...
echo.

if not exist ".venv" (
    echo [エラー] セットアップが完了していません。
    echo 先に setup.bat を実行してください。
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
streamlit run app.py --server.headless true
pause
