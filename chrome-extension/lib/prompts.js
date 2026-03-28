/**
 * Gemini API用プロンプトテンプレート（prompts.py からの移植）
 */

const UNIFIED_LISTING_PROMPT = `あなたはメルカリ出品のプロです。以下のAmazon商品情報を基に、メルカリ出品用の情報を生成してください。

【Amazon商品情報】
タイトル: {title}
ブランド: {brand}
価格: {price}円
カテゴリ: {category}
説明: {description}
特徴:
{bulletPoints}
仕様:
{specifications}

【出品条件】
商品の状態: {condition}
{additionalNotes}

【テンプレート指示】
{templateInstructions}

【生成ルール】
1. タイトル: 必ず40文字以内に収めること（厳守）。文が途中で切れないようにすること。
   構成: ブランド名+商品の種類+最大の魅力（1つに絞る）。
   例: 「SONY WF-1000XM5 ノイキャン完全ワイヤレスイヤホン」「UGREEN 65W 3ポート急速充電器 GaN小型」
   NG例: 「ワイヤレスイヤホン音漏れ」のような途中で切れた不完全なタイトル
2. 説明文: 最大1000文字。以下の構成順で記載:
   1. 商品の状態・補足事項（状態、使用期間、傷・故障の有無、注意点など。購入者が最初に知りたい情報）
   2. 付属品の有無
   3. 商品概要（1-2行、購入者の興味を引く導入）
   4. 主な特徴（箇条書き3-5個、実用的なポイント）
   ※ テンプレート指示にヘッダー・フッターの指定がある場合は、説明文の冒頭・末尾にそれぞれ自然に組み込むこと。内容が重複しないように注意。
3. カテゴリ: メルカリの3階層カテゴリ [大カテゴリ, 中カテゴリ, 小カテゴリ]
   - 大カテゴリ一覧（正確に一致させること）: ファッション, ベビー・キッズ, ゲーム・おもちゃ・グッズ, ホビー・楽器・アート, チケット, 本・雑誌・漫画, CD・DVD・ブルーレイ, スマホ・タブレット・パソコン, テレビ・オーディオ・カメラ, 生活家電・空調, スポーツ, アウトドア・釣り・旅行用品, コスメ・美容, ダイエット・健康, 食品・飲料・酒, キッチン・日用品・その他, 家具・インテリア, ペット用品, DIY・工具, フラワー・ガーデニング, ハンドメイド・手芸, 車・バイク・自転車
4. ハッシュタグ: 検索されやすい5-8個（#なしのテキストのみ）

【出力形式】
以下のJSON形式のみ出力してください。JSON以外のテキストは出力しないでください。
{
    "title": "メルカリ用タイトル（40文字以内）",
    "description": "メルカリ用説明文（1000文字以内）",
    "category": ["大カテゴリ", "中カテゴリ", "小カテゴリ"],
    "hashtags": ["タグ1", "タグ2", "タグ3", "タグ4", "タグ5"]
}`;

/**
 * プロンプトのプレースホルダーを置換する
 */
function buildPrompt(product, condition, additionalNotes = "", descHeader = "", descFooter = "") {
	const bulletText = (product.bulletPoints || []).slice(0, 5).map(bp => `・${bp}`).join("\n") || "なし";
	const specText = Object.entries(product.specifications || {}).slice(0, 10).map(([k, v]) => `・${k}: ${v}`).join("\n") || "なし";
	const categoryText = (product.categoryBreadcrumb || []).join(" > ") || "不明";

	const tplParts = [];
	if (descHeader) tplParts.push(`説明文の冒頭に次の内容を含めてください: 「${descHeader.trim()}」`);
	if (descFooter) tplParts.push(`説明文の末尾に次の内容を含めてください: 「${descFooter.trim()}」`);
	const templateInstructions = tplParts.length > 0 ? tplParts.join("\n") : "特になし";

	return UNIFIED_LISTING_PROMPT
		.replace("{title}", product.title || "")
		.replace("{brand}", product.brand || "不明")
		.replace("{price}", product.price || "不明")
		.replace("{category}", categoryText)
		.replace("{description}", product.description || "なし")
		.replace("{bulletPoints}", bulletText)
		.replace("{specifications}", specText)
		.replace("{condition}", condition)
		.replace("{additionalNotes}", additionalNotes ? `補足: ${additionalNotes}` : "")
		.replace("{templateInstructions}", templateInstructions);
}
