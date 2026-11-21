# ポチの新着フィード（feed.json）仕様 v1

ポチフル（pochi.netaful.jp）の「ダッシュボード」が読む、各ポチの新着ファイルの決まり。設計はマル＋オーナー（2026-11-20、設計書 v0.5）、この仕様はモルが実装用にまとめたもの。

## 置き場所
各サイトのルートに `/feed.json`（例 `https://shinkan.netaful.jp/feed.json`）。GitHub Pages は `Access-Control-Allow-Origin: *` を返すので、ポチフルのブラウザから直接読める。Cloud Run のサイト（第2段）は CORS ヘッダーを付ける。

## 形式

```json
{
  "version": 1,
  "site": "shinkan",
  "site_name": "マンガ新刊ポチ",
  "site_url": "https://shinkan.netaful.jp/",
  "generated": "2026-11-20T05:55:00+09:00",
  "items": [
    {
      "id": "shinkan:9784098632410",
      "title": "盤上のオリオン 12巻",
      "url": "https://shinkan.netaful.jp/work/banjou-no-orion/",
      "date": "2026-11-21",
      "note": "明日発売",
      "image": "https://m.media-amazon.com/images/I/xxxx.jpg",
      "image_link": "https://www.amazon.co.jp/dp/xxxx?tag=...",
      "source": "shinkan",
      "source_name": "マンガ新刊ポチ",
      "icon": null
    }
  ]
}
```

| 欄 | 必須 | 中身 |
|---|---|---|
| id | ○ | フィード全体で一意。`<source>:<そのサイトでのID>` |
| title | ○ | カードの題名 |
| url | ○ | 題名のリンク先。**そのポチの該当ページ**（絶対URL） |
| date | ○ | 新着の日付 `YYYY-MM-DD`（JST）。発売日・セール開始を見つけた日・在庫が出た日など。並び順に使う |
| note | | 種類に応じた一言（「明日発売」「20%OFF ¥1,980」「在庫あり ¥98,800」など）。数字のアクセス数などは入れない |
| brand | | お店（チェーン）やメーカーの名前。カードの note の前に出す（例「スターバックス」）。食ポチの集約 feed で使う |
| image | | 画像URL。Amazon の商品画像なら image_link を必ずセットにする |
| image_link | | 画像のリンク先。Amazon 画像のときは Amazon の商品ページ（アソシエイトタグ付き、そのサイトが普段出しているURLと同じもの） |
| source | ○ | 元のサイトのキー（チップとバッジに使う）。下の表のどれか |
| source_name | ○ | 元のサイトの名前 |
| icon | | 画像が無いときに出すアイコンの絶対URL（食ポチはカテゴリーのドット絵） |

source のキー: `shinkan` `conbini` `fastfood` `cafe` `sushi` `cupmen` `book` `kaden` `apple` `manga` `netaful`

- 食ポチ5サイトの分は新発売ポチの feed.json にまとめて入れ、source に元のサイト（conbini など）を入れる。新発売ポチ自身はチップにしない。
- items は新しい順、最大20件（新発売ポチは食ポチ5サイト分なので最大50件）。新着から3日より古いものは入れない（ポチフル側でも3日で切る）。発売予定で未来の日付は、マンガ新刊ポチの「明日発売」だけ。
- 画像の決まり（オーナー決定）：Amazon の画像は出してよいが、**画像のリンクは Amazon の商品ページ**にする。題名のリンクは各ポチのページ。食ポチは公式画像を使わないので image は入れず、icon にカテゴリーのドット絵を入れる。

## 追加の source（v1 の範囲、2026-11-21）

- `manga`（漫画ポチ、`https://manga.netaful.jp/feed.json`）。形式は上と同じ。道の駅ポチ（`michinoeki`）も feed.json を持つが、ディスカバーからは外した（オーナー決定 2026-11-21、新刊と交互に続いて流れを占めたため）。読めない間はポチフル側が黙って飛ばす（404・CORSエラーでも画面は壊れない）。image も icon も無い item は、サイトの色の帯＋ロゴで出す。
- `netaful`（ネタフル）だけは feed.json ではなく、ブラウザが WordPress REST を直接読み、ポチフル側で feed の形に変換する。
  - URL: `https://netaful.jp/wp-json/wp/v2/posts?tags=728&per_page=20&_fields=id,date,link,title,jetpack_featured_media_url`（`https://pochi.netaful.jp` への CORS 許可済み）
  - 変換: id=`netaful:<投稿ID>` / title=`title.rendered`（タグを落とし HTML の実体参照を戻した平文。表示は textContent のみ）/ url=`link` / date=`date` の先頭10文字（JST）/ image=`jetpack_featured_media_url`（image_link は付けず、題名も画像も記事へ）/ source=`netaful`、source_name=`ネタフル`。

## 並び順（ダッシュボード）
日付の新しい順（未来日付も含む）が主。**同じ日の中は source を固定の順（チップの並び）に1枚ずつ巡回**し、各 source 内は feed の新しい順のまま。そのうえで同じ source が3枚以上続かないよう分散する。
