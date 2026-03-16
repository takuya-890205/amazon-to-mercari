"""ブラウザページ上にフローティングステータスバーを表示するユーティリティ
Playwright / Selenium 両対応
"""

# 共通スタイル
_BAR_STYLE = (
	"position:fixed;top:0;left:0;right:0;z-index:2147483647;"
	"background:#1a73e8;color:#fff;font-size:16px;font-weight:bold;"
	"font-family:Segoe UI,sans-serif;padding:14px 20px;text-align:center;"
	"box-shadow:0 4px 12px rgba(0,0,0,0.3);transition:opacity 0.3s,background 0.3s;"
	"pointer-events:none;letter-spacing:0.5px;"
)

_UPDATE_JS = """
(msg) => {
	if (!window._auto_status_original_title) {
		window._auto_status_original_title = document.title;
	}
	document.title = msg;
	var bar = document.getElementById('_auto_status_bar');
	if (!bar) {
		bar = document.createElement('div');
		bar.id = '_auto_status_bar';
		bar.style.cssText = '%STYLE%';
		var style = document.createElement('style');
		style.id = '_auto_status_style';
		style.textContent = '@keyframes _status_pulse{0%%,100%%{opacity:1}50%%{opacity:0.5}}#_auto_status_bar{animation:_status_pulse 2s ease-in-out infinite}#_auto_status_bar.done{animation:none;opacity:1!important;background:#0d904f!important}';
		if (!document.getElementById('_auto_status_style')) {
			document.head.appendChild(style);
		}
		document.body.appendChild(bar);
	}
	bar.textContent = msg;
	bar.style.opacity = '1';
	bar.style.display = 'block';
	if (msg.indexOf('完了') >= 0) {
		bar.className = 'done';
	} else {
		bar.className = '';
	}
}
""".replace('%STYLE%', _BAR_STYLE).replace('%%', '%')

_HIDE_JS = """
() => {
	var bar = document.getElementById('_auto_status_bar');
	if (bar) {
		bar.style.opacity = '0';
		setTimeout(function() { bar.style.display = 'none'; }, 300);
	}
	if (window._auto_status_original_title) {
		document.title = window._auto_status_original_title;
		delete window._auto_status_original_title;
	}
}
"""


def show_status(page, message: str) -> None:
	"""ブラウザページ上にステータスメッセージを表示"""
	try:
		page.evaluate(_UPDATE_JS, message)
	except Exception:
		pass


def hide_status(page) -> None:
	"""ステータスバーを非表示にしてタイトルを復元"""
	try:
		page.evaluate(_HIDE_JS)
	except Exception:
		pass
