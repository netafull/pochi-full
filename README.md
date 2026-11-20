# ポチフル（試作）

ポチシリーズ全15サイトの一覧ページ。将来 https://pochi.netaful.jp/ （GitHub Pages・静的サイト）。

## 構成
- `data/sites.json` … 掲載サイト（key・name・url・group・description・color）。表示順はこの並び。
- `build.py` … sites.json から `docs/` を書き出す（標準ライブラリのみ）。
- `make_icons.py` … ポチフル自身のアイコン・OGP を `docs/static/assets/` に書き出す（pochi-branding の関数を流用、ヘッドレスChrome使用）。
- `static/style.css` … ソース。build.py が `docs/static/style.css` にコピー。
- `docs/` … 公開物（`CNAME` は公開時用）。`docs/static/icons/<key>.png` は pochi-branding/build/<key>/logo.png のコピー。
- `test_build.py` … unittest。

## ビルド
    python3 build.py
    python3 -m unittest -q
    python3 -m http.server -d docs   # 確認用

## サイトを足すとき
1. pochi-branding の sites.py に追加して、そのサイトのアイコンを作る（build/<key>/logo.png ができていること）。
2. `data/sites.json` に1行足す（group は既存4グループのどれか。新グループは出現順に並ぶ）。
3. `python3 build.py`。タイトル下の「全N」は件数から自動、`make_icons.py` の TAGLINE の「全15サイト」だけ手で直して再実行。`test_build.py` の件数(15)も直す。
   pochi-branding にアイコンが無いサイトは、`sites.json` に `"icon": "<~/Desktop/Claude からの相対パス>.png"` を書くとそのPNGを使う（build.py の SITE_ROOT 基準）。

## 注意
- ポチフルのアイコンは、ポチ各サイトの色を円グラフ状に並べた「P」ボタン（2026-11-20 案C）。色の並びは `make_icons.py` の PIE。ページのアクセントは濃い青灰 `#37474F`（`static/style.css` の `--accent`）。変えたら make_icons.py → build.py を再実行。
- アクセス解析は未設定。`build.py` の head() 内コメントの位置に GA4 を入れる。
- git・デプロイ・DNS は未実施。
