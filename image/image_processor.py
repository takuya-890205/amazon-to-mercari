"""商品画像のダウンロードと最適化"""

from pathlib import Path

import requests
from PIL import Image
from io import BytesIO

from config import (
	DOWNLOAD_DIR,
	IMAGE_FORMAT,
	IMAGE_MAX_SIZE,
	IMAGE_QUALITY,
	MERCARI_IMAGE_MAX,
)


class ImageProcessor:
	"""商品画像のダウンロード・正方形クロップ・リサイズ"""

	def __init__(self, download_dir: str | Path | None = None):
		self.download_dir = Path(download_dir) if download_dir else DOWNLOAD_DIR
		self.download_dir.mkdir(parents=True, exist_ok=True)

	def process_images(
		self,
		image_urls: list[str],
		asin: str,
		max_images: int = MERCARI_IMAGE_MAX,
	) -> list[str]:
		"""画像をダウンロードし最適化して保存。保存パスのリストを返す"""
		# 商品ごとのサブフォルダ
		save_dir = self.download_dir / asin
		save_dir.mkdir(parents=True, exist_ok=True)

		saved_paths = []
		for i, url in enumerate(image_urls[:max_images]):
			save_path = save_dir / f"{asin}_{i + 1:02d}.jpg"
			try:
				img = self._download_image(url)
				if img:
					optimized = self._optimize_for_mercari(img)
					optimized.save(
						str(save_path),
						format=IMAGE_FORMAT,
						quality=IMAGE_QUALITY,
					)
					saved_paths.append(str(save_path))
			except Exception as e:
				print(f"  画像{i + 1}のダウンロードに失敗: {e}")

		return saved_paths

	def _download_image(self, url: str) -> Image.Image | None:
		"""画像をダウンロードしてPIL Imageとして返す"""
		try:
			response = requests.get(url, timeout=15)
			response.raise_for_status()
			return Image.open(BytesIO(response.content))
		except Exception as e:
			print(f"  画像ダウンロードエラー: {e}")
			return None

	def _optimize_for_mercari(self, img: Image.Image) -> Image.Image:
		"""メルカリ向けに最適化（正方形クロップ + リサイズ）"""
		# RGBA → RGB変換
		if img.mode in ("RGBA", "P"):
			background = Image.new("RGB", img.size, (255, 255, 255))
			if img.mode == "P":
				img = img.convert("RGBA")
			background.paste(img, mask=img.split()[3])
			img = background
		elif img.mode != "RGB":
			img = img.convert("RGB")

		# 正方形にクロップ（白背景パディング）
		img = self._make_square(img)

		# リサイズ（最大1080x1080）
		if img.width > IMAGE_MAX_SIZE[0] or img.height > IMAGE_MAX_SIZE[1]:
			img.thumbnail(IMAGE_MAX_SIZE, Image.Resampling.LANCZOS)

		return img

	def _make_square(self, img: Image.Image) -> Image.Image:
		"""画像を正方形にする（短辺側に白背景パディング）"""
		width, height = img.size
		if width == height:
			return img

		size = max(width, height)
		square = Image.new("RGB", (size, size), (255, 255, 255))
		offset_x = (size - width) // 2
		offset_y = (size - height) // 2
		square.paste(img, (offset_x, offset_y))
		return square
