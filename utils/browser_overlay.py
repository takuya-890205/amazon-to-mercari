"""ブラウザページ上にフローティングステータスバーを表示するユーティリティ"""

# 共通スタイル
_BAR_STYLE = (
	"position:fixed;top:0;left:0;right:0;z-index:2147483647;"
	"background:#1a73e8;color:#fff;font-size:16px;font-weight:bold;"
	"font-family:Segoe UI,sans-serif;padding:14px 20px;text-align:center;"
	"box-shadow:0 4px 12px rgba(0,0,0,0.3);transition:opacity 0.3s,background 0.3s;"
	"pointer-events:none;letter-spacing:0.5px;"
)

# ステータスバーのテキストを更新 + ブラウザタイトルにも反映
# ※ arguments[0]が即時実行関数内で参照できないため、先にローカル変数に取得
_UPDATE_JS = """
var _msg = arguments[0];
(function(msg) {
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
})(_msg);
""".replace('%STYLE%', _BAR_STYLE).replace('%%', '%')

# ステータスバーを非表示 + タイトルを復元
_HIDE_JS = """
var bar = document.getElementById('_auto_status_bar');
if (bar) {
	bar.style.opacity = '0';
	setTimeout(function() { bar.style.display = 'none'; }, 300);
}
if (window._auto_status_original_title) {
	document.title = window._auto_status_original_title;
	delete window._auto_status_original_title;
}
"""

# 完了後に一定時間で自動的にバーを消す
_AUTO_HIDE_JS = """
var _delay = arguments[0];
setTimeout(function() {
	var bar = document.getElementById('_auto_status_bar');
	if (bar) {
		bar.style.opacity = '0';
		setTimeout(function() { bar.style.display = 'none'; }, 300);
	}
	if (window._auto_status_original_title) {
		document.title = window._auto_status_original_title;
		delete window._auto_status_original_title;
	}
}, _delay);
"""


def show_status(driver, message: str) -> None:
	"""ブラウザページ上にステータスメッセージを表示（タブタイトルにも反映）"""
	try:
		driver.execute_script(_UPDATE_JS, message)
	except Exception:
		pass


def hide_status(driver) -> None:
	"""ステータスバーを非表示にしてタイトルを復元"""
	try:
		driver.execute_script(_HIDE_JS)
	except Exception:
		pass


def auto_hide_status(driver, delay_ms: int = 5000) -> None:
	"""指定時間後にステータスバーを自動的に非表示にする"""
	try:
		driver.execute_script(_AUTO_HIDE_JS, delay_ms)
	except Exception:
		pass
