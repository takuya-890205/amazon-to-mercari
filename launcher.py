"""exe用ランチャー: Streamlitアプリをサブプロセスとして起動しブラウザを開く"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path


def get_app_dir():
	"""exeまたはスクリプトのあるディレクトリを返す"""
	if getattr(sys, "frozen", False):
		# PyInstallerでビルドされたexe
		return Path(sys.executable).parent
	return Path(__file__).parent


def main():
	app_dir = get_app_dir()
	app_py = app_dir / "app.py"
	port = 8501

	# 仮想環境のPythonを探す
	venv_python = app_dir / ".venv" / "Scripts" / "python.exe"
	if not venv_python.exists():
		venv_python = app_dir / ".venv" / "bin" / "python"
	if not venv_python.exists():
		# venvがなければシステムPython
		venv_python = sys.executable

	# Streamlitのパスを探す
	venv_streamlit = app_dir / ".venv" / "Scripts" / "streamlit.exe"
	if not venv_streamlit.exists():
		venv_streamlit = app_dir / ".venv" / "bin" / "streamlit"

	if venv_streamlit.exists():
		cmd = [
			str(venv_streamlit), "run", str(app_py),
			"--server.headless", "true",
			"--server.port", str(port),
			"--browser.gatherUsageStats", "false",
		]
	else:
		cmd = [
			str(venv_python), "-m", "streamlit", "run", str(app_py),
			"--server.headless", "true",
			"--server.port", str(port),
			"--browser.gatherUsageStats", "false",
		]

	# Streamlitをバックグラウンドで起動
	env = os.environ.copy()
	env["PYTHONIOENCODING"] = "utf-8"
	proc = subprocess.Popen(
		cmd,
		cwd=str(app_dir),
		env=env,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL,
	)

	# サーバーの起動を待ってからブラウザを開く
	import urllib.request
	url = f"http://localhost:{port}"
	for _ in range(30):
		try:
			urllib.request.urlopen(url, timeout=1)
			break
		except Exception:
			time.sleep(0.5)

	webbrowser.open(url)

	# Streamlitプロセスの終了を待つ
	try:
		proc.wait()
	except KeyboardInterrupt:
		proc.terminate()


if __name__ == "__main__":
	main()
