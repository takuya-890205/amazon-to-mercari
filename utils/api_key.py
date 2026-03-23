"""APIキーの安全な保存・取得（OS標準キーストア使用）

優先順位: keyring > 環境変数 > なし
"""

import os

SERVICE_NAME = "amazon-to-mercari"
KEY_NAME = "gemini_api_key"


def get_api_key() -> str:
	"""保存済みAPIキーを取得（keyring > 環境変数）"""
	# 1. keyringから取得
	key = _get_from_keyring()
	if key:
		return key

	# 2. 環境変数からフォールバック
	return os.getenv("GEMINI_API_KEY", "")


def save_api_key(api_key: str) -> bool:
	"""APIキーをkeyringに保存"""
	try:
		import keyring
		keyring.set_password(SERVICE_NAME, KEY_NAME, api_key)
		return True
	except Exception as e:
		print(f"キーリング保存エラー: {e}")
		return False


def delete_api_key() -> bool:
	"""APIキーをkeyringから削除"""
	try:
		import keyring
		keyring.delete_password(SERVICE_NAME, KEY_NAME)
		return True
	except Exception:
		return False


def _get_from_keyring() -> str:
	"""keyringからAPIキーを取得"""
	try:
		import keyring
		key = keyring.get_password(SERVICE_NAME, KEY_NAME)
		return key or ""
	except Exception:
		return ""
