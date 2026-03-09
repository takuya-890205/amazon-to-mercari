"""Claude CLIを使ったメルカリ向け出品テキスト生成"""

import json
import shutil
import subprocess
import sys

from generator.prompts import UNIFIED_LISTING_PROMPT
from scraper.product_data import AmazonProduct, MercariDraft


class ListingGenerator:
	"""Claude CLI経由でメルカリ出品テキストを一括生成"""

	def generate(
		self,
		product: AmazonProduct,
		condition: str = "新品、未使用",
		additional_notes: str = "",
	) -> MercariDraft:
		"""商品情報からメルカリ出品下書きを一括生成"""
		# プロンプトを構築
		bullet_text = "\n".join(f"・{bp}" for bp in product.bullet_points[:5])
		spec_text = "\n".join(f"・{k}: {v}" for k, v in list(product.specifications.items())[:10])
		category_text = " > ".join(product.category_breadcrumb) if product.category_breadcrumb else "不明"

		prompt = UNIFIED_LISTING_PROMPT.format(
			title=product.title,
			brand=product.brand or "不明",
			price=product.price or "不明",
			category=category_text,
			description=product.description or "なし",
			bullet_points=bullet_text or "なし",
			specifications=spec_text or "なし",
			condition=condition,
			additional_notes=f"補足: {additional_notes}" if additional_notes else "",
		)

		# Claude CLI呼び出し
		response_text = self._call_cli(prompt)

		# JSONパース
		result = self._parse_response(response_text)

		return MercariDraft(
			title=result.get("title", product.title[:40]),
			description=result.get("description", ""),
			category=result.get("category", product.category_breadcrumb[:3]),
			brand=product.brand or "",
			condition=condition,
			hashtags=result.get("hashtags", []),
			source_url=product.url,
		)

	def _get_claude_cmd(self) -> str:
		"""環境に応じたClaude CLIコマンド名を返す"""
		# Windowsでは claude.cmd を使う
		if sys.platform == "win32":
			cmd = shutil.which("claude.cmd") or shutil.which("claude")
		else:
			cmd = shutil.which("claude")
		if not cmd:
			raise RuntimeError("Claude CLIが見つかりません。npm install -g @anthropic-ai/claude-code でインストールしてください。")
		return cmd

	def _call_cli(self, prompt: str) -> str:
		"""Claude CLIを呼び出してテキスト生成"""
		claude_cmd = self._get_claude_cmd()
		# CLAUDECODE環境変数をunsetしてネスト制限を回避
		env = dict(__import__("os").environ)
		env.pop("CLAUDECODE", None)
		result = subprocess.run(
			[claude_cmd, "-p", "-", "--output-format", "json"],
			capture_output=True,
			text=True,
			timeout=120,
			encoding="utf-8",
			env=env,
			input=prompt,
		)

		if result.returncode != 0:
			raise RuntimeError(f"Claude CLI エラー: {result.stderr}")

		# Claude CLIのJSON出力から結果テキストを取得
		try:
			output = json.loads(result.stdout)
			return output.get("result", result.stdout)
		except json.JSONDecodeError:
			# JSON形式でない場合はそのまま返す
			return result.stdout

	def _parse_response(self, text: str) -> dict:
		"""Claude CLIのレスポンスからJSONを抽出してパース"""
		text = text.strip()

		# ```json ... ``` ブロックを抽出
		if "```json" in text:
			text = text.split("```json")[1].split("```")[0].strip()
		elif "```" in text:
			text = text.split("```")[1].split("```")[0].strip()

		# 直接JSONの場合
		try:
			return json.loads(text)
		except json.JSONDecodeError:
			# { から } までを切り出してリトライ
			start = text.find("{")
			end = text.rfind("}") + 1
			if start >= 0 and end > start:
				try:
					return json.loads(text[start:end])
				except json.JSONDecodeError:
					pass

		print("警告: JSONパースに失敗しました。デフォルト値を使用します。")
		return {}
